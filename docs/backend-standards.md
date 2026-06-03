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

## STT — Speech-to-Text (`app/features/butler/stt/`)

El butler acepta audio de voz además de texto. La transcripción corre localmente con `faster-whisper` (sin API externa, sin coste por petición).

### Endpoint

```
POST /api/butler/ask-voice   (multipart/form-data)
  audio: UploadFile           — fichero de audio (wav, mp3, webm, ogg…)
  session_id: str | None      — mismo que en /ask; opcional
  world_context: str | None   — JSON serializado de WorldContextDTO; opcional
```

Responde igual que `POST /api/butler/ask`: `list[ButlerAction]`.

### Arquitectura

- `app/features/butler/stt/service.py`: `WhisperModel` singleton + `transcribe_audio(bytes) -> str`.
- Modelo cargado una vez en lifespan (`get_whisper_model()`), cero cold-start en la primera petición de voz.
- `compute_type="int8"` en CPU: ~2× más rápido y mitad de memoria vs float32.
- La transcripción es CPU-bound y se ejecuta fuera del event loop: `await asyncio.to_thread(transcribe_audio, audio_bytes)` en `router.py`.
- Audio vacío o sin habla detectada → HTTP 422.
- `ffmpeg` requerido en el contenedor Docker para decodificar formatos distintos de WAV crudo.

### Diferenciación en historial

`HumanMessage.metadata={"input_mode": "voice"}` vs `{"input_mode": "text"}` — persiste en Redis junto con el historial multi-turn, permitiendo distinguir el origen de cada turno.

### Settings

| Variable | Default | Descripción |
|---|---|---|
| `WHISPER_MODEL` | `base` | Tamaño del modelo: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` o `cuda` |

### Tests

Los tests usan `MagicMock()` como singleton del modelo — sin descarga real. Ver `tests/features/butler/test_stt_service.py`.

## World Context (`app/features/butler/`)

El butler acepta contexto del mundo del jugador para responder preguntas sobre su estado actual (inventario, cofres, animales cercanos, cultivos).

### Contrato

`POST /api/butler/ask` acepta `world_context: WorldContextDTO | None` en el body JSON:

```json
{
  "message": "¿tengo hierro suficiente?",
  "world_context": {
    "player": {"x": 100, "y": 64, "z": -50, "inventory": [{"item": "minecraft:iron_ingot", "count": 5}]},
    "chests": [{"name": "materiales", "items": [...]}],
    "nearby": {
      "animals": [{"type": "minecraft:cow", "count": 3}],
      "monsters": [{"type": "minecraft:zombie", "count": 1}],
      "crops": [...]
    }
  }
}
```

`POST /api/butler/ask-voice` acepta `world_context` como form field de texto (JSON serializado).

Ambos campos son **opcionales** — si ausentes, el comportamiento es idéntico al anterior (retrocompatible).

### Selección selectiva de contexto

El nodo `classify_intent` determina si la pregunta requiere contexto del mundo (`needs_world_context: bool`). Solo se inyecta en el prompt cuando es `True` y el contexto está disponible.

- `needs_world_context=True`: "¿tengo hierro?", "¿qué hay en mis cofres?", "¿están listos los cultivos?"
- `needs_world_context=False`: "¿cómo crafteo una espada?", "¿qué dropea una vaca?"

### Formato inyectado

El contexto se formatea como texto compacto (~80 tokens) con `format_world_context()` en `nodes.py`. Se inyecta en el **system prompt** del request actual, **no** en `messages` (el contexto es efímero, no persiste en Redis).

IDs de Minecraft se usan tal cual (`minecraft:iron_ingot`).

## Streaming SSE (`app/features/butler/`)

Los endpoints de streaming devuelven eventos SSE (`text/event-stream`). El jugador ve el echo de su mensaje inmediatamente y las respuestas de Alfred aparecen frase a frase conforme el LLM genera.

### Endpoints

```
POST /api/butler/ask-stream        (mismo body que /ask)
POST /api/butler/ask-voice-stream  (mismo multipart que /ask-voice)
```

### Protocolo de eventos

```
data: {"type":"echo","message":"[Tú] mensaje del jugador"}

data: {"type":"speak","message":"Primera frase de Alfred."}

data: {"type":"speak","message":"Segunda frase."}

data: [DONE]
```

- **Echo**: primer evento, siempre. Para voz: `[Tú] 🎤 <transcript>`.
- **Acciones**: cada chunk de texto llega como evento `speak` separado en cuanto el LLM genera hasta una frontera natural (`.`, `!`, `?`, `\n`).
- **`[DONE]`**: señal de cierre.

### Implementación backend

- `ButlerService.stream()` usa `graph.astream_events(version="v2")` — captura eventos `on_chat_model_stream` del LLM token a token y los vuelca en cada frontera con `_flush_at_boundaries()`.
- `StreamEvent` en `schemas.py` extiende `ButlerAction` con `type="echo"`.
- Rate limiting: `@limiter.limit("20/minute")` igual que los endpoints no-streaming.
- Los endpoints `/ask` y `/ask-voice` no cambian (retrocompatibles).

### Guía para el cliente Java

Ver `openspec/changes/streaming-butler-responses/design.md` — sección "Guía para el cliente Java". Resumen:
- `BodyHandlers.ofLines()` para recibir el stream línea a línea.
- Parsear `data: <JSON>` → `ButlerAction` → `server.execute(() -> ButlerActionExecutor.execute(...))`.
- Case `"echo"` en `ButlerActionExecutor` → mostrar en gris (`§7`).

## Streaming por chunks — `_flush_at_boundaries`

Helper en `service.py` que acumula tokens y devuelve chunks al detectar fronteras naturales. Protección ante reintentos: el buffer se resetea en `on_chain_start` del nodo responder.

## Estilo de respuesta del LLM

Los system prompts en `graph/nodes.py` instruyen al LLM: sin emojis, sin encabezados markdown, sin introducciones ni conclusiones, respuesta mínima necesaria. Preguntas sencillas → 1-2 frases.

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

## Memoria de conversación (`app/features/butler/`)

El butler es multi-turn: persiste el historial de cada sesión en Redis usando el checkpointer oficial de LangGraph.

### Ciclo de vida

- El grafo se compila una vez en el arranque (`lifespan` → `get_compiled_graph()`) con un `AsyncRedisSaver`.
- `AsyncRedisSaver` requiere `redis/redis-stack` (incluye RediSearch); `redis:7-alpine` NO es suficiente.
- El grafo **no se compila a nivel de módulo**. Usar `get_compiled_graph()` (async, cacheado).

### Contrato de API

```json
POST /api/butler/ask
{ "message": "...", "session_id": "player-uuid" }   // session_id opcional
```

- Con `session_id`: el historial se persiste bajo ese id (TTL configurable, default 24h).
- Sin `session_id`: thread efímero, comportamiento stateless (compatible con el contrato anterior).

### Settings de Redis

| Variable de entorno | Default | Descripción |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | URL de conexión |
| `REDIS_SESSION_TTL_SECONDS` | `86400` | TTL de sesión (renew on read) |

### Estado del grafo

`ButlerState` incluye `messages: Annotated[list[AnyMessage], add_messages]`. El reducer `add_messages` acumula el historial entre turnos. `answer_question` construye el prompt del LLM con el historial completo.

### Tests

Los tests usan `MemorySaver` (sin Redis real):
- `build_client()` instala `compile_graph(MemorySaver())` en `_compiled_graph` antes del lifespan.
- Tests async independientes llaman `reset_compiled_graph()` antes de mockear `get_compiled_graph`.

## RAG Pipeline (`app/features/butler/rag/`)

El butler usa un pipeline RAG para responder preguntas sobre Minecraft con fuente de verdad oficial.

### Módulos

```
app/features/butler/rag/
├── __init__.py       # exporta get_retriever()
├── client.py         # QdrantClient singleton (settings.qdrant_url)
├── schemas.py        # RetrievedDoc, RetrieverConfig
└── retriever.py      # dense_search + build_context + get_retriever
```

### Pipeline de recuperación (dense-only)

```
Query (ES) → _encode_dense (embeddings multilingües)
           → Qdrant dense search (named vector "dense", filtro por doc_type, top_k)
           → build_context() → system prompt del LLM
```

- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (multilingual, cross-lingual: queries ES / corpus EN). El modelo denso es **cross-lingual**, así que una pregunta en español recupera correctamente el corpus en inglés.
- **Parent Document Retrieval**: chunks de wiki indexan `parent_content` en payload → el LLM recibe la sección completa.

> **Por qué dense-only** (ver `openspec/changes/fix-rag-multilingual-retrieval`): el corpus es 100% inglés y los usuarios preguntan en español. La rama **sparse BM42** y el **reranker FlashRank** son léxicos solo-inglés: para consultas en español el sparse devuelve ruido y los rerankers de FlashRank no reordenan ES→EN (el "multilingüe" `ms-marco-MultiBERT-L-12` da scores ~0). Ambas etapas degradaban el ranking del denso. El denso multilingüe por sí solo devuelve el documento correcto en top-1 en ES y EN. La colección Qdrant conserva el named vector `sparse` (lo escribe `scripts/ingest.py`), pero **no se usa en consulta**.

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
| `QDRANT_SCORE_THRESHOLD` | `0.0` | Score mínimo de similitud para incluir un doc en el prompt. `0.0` = sin filtrado (retrocompatible). Valor productivo recomendado: `0.3`. |

## Seguridad

- Passwords con `pwdlib[argon2]` (`hash_password`/`verify_password` en `app.features.auth.security`).
- JWT para acceso; refresh tokens revocables (ver slice `auth`). Al desactivar/borrar usuario, revoca sus refresh tokens.
- Rate limiting con SlowAPI (`app/core/limiter.py`). Endpoints sensibles usan `@limiter.limit("N/period")`. Requiere `request: Request` en la firma del endpoint (antes de parámetros con default). Límites actuales: auth 10/min, butler `/ask` y `/ask-voice` 20/min.
- Nunca commitear secretos; configúralos vía `Settings`/`.env` (ver `.example.env`).
