import asyncio
import os
import re
import uuid
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager

import asyncpg
import pytest
from app.core.database import close_database
from app.core.datetime import utcnow
from app.core.settings import get_settings
from app.features.auth.security import hash_password
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL, make_url

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
    connection = await _connect_to_database(database_url)
    try:
        await connection.execute(
            """
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """,
        )
        await connection.execute(
            "CREATE UNIQUE INDEX ix_users_username ON users (username)",
        )
        await connection.execute(
            """
            CREATE TABLE auth_refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                token_hash VARCHAR(64) NOT NULL UNIQUE,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP NULL,
                user_agent VARCHAR(255) NULL,
                remember_me BOOLEAN NOT NULL
            )
            """,
        )
        await connection.execute(
            """
            CREATE UNIQUE INDEX ix_auth_refresh_tokens_token_hash
            ON auth_refresh_tokens (token_hash)
            """,
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
    get_settings.cache_clear()

    if initializer is not None:
        asyncio.run(initializer(database_url))

    try:
        app = create_app()
        with TestClient(app) as client:
            yield client
    finally:
        asyncio.run(close_database())
        get_settings.cache_clear()
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

