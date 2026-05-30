# MinecraftButlerAI — Backend

Backend FastAPI para un agente LLM que actúa como mayordomo en Minecraft. Recibe peticiones en lenguaje natural (texto o voz), decide qué acción ejecutar y la delega al cliente Java que controla el juego.

## Qué hace este proyecto

El backend es el **cerebro del agente**: no ejecuta acciones en Minecraft directamente, sino que:

1. Recibe la petición del jugador (texto o, eventualmente, audio via STT)
2. Procesa la intención con un grafo **LangGraph** (orquestación de pasos: planificación, retrieval, ejecución)
3. Decide si necesita consultar una base de conocimiento (**RAG**) para dar contexto al LLM
4. Selecciona la acción final (`move_to_position`, `speak`, `craft`, …)
5. Devuelve la acción estructurada al cliente Java que la ejecuta en el juego
6. Registra trazas en **LangSmith** para observabilidad y depuración

## Stack

| Capa | Tecnología |
|---|---|
| API | FastAPI + SQLAlchemy async + Alembic + PostgreSQL |
| Autenticación | JWT (access 15 min) + refresh token (cookie HTTP-only) |
| Agente LLM | LangChain + LangGraph |
| Retrieval | RAG (pendiente de implementar) |
| Voz | STT (pendiente de implementar) |
| Observabilidad | LangSmith |
| Seguridad | SlowAPI (rate limiting), account lockout, argon2 |
| Gestor deps | uv |

## Inicio rápido (Docker)

```powershell
cp .example.env .env   # rellenar variables
docker compose up --build
```

API disponible en `http://localhost:8000/api/documentation`
Credenciales por defecto: `admin` / `ChangeMe123!`

## Desarrollo local

Requiere [uv](https://docs.astral.sh/uv/getting-started/installation/) y PostgreSQL.

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

## Tests

```powershell
uv run pytest -q
```

Requiere PostgreSQL accesible en `127.0.0.1:5432`. Ajusta `TEST_DATABASE_ADMIN_URL` en `.env` si es necesario.

## Estructura

```
app/
├── core/          # settings, DB, lifespan, limiter, migraciones
└── features/
    ├── auth/      # JWT, refresh tokens, lockout, sesiones
    ├── users/     # gestión de cuentas
    ├── roles/     # gestión de roles (admin, user, custom)
    ├── health/    # health check
    └── butler/    # agente LLM → acción Minecraft (LangGraph)
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
```

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
| `SECRET_KEY` | Clave para firmar JWT (≥ 32 chars en producción) |
| `DATABASE_URL` | URL de conexión a PostgreSQL |
| `ADMIN_USERNAME` | Usuario administrador inicial |
| `ADMIN_PASSWORD` | Contraseña del administrador inicial |
| `ANTHROPIC_API_KEY` | **Obligatorio** — clave de la API de Anthropic (Claude) |
| `LANGSMITH_API_KEY` | Opcional — clave de LangSmith para tracing |
| `LANGSMITH_PROJECT` | Nombre del proyecto en LangSmith (default: `minecraftbutlerai`) |
| `LANGSMITH_ENDPOINT` | Endpoint de LangSmith (p. ej. `https://eu.api.smith.langchain.com`) |
| `LANGCHAIN_TRACING_V2` | `true` para activar tracing en LangSmith |
| `SSL_VERIFY` | `false` en entornos con certificados corporativos/proxy |

## Dependencias

```powershell
uv add <paquete>         # producción
uv add --dev <paquete>   # solo desarrollo
uv lock                  # regenerar uv.lock (commitear)
```
