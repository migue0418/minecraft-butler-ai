# CLAUDE.md — MinecraftButlerAI Backend

Fuente de verdad para Claude Code en este repositorio. Léelo antes de actuar.

---

## Proyecto

Backend FastAPI para MinecraftButlerAI. Expone la API REST, gestiona autenticación/autorización con JWT y roles, ejecuta migraciones Alembic y sirve el conjunto de funcionalidades del butler (asistente de Minecraft). Sin frontend propio ni Caddy.

---

## Estructura

```text
/
├── app/
│   ├── core/                  # settings, DB, migraciones, lifespan, limiter
│   ├── features/              # auth, users, roles, health, butler
│   └── main.py
├── alembic/
├── tests/
├── .example.env
└── pyproject.toml
```

---

## Backend

Stack: Python, FastAPI, SQLAlchemy async, asyncpg, Alembic, Pydantic Settings, JWT, pwdlib[argon2], SlowAPI, pytest.

Arquitectura por slice en `app/features/<feature>/`:

```
router.py       # endpoints y dependencias HTTP
schemas.py      # modelos Pydantic
service.py      # casos de uso y reglas de negocio
repository.py   # acceso a datos con AsyncSession
models.py       # modelos SQLAlchemy, si aplica
```

Reglas:

- Mantener routers delgados; la lógica de negocio vive en `service.py`.
- El acceso a DB vive en `repository.py`; no escribir queries complejas en routers.
- Endpoints nuevos bajo `/api/...`.
- Si añades un router, incluirlo en `app/main.py`.
- Si añades un modelo SQLAlchemy, importarlo en `app/core/database.py::import_model_modules`.
- Cambios de schema siempre con migración Alembic en `alembic/versions/`.
- Usar `AsyncSession` y APIs async; no mezclar sesiones sync.
- Usar `Settings` de `app/core/settings.py`; no leer env vars desde código de dominio.

---

## Comandos

Docker:

```powershell
docker compose up --build
```

Backend local (requiere uv):

```powershell
uv sync                                  # crea .venv e instala deps + dev
uv run uvicorn app.main:app --reload
```

Verificación:

```powershell
uv run pytest -q
```

Dependencias backend:

```powershell
uv add <paquete>        # producción
uv add --dev <paquete>  # solo dev/test
uv lock                 # regenerar lock file
```

---

## SDD: OBLIGATORIO al planificar (Plan Mode incluido)

**REGLA CRÍTICA — sin excepciones:** Cuando el usuario exprese intención de planificar, proponer, crear, implementar o diseñar una funcionalidad nueva — ya sea en conversación normal, en Plan Mode o en cualquier otro contexto — el **primer paso siempre es el flujo SDD**:

1. Si la idea necesita refinamiento o hay dudas → invoca `/opsx:explore`
2. Si la idea está clara → invoca directamente `/opsx:propose`

**NO** analices el código, **NO** planifiques directamente, **NO** propongas implementaciones sin haber pasado antes por `/opsx:explore` o `/opsx:propose`. El flujo SDD genera los artefactos (proposal, specs, design, tasks) que son el prerequisito de todo lo demás.

---

## SDD / OpenSpec

Este repo trae un flujo de **Spec-Driven Development** listo para usar. Requiere el CLI de OpenSpec
(`npm i -g @fission-ai/openspec` o `npx @fission-ai/openspec`).

Guía paso a paso con prompts reales: `docs/SDD steps.md`.

Flujo (perfil core):

```
/opsx:explore        # pensar/aclarar una idea (opcional)
/opsx:propose        # crear el cambio + artefactos (proposal, specs, design, tasks)
plan técnico         # agentes backend-developer → .claude/doc/<cambio>/backend.md (OBLIGATORIO)
/opsx:apply          # implementar tareas (el agente también ejecuta las pruebas)
write-pr-report + gh # abrir el PR
/opsx:archive        # fusionar delta specs en openspec/specs/ y archivar
```

- **El plan técnico es obligatorio**: antes de `/opsx:apply` deben existir los planes de los agentes en `.claude/doc/<cambio>/backend.md`, y `apply` debe leerlos.
- Estándares detallados (referencia versionada): `docs/base-standards.md`, `docs/backend-standards.md`, `docs/data-model.md`, `docs/development_guide.md`, `docs/verification-guide.md`, `docs/documentation-standards.md`.
- Contexto del stack inyectado en todos los artefactos: `openspec/config.yaml`.
- Antes de escribir/implementar `tasks.md` se aplica `.claude/rules/openspec-tasks-mandatory-steps.md` (el agente ejecuta las pruebas: `uv run pytest`, curl, Playwright MCP; PR con `gh`).
- Agentes (`.claude/agents/`): `backend-developer` (plan técnico obligatorio), `product-strategy-analyst` (ideación).
- Skills propias: `enrich-us` (refinar user stories de Jira), `write-pr-report` (descripción de PR + `gh`).

---

## NO hacer

- NO instalar dependencias sin confirmación del usuario.
- NO commitear ni imprimir secretos, tokens o passwords.
- NO usar SQLite para tests del backend.
- NO duplicar lógica de negocio.
- NO hacer cambios grandes no relacionados con la petición.
