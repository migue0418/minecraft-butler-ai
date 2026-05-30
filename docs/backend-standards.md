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

## LLM Factory (`app/features/butler/llm/`)

El slice `butler` abstrae la instanciación de LLMs y embeddings detrás de dos factory functions config-driven:

```python
from app.features.butler.llm import get_llm, get_embedding_model

llm = get_llm("classifier")   # → BaseChatModel (Haiku o GPT-4o-mini)
llm = get_llm("responder")    # → BaseChatModel (Sonnet o GPT-4o)
emb = get_embedding_model()   # → Embeddings (HuggingFace o OpenAI)
```

El proveedor y los modelos se leen de `Settings`:

| Variable de entorno | Default | Descripción |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` |
| `CLASSIFIER_MODEL` | `claude-haiku-4-5-20251001` | Modelo rápido para clasificación |
| `RESPONDER_MODEL` | `claude-sonnet-4-6` | Modelo principal de respuesta |
| `EMBEDDING_PROVIDER` | `huggingface` | `huggingface` \| `openai` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Modelo de embeddings |
| `OPENAI_API_KEY` | `` | Obligatoria si `LLM_PROVIDER=openai` |

### Añadir un nuevo proveedor LLM

1. Instalar el paquete langchain del proveedor: `uv add langchain-<provider>`.
2. Añadir un nuevo `if settings.llm_provider == "<provider>":` en `factory.py::get_llm`.
3. Ampliar el `Literal` de `llm_provider` en `Settings`.
4. Añadir la validación de API key en `validate_llm_api_keys`.
5. Escribir tests en `tests/features/butler/test_llm_factory.py`.

## RAG Pipeline (`app/features/butler/rag/`)

El butler usa un pipeline RAG para responder preguntas sobre Minecraft con fuente de verdad oficial.

### Módulos

```
app/features/butler/rag/
├── __init__.py       # exporta get_retriever()
├── client.py         # QdrantClient singleton (settings.qdrant_url)
├── schemas.py        # RetrievedDoc, RetrieverConfig
└── retriever.py      # hybrid_search + rerank + build_context + get_retriever
```

### Pipeline de recuperación

```
Query (ES) → _encode_dense + _encode_sparse
           → Qdrant hybrid search (prefetch dense + sparse, RRF fusion)
           → FlashRank reranking (cross-encoder, top_k docs)
           → build_context() → system prompt del LLM
```

- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (multilingual, queries ES / corpus EN)
- **Sparse**: BM42 via fastembed para keyword matching exacto (nombres de ítems)
- **Reranker**: FlashRank ms-marco-MiniLM (local, sin API key)
- **Parent Document Retrieval**: chunks de wiki indexan `parent_content` en payload → el LLM recibe la sección completa

### Metadata filtering

Cada documento tiene `doc_type: "item" | "mob" | "mechanic"` en el payload. `classify_intent` produce `doc_type` que se usa como filtro en Qdrant antes del vector search.

### Ingesta

```bash
# Primera vez (o tras cambiar el modelo de embeddings)
uv run python scripts/ingest.py

# Reindexar (--force borra y recrea la colección)
uv run python scripts/ingest.py --force
```

Fuentes: `PrismarineJS/minecraft-data 1.21.6` (ítems, mobs) + Minecraft Wiki (mecánicas).

### Añadir un nuevo tipo de documento

1. Añadir función `build_<type>_documents()` en `scripts/ingest.py` siguiendo el patrón existente.
2. Añadir el valor a `doc_type` en el payload.
3. Extender `classify_intent` system prompt para reconocer el nuevo tipo.
4. Re-ejecutar `scripts/ingest.py --force`.

### Variables de entorno Qdrant

| Variable | Default | Descripción |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | URL del servidor Qdrant |
| `QDRANT_COLLECTION` | `minecraft_knowledge` | Nombre de la colección |
| `QDRANT_TOP_K` | `5` | Docs a devolver al LLM |
| `QDRANT_PREFETCH_LIMIT` | `20` | Candidatos antes del reranking |

## Seguridad

- Passwords con `pwdlib[argon2]` (`hash_password`/`verify_password` en `app.features.auth.security`).
- JWT para acceso; refresh tokens revocables (ver slice `auth`). Al desactivar/borrar usuario, revoca sus refresh tokens.
- Rate limiting con SlowAPI (`app/core/limiter.py`). Endpoints sensibles usan `@limiter.limit("N/period")`.
- Nunca commitear secretos; configúralos vía `Settings`/`.env` (ver `.example.env`).
