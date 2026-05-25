# FastAPI Template

Plantilla de proyecto full-stack lista para usar. Incluye autenticación JWT, gestión de usuarios y roles, y una interfaz React moderna.

## Stack

- **Backend**: FastAPI, SQLAlchemy async, Alembic, PostgreSQL, uv
- **Auth**: JWT (access token 15 min) + refresh token en cookie HTTP-only
- **Deploy**: Docker Compose con Caddy como reverse proxy

## Inicio rápido (Docker)

```powershell
# Copiar y rellenar variables de entorno
cp .example.env .env

docker compose up --build
```

App disponible en `http://localhost:8000`  
Credenciales por defecto: `admin` / `ChangeMe123!`

## Desarrollo local

Requiere [uv](https://docs.astral.sh/uv/getting-started/installation/) instalado.

```powershell
# Backend (uv crea .venv e instala todo, incluidas deps de dev)
uv sync
uv run uvicorn app.main:app --reload

- Backend en `http://127.0.0.1:8000`

## Tests

```powershell
uv run pytest -q
```

Requiere PostgreSQL accesible en `127.0.0.1:5432`. Configura `TEST_DATABASE_ADMIN_URL` en `.env` si es necesario.

## Dependencias

Las dependencias se gestionan con `uv` y `pyproject.toml`:

- **Producción** (`[project.dependencies]`): instaladas en Docker con `uv sync --no-dev`
- **Desarrollo** (`[dependency-groups] dev`): `pytest`, `httpx` — solo en local, nunca en la imagen Docker

```powershell
uv add <paquete>             # añadir dependencia de producción
uv add --dev <paquete>       # añadir dependencia de desarrollo
uv lock                      # regenerar uv.lock (commitear)
```

## Añadir nuevas features

Sigue la arquitectura por slice:

```
app/features/<feature>/
    router.py       # endpoints FastAPI
    schemas.py      # modelos Pydantic
    service.py      # lógica de negocio
    repository.py   # acceso a datos
    models.py       # modelos SQLAlchemy (si hay tabla nueva)

Cuando añadas un modelo SQLAlchemy nuevo, impórtalo en `app/core/database.py::import_model_modules` y genera la migración:

```powershell
uv run alembic revision --autogenerate -m "descripcion"
uv run alembic upgrade head
```

## Variables de entorno relevantes

| Variable | Descripción |
|---|---|
| `APP_NAME` | Nombre de la aplicación |
| `ENVIRONMENT` | `development` / `production` / `test` |
| `SECRET_KEY` | Clave para firmar JWT (cambiar en producción) |
| `DATABASE_URL` | URL de conexión a PostgreSQL |
| `ADMIN_USERNAME` | Usuario administrador inicial |
| `ADMIN_PASSWORD` | Contraseña del administrador inicial |
