# Estándares de backend

FastAPI con SQLAlchemy **async**, arquitectura por slices. Esta guía describe los patrones reales del
template; imítalos al añadir o modificar features.

## Stack

- Python ≥ 3.12, FastAPI, SQLAlchemy async + asyncpg, Alembic, Pydantic Settings, JWT (`pyjwt`),
  `pwdlib[argon2]`, `python-multipart`, `slowapi`. Gestor de dependencias: **uv** (no pip).
- Tests: **pytest** + `httpx` (en `tests/`). **Nunca SQLite** en tests: usa PostgreSQL.

## Arquitectura por slice (`app/features/<feature>/`)

```
router.py       # endpoints HTTP delgados
schemas.py      # modelos Pydantic (request/response)
service.py      # casos de uso y reglas de negocio
repository.py   # acceso a datos con AsyncSession
models.py       # modelos SQLAlchemy (si el slice persiste datos)
```

Núcleo en `app/core/`: `settings.py`, `database.py`, `lifespan.py`, `migrations.py`, `limiter.py`.

### `router.py` — delgado

```python
router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("", response_model=list[UserResponse])
async def list_users(
    _: object = Depends(require_roles("admin")),
    service: UsersService = Depends(get_users_service),
) -> list[UserResponse]:
    return await service.list_users()
```

- Solo orquesta: dependencias (`Depends`), llamada al service, `response_model`.
- Autorización con `require_roles("admin")` o `get_authenticated_user` (de `app.features.auth.dependencies`).
- Sin lógica de negocio ni queries.

### `service.py` — reglas de negocio

```python
class UsersService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users_repository = UsersRepository(session)

    async def create_user(self, payload: CreateUserRequest) -> UserDetailResponse:
        if await self.users_repository.get_user_by_username_without_roles(payload.username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese username")
        user = await self.users_repository.create_user(...)
        await self.session.commit()
        return self._serialize_user_detail(user)

def get_users_service(session: AsyncSession = Depends(get_session)) -> UsersService:
    return UsersService(session)
```

- Clase `XxxService(session)` que compone los repositories que necesite.
- Hace `await self.session.commit()` (el repository hace `flush`/`refresh`, no commit).
- Errores de negocio → `HTTPException` con `detail` en español y el status adecuado.
- Factory `get_xxx_service(session=Depends(get_session))` para inyectar en el router.

### `repository.py` — acceso a datos

```python
class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).options(selectinload(User.roles)).where(User.id == user_id),
        )
        return result.scalar_one_or_none()
```

- Solo `AsyncSession` y APIs async. Queries con `select(...)`, `selectinload` para relaciones.
- Sin lógica de negocio ni `HTTPException`.

### `models.py`

- Heredan de `app.core.database.Base` (`DeclarativeBase`).
- **Todo modelo nuevo debe importarse** en `app.core.database.import_model_modules()` (si no, Alembic/metadata no lo ven).

## Reglas transversales

- Endpoints SIEMPRE bajo `/api/...`.
- **Registrar routers nuevos** en `app/main.py`.
- **Cambios de schema ⇒ migración Alembic** en `alembic/versions/`. Las migraciones se ejecutan
  en el arranque (`init_database` → `run_migrations`).
- Settings vía `app.core.settings.get_settings()`. No leer variables de entorno desde código de dominio.
- Sesiones: usa la dependencia `get_session`; para scripts/seed, `session_scope()`.

## Tests

- pytest en `tests/`, API con `httpx`. Cubre happy path y errores (401/403, 404, 409, 422).
- **Nunca SQLite**: los tests corren contra PostgreSQL (ver `docs/verification-guide.md`).
- No mockear la base de datos para tests de integración de endpoints.

## Seguridad

- Passwords con `pwdlib[argon2]` (`hash_password`/`verify_password` en `app.features.auth.security`).
- JWT para acceso; refresh tokens revocables (ver slice `auth`). Al desactivar/borrar usuario, revoca sus refresh tokens.
- Rate limiting con SlowAPI (`app/core/limiter.py`). Endpoints sensibles usan `@limiter.limit("N/period")`.
- Nunca commitear secretos; configúralos vía `Settings`/`.env` (ver `.example.env`).
