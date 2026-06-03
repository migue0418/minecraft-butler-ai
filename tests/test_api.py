import asyncio
import os
import re
import uuid
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL, make_url

from app.core.database import close_database
from app.core.datetime import utcnow
from app.core.limiter import limiter
from app.core.settings import get_settings
from app.features.auth.security import hash_password
from app.main import create_app

DEFAULT_TEST_DATABASE_ADMIN_URL = (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres"
)


def _get_test_database_admin_url() -> str:
    return os.getenv("TEST_DATABASE_ADMIN_URL", DEFAULT_TEST_DATABASE_ADMIN_URL)


def _quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", identifier):
        raise ValueError(f"Invalid PostgreSQL identifier: {identifier}")
    return f'"{identifier}"'


def _make_asyncpg_connect_kwargs(url: URL) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "host": url.host or "127.0.0.1",
        "port": int(url.port or 5432),
        "database": url.database or "postgres",
    }
    if url.username is not None:
        kwargs["user"] = url.username
    if url.password is not None:
        kwargs["password"] = url.password
    return kwargs


async def _create_test_database(admin_url: str, database_name: str) -> str:
    url = make_url(admin_url)
    admin_connection = await asyncpg.connect(**_make_asyncpg_connect_kwargs(url))
    try:
        await admin_connection.execute(
            f"CREATE DATABASE {_quote_identifier(database_name)}",
        )
    finally:
        await admin_connection.close()
    return url.set(database=database_name).render_as_string(hide_password=False)


async def _drop_test_database(admin_url: str, database_name: str) -> None:
    url = make_url(admin_url)
    admin_connection = await asyncpg.connect(**_make_asyncpg_connect_kwargs(url))
    try:
        await admin_connection.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            database_name,
        )
        await admin_connection.execute(
            f"DROP DATABASE IF EXISTS {_quote_identifier(database_name)}",
        )
    finally:
        await admin_connection.close()


async def _connect_to_database(database_url: str) -> asyncpg.Connection:
    return await asyncpg.connect(**_make_asyncpg_connect_kwargs(make_url(database_url)))


async def _seed_legacy_schema(database_url: str) -> None:
    """Simulates a pre-Alembic database that's already at revision 0001 state.

    Creates the full schema that 0001 produces (without the lockout fields added in 0002),
    stamps alembic_version to '0001', and inserts an admin user without roles.
    On startup, migration 0002 runs (adding failed_login_attempts/locked_until) and the
    lifespan seed assigns roles to the existing admin user.
    """
    connection = await _connect_to_database(database_url)
    try:
        await connection.execute(
            """
            CREATE TABLE users (
                id SERIAL NOT NULL,
                username VARCHAR(50) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                email VARCHAR(255),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                PRIMARY KEY (id)
            )
            """,
        )
        await connection.execute(
            "CREATE UNIQUE INDEX ix_users_username ON users (username)",
        )
        await connection.execute(
            """
            CREATE TABLE roles (
                id SERIAL NOT NULL,
                name VARCHAR(50) NOT NULL,
                description VARCHAR(255) NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                PRIMARY KEY (id)
            )
            """,
        )
        await connection.execute("CREATE UNIQUE INDEX ix_roles_name ON roles (name)")
        await connection.execute(
            """
            CREATE TABLE user_roles (
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, role_id),
                CONSTRAINT uq_user_roles_user_id_role_id UNIQUE (user_id, role_id),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE
            )
            """,
        )
        await connection.execute(
            """
            CREATE TABLE auth_refresh_tokens (
                id SERIAL NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                token_hash VARCHAR(64) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP NULL,
                user_agent VARCHAR(255) NULL,
                remember_me BOOLEAN NOT NULL,
                PRIMARY KEY (id)
            )
            """,
        )
        await connection.execute(
            """
            CREATE UNIQUE INDEX ix_auth_refresh_tokens_token_hash
            ON auth_refresh_tokens (token_hash)
            """,
        )
        await connection.execute(
            """
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
            """,
        )
        await connection.execute(
            "INSERT INTO alembic_version (version_num) VALUES ('0001')",
        )
        now = utcnow()
        await connection.execute(
            """
            INSERT INTO users (username, password_hash, is_active, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            "admin",
            hash_password("ChangeMe123!"),
            True,
            now,
            now,
        )
    finally:
        await connection.close()


@contextmanager
def build_client(
    monkeypatch,
    initializer: Callable[[str], Awaitable[None]] | None = None,
) -> Generator[TestClient, None, None]:
    admin_url = _get_test_database_admin_url()
    database_name = f"autorecambios_test_{uuid.uuid4().hex}"
    try:
        database_url = asyncio.run(_create_test_database(admin_url, database_name))
    except (OSError, asyncpg.PostgresError) as exc:
        raise RuntimeError(
            "PostgreSQL de tests no disponible. Arranca PostgreSQL o ajusta "
            "TEST_DATABASE_ADMIN_URL antes de ejecutar pytest.",
        ) from exc

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "ChangeMe123!")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()

    if initializer is not None:
        asyncio.run(initializer(database_url))

    # En tests usamos MemorySaver en lugar de Redis para no requerir un servidor Redis.
    from langgraph.checkpoint.memory import MemorySaver

    from app.features.butler.graph import graph as _graph_module
    from app.features.butler.stt import service as _stt_module

    test_graph = _graph_module.compile_graph(checkpointer=MemorySaver())
    _graph_module._compiled_graph = test_graph

    # Evitar que el lifespan cargue el modelo Whisper real en tests.
    _stt_module._whisper_model = MagicMock()

    try:
        limiter._storage.reset()
        app = create_app()
        with TestClient(app) as client:
            yield client
    finally:
        asyncio.run(close_database())
        get_settings.cache_clear()
        _graph_module._compiled_graph = None  # reset singleton para siguientes tests
        _stt_module._whisper_model = None  # reset singleton para siguientes tests
        asyncio.run(_drop_test_database(admin_url, database_name))


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def login(
    client: TestClient,
    *,
    username: str = "admin",
    password: str = "ChangeMe123!",
    remember_me: bool = True,
) -> dict:
    response = client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": password,
            "remember_me": remember_me,
        },
    )
    assert response.status_code == 200
    return response.json()


def get_role_map(client: TestClient, access_token: str) -> dict[str, int]:
    response = client.get("/api/roles", headers=auth_headers(access_token))
    assert response.status_code == 200
    return {role["name"]: role["id"] for role in response.json()}


def create_user(
    client: TestClient,
    access_token: str,
    *,
    username: str,
    password: str,
    role_ids: list[int],
    full_name: str | None = None,
    email: str | None = None,
    is_active: bool = True,
) -> dict:
    response = client.post(
        "/api/users",
        json={
            "username": username,
            "password": password,
            "role_ids": role_ids,
            "full_name": full_name,
            "email": email,
            "is_active": is_active,
        },
        headers=auth_headers(access_token),
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def client(monkeypatch) -> Generator[TestClient, None, None]:
    with build_client(monkeypatch) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_and_me(client: TestClient) -> None:
    tokens = login(client)
    me_response = client.get(
        "/api/auth/me",
        headers=auth_headers(tokens["access_token"]),
    )
    assert me_response.status_code == 200
    assert me_response.json() == {
        "id": 1,
        "username": "admin",
        "full_name": "Administrador",
        "email": None,
        "is_active": True,
        "roles": ["admin"],
    }


def test_me_requires_bearer(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_refresh_rotation_and_reuse_detection(client: TestClient) -> None:
    login(client)
    original_cookie = client.cookies.get("refresh_token")
    assert original_cookie is not None

    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 200
    rotated_cookie = client.cookies.get("refresh_token")
    assert rotated_cookie is not None
    assert rotated_cookie != original_cookie

    client.cookies.set(
        "refresh_token",
        original_cookie,
        path="/api/auth",
    )
    reuse_response = client.post("/api/auth/refresh")
    assert reuse_response.status_code == 401


def test_sessions_and_revoke(client: TestClient) -> None:
    tokens = login(client)
    headers = auth_headers(tokens["access_token"])

    sessions_response = client.get("/api/auth/sessions", headers=headers)
    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True

    delete_response = client.delete(
        f"/api/auth/sessions/{sessions[0]['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    sessions_after = client.get("/api/auth/sessions", headers=headers)
    assert sessions_after.status_code == 200
    assert sessions_after.json() == []


def test_legacy_schema_is_migrated_and_seeded(monkeypatch) -> None:
    with build_client(monkeypatch, initializer=_seed_legacy_schema) as legacy_client:
        tokens = login(legacy_client)
        me_response = legacy_client.get(
            "/api/auth/me",
            headers=auth_headers(tokens["access_token"]),
        )
        assert me_response.status_code == 200
        assert me_response.json()["roles"] == ["admin"]

        roles_response = legacy_client.get(
            "/api/roles",
            headers=auth_headers(tokens["access_token"]),
        )
        assert roles_response.status_code == 200
        role_names = {role["name"] for role in roles_response.json()}
        assert role_names == {"admin", "user"}


def test_admin_can_manage_roles_and_users(client: TestClient) -> None:
    admin_tokens = login(client)
    admin_headers = auth_headers(admin_tokens["access_token"])
    role_map = get_role_map(client, admin_tokens["access_token"])

    create_role_response = client.post(
        "/api/roles",
        json={"name": "manager", "description": "Gestion de stock"},
        headers=admin_headers,
    )
    assert create_role_response.status_code == 201
    manager_role = create_role_response.json()
    assert manager_role["name"] == "manager"

    duplicate_role_response = client.post(
        "/api/roles",
        json={"name": "manager", "description": "Duplicado"},
        headers=admin_headers,
    )
    assert duplicate_role_response.status_code == 409

    update_role_response = client.put(
        f"/api/roles/{manager_role['id']}",
        json={"name": "manager", "description": "Gestion de stock y equipo"},
        headers=admin_headers,
    )
    assert update_role_response.status_code == 200
    assert update_role_response.json()["description"] == "Gestion de stock y equipo"

    created_user = create_user(
        client,
        admin_tokens["access_token"],
        username="operario",
        password="Operario123!",
        role_ids=[role_map["user"], manager_role["id"]],
        full_name="Operario Principal",
        email="operario@example.com",
    )
    assert created_user["roles"] == ["manager", "user"]

    duplicate_user_response = client.post(
        "/api/users",
        json={
            "username": "operario",
            "password": "Operario123!",
            "role_ids": [role_map["user"]],
            "full_name": None,
            "email": None,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert duplicate_user_response.status_code == 409

    list_users_response = client.get("/api/users", headers=admin_headers)
    assert list_users_response.status_code == 200
    assert any(user["username"] == "operario" for user in list_users_response.json())

    detail_response = client.get(
        f"/api/users/{created_user['id']}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["role_ids"] == sorted(
        [role_map["user"], manager_role["id"]],
    )

    user_tokens = login(client, username="operario", password="Operario123!")
    user_headers = auth_headers(user_tokens["access_token"])
    user_refresh_cookie = client.cookies.get("refresh_token")
    assert user_refresh_cookie is not None

    forbidden_users_response = client.get("/api/users", headers=user_headers)
    assert forbidden_users_response.status_code == 403
    forbidden_roles_response = client.get("/api/roles", headers=user_headers)
    assert forbidden_roles_response.status_code == 403

    update_user_response = client.put(
        f"/api/users/{created_user['id']}",
        json={
            "username": "operario",
            "full_name": "Operario Desactivado",
            "email": "operario@example.com",
            "is_active": False,
            "role_ids": [manager_role["id"]],
        },
        headers=admin_headers,
    )
    assert update_user_response.status_code == 200
    assert update_user_response.json()["is_active"] is False
    assert update_user_response.json()["roles"] == ["manager"]

    client.cookies.set("refresh_token", user_refresh_cookie, path="/api/auth")
    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 401


def test_change_own_password_revokes_sessions(client: TestClient) -> None:
    admin_tokens = login(client)
    role_map = get_role_map(client, admin_tokens["access_token"])
    create_user(
        client,
        admin_tokens["access_token"],
        username="tecnico",
        password="Tecnico123!",
        role_ids=[role_map["user"]],
        full_name="Tecnico",
    )

    user_tokens = login(client, username="tecnico", password="Tecnico123!")
    user_refresh_cookie = client.cookies.get("refresh_token")
    assert user_refresh_cookie is not None

    change_password_response = client.post(
        "/api/users/me/change-password",
        json={
            "current_password": "Tecnico123!",
            "new_password": "Tecnico456!",
        },
        headers=auth_headers(user_tokens["access_token"]),
    )
    assert change_password_response.status_code == 204

    client.cookies.set("refresh_token", user_refresh_cookie, path="/api/auth")
    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 401

    old_login_response = client.post(
        "/api/auth/login",
        json={
            "username": "tecnico",
            "password": "Tecnico123!",
            "remember_me": True,
        },
    )
    assert old_login_response.status_code == 401

    new_login_response = client.post(
        "/api/auth/login",
        json={
            "username": "tecnico",
            "password": "Tecnico456!",
            "remember_me": True,
        },
    )
    assert new_login_response.status_code == 200


def test_admin_can_reset_password_and_last_admin_is_protected(
    client: TestClient,
) -> None:
    admin_tokens = login(client)
    admin_headers = auth_headers(admin_tokens["access_token"])
    role_map = get_role_map(client, admin_tokens["access_token"])

    created_user = create_user(
        client,
        admin_tokens["access_token"],
        username="almacen",
        password="Almacen123!",
        role_ids=[role_map["user"]],
        full_name="Usuario Almacen",
    )

    _ = login(client, username="almacen", password="Almacen123!")
    user_refresh_cookie = client.cookies.get("refresh_token")
    assert user_refresh_cookie is not None

    reset_password_response = client.post(
        f"/api/users/{created_user['id']}/reset-password",
        json={"new_password": "Almacen456!"},
        headers=admin_headers,
    )
    assert reset_password_response.status_code == 204

    client.cookies.set("refresh_token", user_refresh_cookie, path="/api/auth")
    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 401

    old_login_response = client.post(
        "/api/auth/login",
        json={
            "username": "almacen",
            "password": "Almacen123!",
            "remember_me": True,
        },
    )
    assert old_login_response.status_code == 401

    new_login_response = client.post(
        "/api/auth/login",
        json={
            "username": "almacen",
            "password": "Almacen456!",
            "remember_me": True,
        },
    )
    assert new_login_response.status_code == 200

    admin_detail_response = client.get("/api/users", headers=admin_headers)
    admin_id = next(
        user["id"]
        for user in admin_detail_response.json()
        if user["username"] == "admin"
    )

    delete_admin_response = client.delete(
        f"/api/users/{admin_id}",
        headers=admin_headers,
    )
    assert delete_admin_response.status_code == 400

    deactivate_admin_response = client.put(
        f"/api/users/{admin_id}",
        json={
            "username": "admin",
            "full_name": "Administrador",
            "email": None,
            "is_active": False,
            "role_ids": [role_map["admin"]],
        },
        headers=admin_headers,
    )
    assert deactivate_admin_response.status_code == 400

    demote_admin_response = client.put(
        f"/api/users/{admin_id}",
        json={
            "username": "admin",
            "full_name": "Administrador",
            "email": None,
            "is_active": True,
            "role_ids": [role_map["user"]],
        },
        headers=admin_headers,
    )
    assert demote_admin_response.status_code == 400


def test_ask_without_auth(client: TestClient) -> None:
    response = client.post("/api/butler/ask", json={"message": "hola"})
    assert response.status_code == 401


_SPEAK_RESPONSE = [{"type": "speak", "message": "Respuesta de prueba"}]
_MOVE_RESPONSE = [
    {
        "type": "move_to_position",
        "message": "Me dirijo allí.",
        "x": 100,
        "y": 64,
        "z": -50,
    },
]


def test_ask_with_valid_token(client: TestClient) -> None:
    tokens = login(client)
    with patch(
        "app.features.butler.service.ButlerService.run",
        new_callable=AsyncMock,
        return_value=[
            type(
                "ButlerAction",
                (),
                {
                    "type": "speak",
                    "message": "Respuesta de prueba",
                    "x": None,
                    "y": None,
                    "z": None,
                },
            )(),
        ],
    ):
        response = client.post(
            "/api/butler/ask",
            json={"message": "hola Alfred"},
            headers=auth_headers(tokens["access_token"]),
        )
    assert response.status_code == 200
    actions = response.json()
    assert len(actions) == 1
    assert actions[0]["type"] == "speak"


def test_ask_response_is_list(client: TestClient) -> None:
    tokens = login(client)
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "message": "test",
            "intent": "speak",
            "doc_type": "none",
            "retrieved_docs": [],
            "messages": [],
            "actions": _SPEAK_RESPONSE,
        },
    )
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        response = client.post(
            "/api/butler/ask",
            json={"message": "test"},
            headers=auth_headers(tokens["access_token"]),
        )
    assert isinstance(response.json(), list)


def test_ask_with_coordinates_returns_move_to_position(client: TestClient) -> None:
    tokens = login(client)
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "message": "ve a 100 64 -50",
            "intent": "move",
            "doc_type": "none",
            "retrieved_docs": [],
            "messages": [],
            "actions": _MOVE_RESPONSE,
        },
    )
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        response = client.post(
            "/api/butler/ask",
            json={"message": "ve a 100 64 -50"},
            headers=auth_headers(tokens["access_token"]),
        )
    assert response.status_code == 200
    actions = response.json()
    assert len(actions) == 1
    assert actions[0]["type"] == "move_to_position"
    assert actions[0]["x"] == 100
    assert actions[0]["y"] == 64
    assert actions[0]["z"] == -50


def test_ask_without_coordinates_returns_speak(client: TestClient) -> None:
    tokens = login(client)
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "message": "hola Alfred",
            "intent": "speak",
            "doc_type": "none",
            "retrieved_docs": [],
            "messages": [],
            "actions": _SPEAK_RESPONSE,
        },
    )
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        response = client.post(
            "/api/butler/ask",
            json={"message": "hola Alfred"},
            headers=auth_headers(tokens["access_token"]),
        )
    assert response.status_code == 200
    actions = response.json()
    assert len(actions) == 1
    assert actions[0]["type"] == "speak"


# ── Butler streaming (SSE) tests ─────────────────────────────────────────────


async def _async_gen_actions(actions):
    for a in actions:
        yield a


def test_ask_stream_first_event_is_echo(client: TestClient) -> None:
    tokens = login(client)
    mock_action = type(
        "BA",
        (),
        {
            "type": "speak",
            "message": "Hola!",
            "x": None,
            "y": None,
            "z": None,
            "model_dump": lambda self, **kw: {"type": "speak", "message": "Hola!"},
        },
    )()
    with patch(
        "app.features.butler.service.ButlerService.stream",
        return_value=_async_gen_actions([mock_action]),
    ):
        response = client.post(
            "/api/butler/ask-stream",
            json={"message": "hola Alfred"},
            headers=auth_headers(tokens["access_token"]),
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    lines = [ln for ln in response.text.split("\n") if ln.startswith("data: ")]
    import json as _j

    first = _j.loads(lines[0][6:])
    assert first["type"] == "echo"
    assert "[Tú]" in first["message"]
    assert "hola Alfred" in first["message"]
    assert lines[-1] == "data: [DONE]"


def test_ask_stream_contains_action_events(client: TestClient) -> None:
    tokens = login(client)
    mock_action = type(
        "BA",
        (),
        {
            "type": "speak",
            "message": "Respuesta de prueba",
            "x": None,
            "y": None,
            "z": None,
            "model_dump": lambda self, **kw: {
                "type": "speak",
                "message": "Respuesta de prueba",
            },
        },
    )()
    with patch(
        "app.features.butler.service.ButlerService.stream",
        return_value=_async_gen_actions([mock_action]),
    ):
        response = client.post(
            "/api/butler/ask-stream",
            json={"message": "test"},
            headers=auth_headers(tokens["access_token"]),
        )
    import json as _j

    lines = [ln for ln in response.text.split("\n") if ln.startswith("data: ")]
    # lines[0] = echo, lines[1] = speak action, lines[-1] = [DONE]
    assert len(lines) == 3
    action_event = _j.loads(lines[1][6:])
    assert action_event["type"] == "speak"
    assert action_event["message"] == "Respuesta de prueba"


def test_ask_stream_without_auth_returns_401(client: TestClient) -> None:
    response = client.post("/api/butler/ask-stream", json={"message": "hola"})
    assert response.status_code == 401


def test_ask_voice_stream_echo_has_mic_prefix(client: TestClient) -> None:
    tokens = login(client)
    mock_action = type(
        "BA",
        (),
        {
            "type": "speak",
            "message": "ok",
            "x": None,
            "y": None,
            "z": None,
            "model_dump": lambda self, **kw: {"type": "speak", "message": "ok"},
        },
    )()
    with (
        patch(
            "app.features.butler.router.transcribe_audio",
            return_value="como crafteo una espada",
        ),
        patch(
            "app.features.butler.service.ButlerService.stream",
            return_value=_async_gen_actions([mock_action]),
        ),
    ):
        response = client.post(
            "/api/butler/ask-voice-stream",
            files={"audio": ("test.wav", b"fake_wav_bytes", "audio/wav")},
            headers=auth_headers(tokens["access_token"]),
        )
    assert response.status_code == 200
    import json as _j

    lines = [ln for ln in response.text.split("\n") if ln.startswith("data: ")]
    first = _j.loads(lines[0][6:])
    assert first["type"] == "echo"
    assert "🎤" in first["message"] or "\U0001f3a4" in first["message"]
    assert "como crafteo una espada" in first["message"]


# ── Butler rate limiting tests ───────────────────────────────────────────────


def test_ask_rate_limit_returns_429_after_20_requests(client: TestClient) -> None:
    """POST /api/butler/ask devuelve 429 después de 20 peticiones por minuto."""
    tokens = login(client)
    limiter._storage.reset()
    with patch(
        "app.features.butler.service.ButlerService.run",
        new_callable=AsyncMock,
        return_value=[
            type(
                "BA",
                (),
                {"type": "speak", "message": "ok", "x": None, "y": None, "z": None},
            )(),
        ],
    ):
        responses = [
            client.post(
                "/api/butler/ask",
                json={"message": "hola"},
                headers=auth_headers(tokens["access_token"]),
            )
            for _ in range(21)
        ]

    ok_responses = [r for r in responses if r.status_code == 200]
    rate_limited = [r for r in responses if r.status_code == 429]
    assert len(ok_responses) == 20
    assert len(rate_limited) == 1


# ── Butler world_context router tests ────────────────────────────────────────

_WORLD_CONTEXT_PAYLOAD = {
    "player": {
        "x": 100,
        "y": 64,
        "z": -50,
        "inventory": [{"item": "minecraft:iron_ingot", "count": 5}],
    },
    "chests": [
        {"name": "despensa", "items": [{"item": "minecraft:bread", "count": 10}]},
    ],
    "nearby": {
        "animals": [{"type": "minecraft:cow", "count": 3}],
        "crops": [{"type": "minecraft:wheat", "mature": 5, "growing": 2}],
    },
}


def test_ask_without_world_context_still_works(client: TestClient) -> None:
    tokens = login(client)
    with patch(
        "app.features.butler.service.ButlerService.run",
        new_callable=AsyncMock,
        return_value=[
            type(
                "BA",
                (),
                {"type": "speak", "message": "ok", "x": None, "y": None, "z": None},
            )(),
        ],
    ):
        response = client.post(
            "/api/butler/ask",
            json={"message": "hola"},
            headers=auth_headers(tokens["access_token"]),
        )
    assert response.status_code == 200


def test_ask_with_valid_world_context_returns_200(client: TestClient) -> None:
    tokens = login(client)
    with patch(
        "app.features.butler.service.ButlerService.run",
        new_callable=AsyncMock,
        return_value=[
            type(
                "BA",
                (),
                {"type": "speak", "message": "ok", "x": None, "y": None, "z": None},
            )(),
        ],
    ) as mock_run:
        response = client.post(
            "/api/butler/ask",
            json={"message": "¿tengo hierro?", "world_context": _WORLD_CONTEXT_PAYLOAD},
            headers=auth_headers(tokens["access_token"]),
        )
    assert response.status_code == 200
    call_kwargs = mock_run.call_args
    assert call_kwargs.kwargs.get("world_context") is not None
    assert call_kwargs.kwargs["world_context"]["player"]["x"] == 100


def test_ask_with_invalid_world_context_returns_422(client: TestClient) -> None:
    tokens = login(client)
    response = client.post(
        "/api/butler/ask",
        json={
            "message": "test",
            "world_context": {"player": "not-an-object", "nearby": {}},
        },
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422


# ── Butler graph unit tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_butler_service_question_intent() -> None:
    """ButlerService.run devuelve speak cuando el grafo clasifica 'question'."""
    from app.features.butler.graph.graph import reset_compiled_graph

    reset_compiled_graph()
    mock_state = {
        "message": "¿cómo fabrico una espada?",
        "intent": "question",
        "doc_type": "item",
        "retrieved_docs": [],
        "messages": [],
        "actions": [{"type": "speak", "message": "Necesitas 2 palos y 3 diamantes."}],
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_state)
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        from app.features.butler.service import ButlerService

        service = ButlerService()
        actions = await service.run("¿cómo fabrico una espada?")

    assert len(actions) == 1
    assert actions[0].type == "speak"
    assert "diamantes" in actions[0].message


@pytest.mark.asyncio
async def test_butler_service_move_intent() -> None:
    """ButlerService.run devuelve move_to_position cuando el grafo clasifica 'move'."""
    from app.features.butler.graph.graph import reset_compiled_graph

    reset_compiled_graph()
    mock_state = {
        "message": "ve a 100 64 -200",
        "intent": "move",
        "doc_type": "none",
        "retrieved_docs": [],
        "messages": [],
        "actions": [
            {
                "type": "move_to_position",
                "message": "Me dirijo allí.",
                "x": 100,
                "y": 64,
                "z": -200,
            },
        ],
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_state)
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        from app.features.butler.service import ButlerService

        service = ButlerService()
        actions = await service.run("ve a 100 64 -200")

    assert len(actions) == 1
    assert actions[0].type == "move_to_position"
    assert actions[0].x == 100
    assert actions[0].y == 64
    assert actions[0].z == -200


# ── classify_intent doc_type tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_intent_item_question_sets_doc_type() -> None:
    """classify_intent devuelve doc_type='item' para preguntas de crafteo."""
    from unittest.mock import AsyncMock as _AsyncMock

    from app.features.butler.graph.nodes import IntentOutput, classify_intent

    mock_result = IntentOutput(intent="question", doc_type="item")
    with patch(
        "app.features.butler.graph.nodes.get_llm",
        return_value=MagicMock(
            with_structured_output=MagicMock(
                return_value=MagicMock(
                    ainvoke=_AsyncMock(return_value=mock_result),
                ),
            ),
        ),
    ):
        result = await classify_intent(
            {
                "message": "¿cómo fabrico una espada de diamante?",
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
            },
        )

    assert result["intent"] == "question"
    assert result["doc_type"] == "item"


@pytest.mark.asyncio
async def test_classify_intent_mob_question_sets_doc_type() -> None:
    """classify_intent devuelve doc_type='mob' para preguntas sobre mobs."""
    from unittest.mock import AsyncMock as _AsyncMock

    from app.features.butler.graph.nodes import IntentOutput, classify_intent

    mock_result = IntentOutput(intent="question", doc_type="mob")
    with patch(
        "app.features.butler.graph.nodes.get_llm",
        return_value=MagicMock(
            with_structured_output=MagicMock(
                return_value=MagicMock(
                    ainvoke=_AsyncMock(return_value=mock_result),
                ),
            ),
        ),
    ):
        result = await classify_intent(
            {
                "message": "¿qué dropea un creeper?",
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
            },
        )

    assert result["intent"] == "question"
    assert result["doc_type"] == "mob"


@pytest.mark.asyncio
async def test_classify_intent_move_sets_doc_type_none() -> None:
    """classify_intent devuelve doc_type='none' para intents de movimiento."""
    from unittest.mock import AsyncMock as _AsyncMock

    from app.features.butler.graph.nodes import IntentOutput, classify_intent

    mock_result = IntentOutput(intent="move", doc_type="none")
    with patch(
        "app.features.butler.graph.nodes.get_llm",
        return_value=MagicMock(
            with_structured_output=MagicMock(
                return_value=MagicMock(
                    ainvoke=_AsyncMock(return_value=mock_result),
                ),
            ),
        ),
    ):
        result = await classify_intent(
            {
                "message": "ve a 100 64 -200",
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
            },
        )

    assert result["intent"] == "move"
    assert result["doc_type"] == "none"


# ── retrieve_context (sin filtro duro por doc_type) ──────────────────────────


@pytest.mark.asyncio
async def test_retrieve_context_does_not_hard_filter_by_doc_type() -> None:
    """retrieve_context NO filtra por doc_type: el clasificador puede equivocar el
    tipo (p.ej. "¿qué items dropea una vaca?" → item, excluyendo el doc del mob
    Cow). El retriever denso elige el tipo correcto por semántica."""
    from app.features.butler.graph.nodes import retrieve_context

    mock_retriever = MagicMock(return_value=[])
    with patch(
        "app.features.butler.rag.get_retriever",
        return_value=mock_retriever,
    ):
        await retrieve_context(
            {
                "message": "¿qué items dropea una vaca?",
                "intent": "question",
                "doc_type": "item",
                "retrieved_docs": [],
                "actions": [],
            },
        )

    mock_retriever.assert_called_once_with("¿qué items dropea una vaca?")


# ── conversation-memory: session_id y multi-turn ─────────────────────────────


def test_ask_accepts_optional_session_id(client: TestClient) -> None:
    """AskRequest acepta session_id opcional; sin él responde 200 igual."""
    tokens = login(client)
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "message": "hola",
            "intent": "speak",
            "doc_type": "none",
            "retrieved_docs": [],
            "messages": [],
            "actions": _SPEAK_RESPONSE,
        },
    )
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        r1 = client.post(
            "/api/butler/ask",
            json={"message": "hola"},
            headers=auth_headers(tokens["access_token"]),
        )
        r2 = client.post(
            "/api/butler/ask",
            json={"message": "hola", "session_id": "player-abc"},
            headers=auth_headers(tokens["access_token"]),
        )
    assert r1.status_code == 200
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_butler_service_uses_session_id_as_thread_id() -> None:
    """ButlerService.run pasa session_id como thread_id al grafo."""
    from app.features.butler.graph.graph import reset_compiled_graph

    reset_compiled_graph()
    mock_state = {
        "message": "test",
        "intent": "speak",
        "doc_type": "none",
        "retrieved_docs": [],
        "messages": [],
        "actions": [{"type": "speak", "message": "ok"}],
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_state)
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        from app.features.butler.service import ButlerService

        service = ButlerService()
        await service.run("test", session_id="player-xyz")

    _, call_kwargs = mock_graph.ainvoke.call_args
    thread_id = call_kwargs.get("config", {}).get("configurable", {}).get("thread_id")
    assert thread_id == "player-xyz"


@pytest.mark.asyncio
async def test_butler_service_ephemeral_thread_without_session_id() -> None:
    """Sin session_id el servicio usa un thread_id efímero diferente en cada llamada."""
    from app.features.butler.graph.graph import reset_compiled_graph

    reset_compiled_graph()
    mock_state = {
        "message": "test",
        "intent": "speak",
        "doc_type": "none",
        "retrieved_docs": [],
        "messages": [],
        "actions": [{"type": "speak", "message": "ok"}],
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_state)
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        from app.features.butler.service import ButlerService

        service = ButlerService()
        await service.run("msg1")
        await service.run("msg2")

    calls = mock_graph.ainvoke.call_args_list
    tid1 = (
        calls[0].kwargs.get("config", {}).get("configurable", {}).get("thread_id", "")
    )
    tid2 = (
        calls[1].kwargs.get("config", {}).get("configurable", {}).get("thread_id", "")
    )
    assert tid1 != tid2
    assert tid1.startswith("ephemeral-")
    assert tid2.startswith("ephemeral-")


@pytest.mark.asyncio
async def test_multi_turn_memory_with_memory_saver() -> None:
    """Dos turnos con el mismo thread_id acumulan messages en el estado."""
    from unittest.mock import AsyncMock as _AsyncMock

    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.checkpoint.memory import MemorySaver

    from app.features.butler.graph.graph import compile_graph
    from app.features.butler.graph.routing import route_intent

    graph = compile_graph(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "test-session"}}

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(
        return_value=MagicMock(
            ainvoke=_AsyncMock(
                return_value=MagicMock(
                    intent="speak",
                    doc_type="none",
                    needs_world_context=False,
                ),
            ),
        ),
    )
    mock_llm.ainvoke = _AsyncMock(
        return_value=MagicMock(content="Respuesta del asistente."),
    )

    with patch("app.features.butler.graph.nodes.get_llm", return_value=mock_llm):
        await graph.ainvoke(
            {
                "message": "¿cómo fabrico una espada?",
                "messages": [HumanMessage(content="¿cómo fabrico una espada?")],
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
            },
            config=cfg,
        )
        state2 = await graph.ainvoke(
            {
                "message": "¿y si no tengo materiales?",
                "messages": [HumanMessage(content="¿y si no tengo materiales?")],
                "intent": "",
                "doc_type": "none",
                "retrieved_docs": [],
                "actions": [],
            },
            config=cfg,
        )

    # Después de dos turnos el historial debe tener al menos: H1 + AI1 + H2 + AI2
    assert len(state2["messages"]) >= 4
    assert isinstance(state2["messages"][0], HumanMessage)
    assert isinstance(state2["messages"][-1], AIMessage)


# ── voice-stt-input: input_mode y endpoint /ask-voice ────────────────────────


@pytest.mark.asyncio
async def test_butler_service_text_input_mode_sets_metadata() -> None:
    """run() con input_mode='text' crea HumanMessage con metadata input_mode=text."""
    from app.features.butler.graph.graph import reset_compiled_graph

    reset_compiled_graph()
    mock_state = {
        "message": "test",
        "intent": "speak",
        "doc_type": "none",
        "retrieved_docs": [],
        "messages": [],
        "input_mode": "text",
        "actions": [{"type": "speak", "message": "ok"}],
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_state)
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        from app.features.butler.service import ButlerService

        await ButlerService().run("test", input_mode="text")

    _, call_kwargs = mock_graph.ainvoke.call_args
    state_input = mock_graph.ainvoke.call_args[0][0]
    human_msg = state_input["messages"][0]
    assert human_msg.metadata.get("input_mode") == "text"
    assert state_input["input_mode"] == "text"


@pytest.mark.asyncio
async def test_butler_service_voice_input_mode_sets_metadata() -> None:
    """run() con input_mode='voice' crea HumanMessage con metadata input_mode=voice."""
    from app.features.butler.graph.graph import reset_compiled_graph

    reset_compiled_graph()
    mock_state = {
        "message": "test",
        "intent": "speak",
        "doc_type": "none",
        "retrieved_docs": [],
        "messages": [],
        "input_mode": "voice",
        "actions": [{"type": "speak", "message": "ok"}],
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_state)
    with patch(
        "app.features.butler.service.get_compiled_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        from app.features.butler.service import ButlerService

        await ButlerService().run("test transcrito", input_mode="voice")

    state_input = mock_graph.ainvoke.call_args[0][0]
    human_msg = state_input["messages"][0]
    assert human_msg.metadata.get("input_mode") == "voice"
    assert state_input["input_mode"] == "voice"


def test_ask_voice_requires_auth(client: TestClient) -> None:
    """POST /api/butler/ask-voice sin token devuelve 401."""
    response = client.post(
        "/api/butler/ask-voice",
        files={"audio": ("test.wav", b"fake", "audio/wav")},
    )
    assert response.status_code == 401


def test_ask_voice_with_valid_audio_returns_actions(client: TestClient) -> None:
    """POST /api/butler/ask-voice con audio válido (mockeado) devuelve 200."""
    tokens = login(client)
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "message": "como fabrico una espada",
            "intent": "question",
            "doc_type": "item",
            "retrieved_docs": [],
            "messages": [],
            "input_mode": "voice",
            "actions": _SPEAK_RESPONSE,
        },
    )
    with (
        patch(
            "app.features.butler.service.get_compiled_graph",
            new=AsyncMock(return_value=mock_graph),
        ),
        patch(
            "app.features.butler.router.transcribe_audio",
            return_value="como fabrico una espada",
        ),
    ):
        response = client.post(
            "/api/butler/ask-voice",
            files={"audio": ("test.wav", b"fake_wav_bytes", "audio/wav")},
            headers=auth_headers(tokens["access_token"]),
        )

    assert response.status_code == 200
    actions = response.json()
    assert isinstance(actions, list)
    assert actions[0]["type"] == "speak"


def test_ask_voice_empty_audio_returns_422(client: TestClient) -> None:
    """POST /api/butler/ask-voice con audio vacío devuelve 422."""
    tokens = login(client)
    response = client.post(
        "/api/butler/ask-voice",
        files={"audio": ("empty.wav", b"", "audio/wav")},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422


def test_ask_voice_passes_session_id(client: TestClient) -> None:
    """session_id en ask-voice se propaga al grafo como thread_id."""
    tokens = login(client)
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "message": "test",
            "intent": "speak",
            "doc_type": "none",
            "retrieved_docs": [],
            "messages": [],
            "input_mode": "voice",
            "actions": _SPEAK_RESPONSE,
        },
    )
    with (
        patch(
            "app.features.butler.service.get_compiled_graph",
            new=AsyncMock(return_value=mock_graph),
        ),
        patch(
            "app.features.butler.router.transcribe_audio",
            return_value="hola",
        ),
    ):
        client.post(
            "/api/butler/ask-voice",
            data={"session_id": "player-voice-session"},
            files={"audio": ("test.wav", b"fake", "audio/wav")},
            headers=auth_headers(tokens["access_token"]),
        )

    _, call_kwargs = mock_graph.ainvoke.call_args
    thread_id = call_kwargs.get("config", {}).get("configurable", {}).get("thread_id")
    assert thread_id == "player-voice-session"


def test_ask_voice_transcription_uses_asyncio_to_thread(client: TestClient) -> None:
    """La transcripción STT se delega a asyncio.to_thread (no bloquea el event loop)."""
    tokens = login(client)
    with (
        patch(
            "app.features.butler.service.ButlerService.run",
            new_callable=AsyncMock,
            return_value=[
                type(
                    "BA",
                    (),
                    {"type": "speak", "message": "ok", "x": None, "y": None, "z": None},
                )(),
            ],
        ),
        patch(
            "asyncio.to_thread",
            new_callable=AsyncMock,
            return_value="transcripción mockeada",
        ) as mock_to_thread,
    ):
        response = client.post(
            "/api/butler/ask-voice",
            files={"audio": ("test.wav", b"fake_bytes", "audio/wav")},
            headers=auth_headers(tokens["access_token"]),
        )

    assert response.status_code == 200
    mock_to_thread.assert_called_once()
    # El primer argumento debe ser la función de transcripción
    from app.features.butler.stt import transcribe_audio as _transcribe

    assert mock_to_thread.call_args[0][0] is _transcribe
