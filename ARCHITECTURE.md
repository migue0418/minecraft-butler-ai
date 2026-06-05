# MinecraftButlerAI — Arquitectura y decisiones técnicas

> Documento de referencia para presentar y defender el proyecto. Cada decisión que
> aparece aquí está respaldada por el código real del repositorio, con enlaces a los
> ficheros concretos. Estructura: un **pitch de una página** para la visión rápida y un
> **anexo técnico** por tecnología para las repreguntas. Versión en inglés más abajo.

---

## Diagrama del sistema

```
                     POST /api/butler/ask-stream  (SSE · JWT · rate-limit 20/min)
                                       │
                                       ▼
       ┌───────────────────────────────────────────────────────────────┐
       │                   ButlerService (orquestador)                  │
       │     run() → respuesta completa  |  stream() → frase a frase    │
       └───────────────────────────────────────────────────────────────┘
                                       │  ainvoke / astream_events
                                       ▼
       ┌───────────────────────────────────────────────────────────────┐
       │                  LangGraph  (máquina de estados)               │
       │                                                                │
       │   START ─▶ classify_intent ─┬─(question)─▶ retrieve_context    │
       │                             │                    │             │
       │                             │                    ▼             │
       │                             │              answer_question ─▶ END
       │                             ├─(move)────▶ move_action ────────▶ END
       │                             └─(speak)───▶ speak_action ───────▶ END
       │                                                                │
       │   Estado compartido (ButlerState) + checkpointer Redis (TTL)   │
       └───────────────────────────────────────────────────────────────┘
                 │                        │                      │
                 ▼                        ▼                      ▼
         Haiku 4.5 (clasif.)      Qdrant + embeddings    Sonnet 4.6 (respuesta)
                            paraphrase-multilingual-MiniLM-L12

   Entrada de voz:  audio ─▶ faster-whisper (STT, on-device) ─▶ mismo grafo
```

---

## Pitch (una página)

MinecraftButlerAI es un backend **FastAPI** que da vida a un mayordomo ("Alfred") dentro
de Minecraft: entiende preguntas en lenguaje natural —por texto o por voz—, responde con
conocimiento real del juego y ejecuta acciones en el mundo. No es "una llamada a un LLM":
es una **arquitectura agéntica** donde cada pieza resuelve un problema concreto.

- **Agente con LangGraph.** El butler es una **máquina de estados**: un nodo clasifica la
  intención del usuario y el grafo **enruta** a una de tres ramas —responder una pregunta
  (con RAG), moverse a unas coordenadas, o conversar—. Esto da separación de
  responsabilidades, ramas testeables y enrutado **determinista** (un diccionario, no
  "magia del LLM"). El estado fluye tipado por el grafo y se **persiste en Redis** por
  sesión, lo que da **memoria conversacional multi-turno**.

- **Dos modelos según el trabajo.** La clasificación la hace **Claude Haiku 4.5** (rápido y
  barato) y solo la respuesta final usa **Claude Sonnet 4.6**. Es optimización consciente de
  coste y latencia, no usar el modelo caro para todo. Detrás hay un **factory** que abstrae
  por *rol* ("clasificador"/"respondedor") y por *proveedor* (Anthropic u OpenAI): el código
  pide capacidades, no modelos concretos.

- **RAG denso multilingüe.** El corpus de Minecraft está en **inglés** (PrismarineJS +
  Minecraft Wiki), pero los usuarios preguntan en **español**. Resuelvo el salto de idioma
  con **embeddings cross-lingual** (`paraphrase-multilingual-MiniLM-L12-v2`) y búsqueda
  vectorial densa en **Qdrant**. La historia de ingeniería: empecé con un pipeline híbrido
  (sparse BM42 + reranker FlashRank) y lo **descarté con datos** porque ambos son léxicos y
  solo-inglés, y degradaban el ranking en español. El denso multilingüe solo es superior en
  ambos idiomas.

- **Streaming pensado para voz.** La respuesta se emite por **SSE frase a frase**, no token a
  token, porque el cliente la **sintetiza por voz (TTS)** y un TTS necesita frases completas.
  Da percepción de inmediatez sin trocear el audio.

- **Voz local.** La transcripción usa **faster-whisper** on-device (cuantización `int8`,
  modelo precalentado en el arranque → cero *cold-start*), lo que además **no envía el audio
  del usuario a terceros**.

- **Grounding en el mundo real.** El butler conoce inventario, cofres, mobs y cultivos
  cercanos del jugador. El clasificador decide cuándo la pregunta necesita ese contexto, así
  que distingue "¿cómo crafteo una espada?" (conocimiento → RAG) de "¿tengo hierro?" (estado
  del mundo → contexto inyectado).

- **Producción de verdad.** JWT con roles, rate-limiting (SlowAPI), migraciones Alembic,
  arquitectura por *slices*, settings validados con Pydantic y observabilidad opcional con
  **LangSmith**. No es un notebook.

---

## Anexo técnico

### 1. El agente — LangGraph como máquina de estados

**Qué es.** En lugar de un único prompt que lo intenta todo, el butler se modela como un
**grafo de nodos** ([app/features/butler/graph/graph.py](app/features/butler/graph/graph.py)).
El primer nodo clasifica la intención y, según el resultado, el grafo enruta a una de tres
ramas. El enrutado es un simple diccionario intención→nodo
([routing.py](app/features/butler/graph/routing.py)), por lo que es **determinista y
auditable**.

**Partes.**
- **Nodos** ([nodes.py](app/features/butler/graph/nodes.py)): `classify_intent`,
  `retrieve_context`, `answer_question`, `speak_action`, `move_action`. Cada uno es una
  función async pequeña y testeable por separado.
- **Estado compartido** ([state.py](app/features/butler/graph/state.py)): `ButlerState` es un
  `TypedDict`. El campo `messages` usa el reducer `add_messages` de LangGraph, que **acumula
  el historial automáticamente** → memoria conversacional dentro de la misma ejecución y entre
  turnos.
- **Persistencia** ([graph.py](app/features/butler/graph/graph.py)): el grafo se compila con un
  **checkpointer `AsyncRedisSaver`**. Cada sesión (`thread_id`) guarda su estado en Redis con
  **TTL** (24h por defecto, refrescado en lectura). El grafo se compila una sola vez (singleton
  protegido con `asyncio.Lock`).

**Por qué es útil.** Separación de responsabilidades, ramas testeables, enrutado determinista
y memoria con estado. Es la diferencia entre un **agente con memoria** y un chatbot sin estado.

**Detalle defendible.** La clasificación usa **structured output**
(`with_structured_output(IntentOutput)`): el LLM no devuelve texto libre que haya que parsear,
sino un objeto Pydantic validado con `intent`, `doc_type` y `needs_world_context`. Fiabilidad
en lugar de *prompt-engineering* frágil.

### 2. El RAG — recuperación densa multilingüe

**El problema.** El conocimiento del juego se ingiere en **inglés** (datos de
PrismarineJS/minecraft-data 1.21 + extractos de la Minecraft Wiki), pero las preguntas llegan
en **español**. Hay que recuperar documentos en inglés a partir de consultas en español.

**La solución.** **Embeddings cross-lingual** (`paraphrase-multilingual-MiniLM-L12-v2`, 384
dimensiones): el modelo mapea "¿qué dropea una vaca?" y "Cow drops leather and beef" al mismo
punto del espacio vectorial porque comparten **significado**, no palabras. La búsqueda es densa
por **similitud coseno** en **Qdrant**, con `top_k` y umbral de score configurables
([retriever.py](app/features/butler/rag/retriever.py)).

**La decisión que mejor demuestra criterio.** El diseño original tenía un pipeline híbrido
completo: rama **sparse BM42** + **reranker FlashRank**. Lo **eliminé** porque ambos son
**léxicos y solo-inglés**: con consultas en español, el sparse devolvía ruido y el reranker no
sabía reordenar resultados ES→EN. Conclusión medida y documentada en el código: *el denso
multilingüe solo es superior en español y en inglés*. (Matiz honesto: la ingesta **todavía
indexa** los vectores sparse en Qdrant; quitarlos no compensaba el coste, así que conviven
inertes.)

**Parent Document Retrieval** ([scripts/ingest.py](scripts/ingest.py)). Para las mecánicas de
la wiki indexo **chunks pequeños** (~800 caracteres, que producen embeddings precisos) pero
guardo en el *payload* el **bloque padre grande** (~2000 caracteres). Busco con el chunk pero
al LLM le paso el padre. Resuelve la tensión clásica del RAG: **precisión de recuperación vs.
suficiencia de contexto**.

**Confiar en la semántica sobre el filtro duro** ([nodes.py](app/features/butler/graph/nodes.py)).
El clasificador adivina un `doc_type`, pero deliberadamente **no filtro** por él en Qdrant:
"¿qué ítems dropea una vaca?" se clasifica como `item`, pero el documento correcto es el del
mob `Cow`, y un filtro duro lo excluiría. Dejo que el ranking semántico decida. Demuestra que
entiendo los modos de fallo de mi propio sistema.

```
   Ingesta (scripts/ingest.py)            Consulta (runtime)
   ──────────────────────────             ──────────────────
   PrismarineJS 1.21 ─┐                   "¿qué suelta una vaca?" (ES)
   Minecraft Wiki ────┤                            │
        │             │                            ▼  embed cross-lingual
        ▼             │                     vector denso 384-dim
   chunk 800c ──embed──▶ Qdrant ◀──cosine── (top_k, score_threshold)
   + parent 2000c       (dense +                   │
   en payload           sparse inerte)             ▼  extrae parent_content
                                            build_context() ─▶ prompt de Sonnet
```

### 3. Los LLMs — abstracción por rol y por proveedor

**El patrón factory** ([llm/factory.py](app/features/butler/llm/factory.py)). En vez de
instanciar modelos repartidos por el código, hay `get_llm("classifier")` y
`get_llm("responder")`.

- **Roles semánticos, no modelos hardcoded.** El código pide "el clasificador", no "Haiku". El
  modelo concreto vive en `Settings` y se cambia sin tocar lógica.
- **Provider-agnostic.** Soporta **Anthropic** y **OpenAI** tras la misma interfaz
  `BaseChatModel` de LangChain. Lo mismo con embeddings (**HuggingFace** local vs. OpenAI API).
  No hay *lock-in* de proveedor: argumento de riesgo y de coste.
- **Caché.** `lru_cache` evita recrear clientes y recargar el modelo de embeddings (~150 MB) en
  cada petición. Además, el `lifespan` **precalienta el modelo de embeddings y el cliente Qdrant
  en el arranque** (un embed de calentamiento + comprobación de conectividad), igual que con
  Whisper, para que la primera pregunta con RAG no pague el cold-start. Es tolerante a fallos: si
  Qdrant no está disponible al arrancar, registra un aviso y cae a carga perezosa.

### 4. Streaming — frase a frase por SSE

**Dónde** ([service.py](app/features/butler/service.py)). El servicio consume los eventos de
LangGraph (`astream_events`) y los emite por **Server-Sent Events**. Pero **no** reenvía cada
token: acumula en un buffer y solo emite en **fronteras de frase** (`.!?` o salto de línea).

**Por qué.** El cliente final es un mayordomo que **habla por voz (TTS)**; un TTS no puede
sintetizar medio token, necesita frases completas para sonar natural. Emitir frase a frase da
**percepción de inmediatez** (empieza a hablar antes de terminar de "pensar") sin trocear el
audio. Detalle de robustez: el buffer se **resetea si un nodo reintenta**, para no duplicar
frases.

**Patrón productor/consumidor (para preservar las trazas).** La ejecución del grafo no vive
dentro del generador que consume `StreamingResponse`, sino en una **task de fondo** (productor)
que empuja los `ButlerAction` a una `asyncio.Queue`; el generador SSE solo **drena la cola**.
Esto resuelve un problema real ([langsmith-sdk #817](https://github.com/langchain-ai/langsmith-sdk/issues/817)):
si el grafo corre dentro del generador, FastAPI lo consume en otro contexto y se rompe la
propagación del `contextvar` del run padre de LangSmith, dejando la traza **plana** (solo
input→output). Ejecutar `astream_events` íntegro en una sola task mantiene el contexto estable y
**conserva el árbol de nodos** en la traza. El consumidor cancela la task productora si el cliente
se desconecta (sin tasks huérfanas).

### 5. Voz — STT con faster-whisper

[stt/service.py](app/features/butler/stt/service.py). Transcripción **on-device** con
`faster-whisper`, con autodetección de idioma (ES, EN y +90 más).

- **Cuantización `int8` en CPU**: ~2× más rápido y la mitad de memoria que float32, sin pérdida
  apreciable.
- **Singleton precalentado en el `lifespan`** ([core/lifespan.py](app/core/lifespan.py)): el
  modelo se carga al arrancar → **cero cold-start** en la primera petición de voz.
- **Privacidad**: al ser local, el audio del usuario **no se envía a terceros**.

### 6. Grounding en el mundo real — `world_context`

[nodes.py](app/features/butler/graph/nodes.py). El butler recibe el estado del mundo del
jugador (posición, inventario, cofres, mobs y cultivos cercanos) y lo formatea en texto para el
prompt. El clasificador decide `needs_world_context`, así que el contexto **solo se inyecta
cuando hace falta**: distingue "¿cómo crafteo una espada?" (conocimiento general → RAG) de
"¿tengo hierro?" (estado del mundo → contexto). Esto es *grounding* agéntico real, no un
chatbot genérico.

### 7. Plataforma y operación

- **API**: FastAPI con arquitectura por *slices* (`router`/`schemas`/`service`/`repository`),
  routers delgados y la lógica en servicios.
- **Seguridad**: autenticación **JWT** con roles, hashing **argon2** (pwdlib), validación de
  secretos en producción vía Pydantic Settings.
- **Resiliencia**: **rate-limiting** con SlowAPI (20/min en los endpoints del butler).
- **Datos**: PostgreSQL async (asyncpg/SQLAlchemy) + **Alembic** para migraciones; **Qdrant**
  para vectores; **Redis** para estado conversacional.
- **Observabilidad**: tracing opcional de cada ejecución del grafo con **LangSmith**.

---
---

# MinecraftButlerAI — Architecture & technical decisions

> Reference document to present and defend the project. Every decision here is backed by the
> actual repository code, with links to the concrete files. Structure: a **one-page pitch** for
> the quick overview and a **technical annex** per technology for follow-up questions.

---

## System diagram

```
                     POST /api/butler/ask-stream  (SSE · JWT · rate-limit 20/min)
                                       │
                                       ▼
       ┌───────────────────────────────────────────────────────────────┐
       │                   ButlerService (orchestrator)                 │
       │     run() → full response   |   stream() → sentence by sentence│
       └───────────────────────────────────────────────────────────────┘
                                       │  ainvoke / astream_events
                                       ▼
       ┌───────────────────────────────────────────────────────────────┐
       │                  LangGraph  (state machine)                    │
       │                                                                │
       │   START ─▶ classify_intent ─┬─(question)─▶ retrieve_context    │
       │                             │                    │             │
       │                             │                    ▼             │
       │                             │              answer_question ─▶ END
       │                             ├─(move)────▶ move_action ────────▶ END
       │                             └─(speak)───▶ speak_action ───────▶ END
       │                                                                │
       │   Shared state (ButlerState) + Redis checkpointer (TTL)        │
       └───────────────────────────────────────────────────────────────┘
                 │                        │                      │
                 ▼                        ▼                      ▼
         Haiku 4.5 (classifier)   Qdrant + embeddings    Sonnet 4.6 (responder)
                            paraphrase-multilingual-MiniLM-L12

   Voice input:  audio ─▶ faster-whisper (STT, on-device) ─▶ same graph
```

---

## Pitch (one page)

MinecraftButlerAI is a **FastAPI** backend that brings a butler ("Alfred") to life inside
Minecraft: it understands natural-language questions —by text or by voice—, answers with real
game knowledge and executes in-world actions. It is **not** "a single LLM call": it is an
**agentic architecture** where each piece solves a concrete problem.

- **Agent built on LangGraph.** The butler is a **state machine**: one node classifies the
  user's intent and the graph **routes** to one of three branches —answer a question (with
  RAG), move to coordinates, or chat. This gives separation of concerns, testable branches and
  **deterministic** routing (a dictionary, not "LLM magic"). State flows typed through the
  graph and is **persisted in Redis** per session, providing **multi-turn conversational
  memory**.

- **Two models for two jobs.** Classification runs on **Claude Haiku 4.5** (fast and cheap) and
  only the final answer uses **Claude Sonnet 4.6**. Deliberate cost/latency optimization, not
  using the expensive model for everything. Behind it sits a **factory** that abstracts by
  *role* ("classifier"/"responder") and by *provider* (Anthropic or OpenAI): the code asks for
  capabilities, not concrete models.

- **Dense multilingual RAG.** The Minecraft corpus is in **English** (PrismarineJS + Minecraft
  Wiki), but users ask in **Spanish**. I bridge the language gap with **cross-lingual
  embeddings** (`paraphrase-multilingual-MiniLM-L12-v2`) and dense vector search in **Qdrant**.
  The engineering story: I started with a hybrid pipeline (sparse BM42 + FlashRank reranker)
  and **dropped it with data** because both are lexical and English-only, degrading Spanish
  ranking. Dense multilingual alone is superior in both languages.

- **Streaming designed for voice.** The response is streamed over **SSE sentence by sentence**,
  not token by token, because the client **synthesizes it as speech (TTS)** and a TTS needs
  complete sentences. It gives a sense of immediacy without chopping the audio.

- **Local voice.** Transcription uses **faster-whisper** on-device (`int8` quantization, model
  pre-warmed at startup → zero cold-start), which also means the user's audio is **never sent
  to third parties**.

- **Real-world grounding.** The butler knows the player's nearby inventory, chests, mobs and
  crops. The classifier decides when a question needs that context, so it tells "how do I craft
  a sword?" (knowledge → RAG) apart from "do I have iron?" (world state → injected context).

- **Production-grade.** JWT with roles, rate-limiting (SlowAPI), Alembic migrations, slice
  architecture, Pydantic-validated settings and optional observability with **LangSmith**. Not
  a notebook.

---

## Technical annex

### 1. The agent — LangGraph as a state machine

**What it is.** Instead of one prompt trying to do everything, the butler is modeled as a
**graph of nodes** ([app/features/butler/graph/graph.py](app/features/butler/graph/graph.py)).
The first node classifies intent and, based on the result, the graph routes to one of three
branches. Routing is a plain intent→node dictionary
([routing.py](app/features/butler/graph/routing.py)), so it is **deterministic and auditable**.

**Parts.**
- **Nodes** ([nodes.py](app/features/butler/graph/nodes.py)): `classify_intent`,
  `retrieve_context`, `answer_question`, `speak_action`, `move_action`. Each is a small async
  function, independently testable.
- **Shared state** ([state.py](app/features/butler/graph/state.py)): `ButlerState` is a
  `TypedDict`. Its `messages` field uses LangGraph's `add_messages` reducer, which
  **accumulates history automatically** → conversational memory within a run and across turns.
- **Persistence** ([graph.py](app/features/butler/graph/graph.py)): the graph compiles with an
  **`AsyncRedisSaver` checkpointer**. Each session (`thread_id`) stores its state in Redis with
  a **TTL** (24h default, refreshed on read). The graph compiles once (singleton guarded by an
  `asyncio.Lock`).

**Why it's useful.** Separation of concerns, testable branches, deterministic routing and
stateful memory. The difference between an **agent with memory** and a stateless chatbot.

**Defensible detail.** Classification uses **structured output**
(`with_structured_output(IntentOutput)`): the LLM doesn't return free text to be parsed, but a
validated Pydantic object with `intent`, `doc_type` and `needs_world_context`. Reliability over
fragile prompt engineering.

### 2. The RAG — dense multilingual retrieval

**The problem.** Game knowledge is ingested in **English** (PrismarineJS/minecraft-data 1.21 +
Minecraft Wiki extracts), but questions arrive in **Spanish**. We must retrieve English
documents from Spanish queries.

**The solution.** **Cross-lingual embeddings** (`paraphrase-multilingual-MiniLM-L12-v2`, 384
dims): the model maps "¿qué dropea una vaca?" and "Cow drops leather and beef" to the same
point in vector space because they share **meaning**, not words. Search is dense via **cosine
similarity** in **Qdrant**, with configurable `top_k` and score threshold
([retriever.py](app/features/butler/rag/retriever.py)).

**The decision that best shows judgment.** The original design had a full hybrid pipeline: a
**sparse BM42** branch + a **FlashRank reranker**. I **removed it** because both are **lexical
and English-only**: with Spanish queries the sparse branch returned noise and the reranker
couldn't reorder ES→EN results. Measured conclusion, documented in the code: *dense
multilingual alone is superior in both Spanish and English*. (Honest nuance: ingestion **still
indexes** the sparse vectors in Qdrant; removing them wasn't worth the cost, so they coexist
inert.)

**Parent Document Retrieval** ([scripts/ingest.py](scripts/ingest.py)). For wiki mechanics I
index **small chunks** (~800 chars, which produce precise embeddings) but store the **large
parent block** (~2000 chars) in the payload. I search with the chunk but feed the LLM the
parent. This resolves the classic RAG tension: **retrieval precision vs. context sufficiency**.

**Trusting semantics over hard filters** ([nodes.py](app/features/butler/graph/nodes.py)). The
classifier guesses a `doc_type`, but I deliberately **don't filter** on it in Qdrant: "what
items does a cow drop?" is classified as `item`, yet the right document is the `Cow` mob's, and
a hard filter would exclude it. I let semantic ranking decide. Shows I understand my own
system's failure modes.

```
   Ingestion (scripts/ingest.py)          Query (runtime)
   ──────────────────────────             ───────────────
   PrismarineJS 1.21 ─┐                   "¿qué suelta una vaca?" (ES)
   Minecraft Wiki ────┤                            │
        │             │                            ▼  cross-lingual embed
        ▼             │                     384-dim dense vector
   chunk 800c ──embed──▶ Qdrant ◀──cosine── (top_k, score_threshold)
   + parent 2000c       (dense +                   │
   in payload           sparse inert)              ▼  extract parent_content
                                            build_context() ─▶ Sonnet prompt
```

### 3. The LLMs — abstraction by role and by provider

**The factory pattern** ([llm/factory.py](app/features/butler/llm/factory.py)). Instead of
instantiating models scattered across the code, there's `get_llm("classifier")` and
`get_llm("responder")`.

- **Semantic roles, not hardcoded models.** The code asks for "the classifier", not "Haiku".
  The concrete model lives in `Settings` and changes without touching logic.
- **Provider-agnostic.** Supports **Anthropic** and **OpenAI** behind LangChain's same
  `BaseChatModel` interface. Same for embeddings (**HuggingFace** local vs. OpenAI API). No
  provider lock-in: a risk and cost argument.
- **Caching.** `lru_cache` avoids recreating clients and reloading the ~150 MB embedding model
  on every request. On top of that, the `lifespan` **pre-warms the embedding model and the Qdrant
  client at startup** (a warm-up embed + connectivity check), just like Whisper, so the first RAG
  question doesn't pay the cold-start. It is fault-tolerant: if Qdrant is unavailable at startup,
  it logs a warning and falls back to lazy loading.

### 4. Streaming — sentence by sentence over SSE

**Where** ([service.py](app/features/butler/service.py)). The service consumes LangGraph events
(`astream_events`) and emits them over **Server-Sent Events**. But it does **not** forward each
token: it buffers and only flushes at **sentence boundaries** (`.!?` or newline).

**Why.** The end client is a butler that **speaks (TTS)**; a TTS can't synthesize half a token,
it needs complete sentences to sound natural. Sentence-by-sentence streaming gives a **sense of
immediacy** (it starts talking before it finishes "thinking") without chopping the audio.
Robustness detail: the buffer **resets if a node retries**, to avoid duplicating sentences.

**Producer/consumer pattern (to preserve traces).** Graph execution does not live inside the
generator that `StreamingResponse` consumes, but in a **background task** (producer) that pushes
`ButlerAction`s to an `asyncio.Queue`; the SSE generator only **drains the queue**. This fixes a
real issue ([langsmith-sdk #817](https://github.com/langchain-ai/langsmith-sdk/issues/817)): if
the graph runs inside the generator, FastAPI consumes it in a different context and breaks the
propagation of LangSmith's parent-run `contextvar`, leaving a **flat** trace (input→output only).
Running `astream_events` entirely in a single task keeps the context stable and **preserves the
node tree** in the trace. The consumer cancels the producer task if the client disconnects (no
orphan tasks).

### 5. Voice — STT with faster-whisper

[stt/service.py](app/features/butler/stt/service.py). **On-device** transcription with
`faster-whisper`, with language auto-detection (ES, EN and 90+ more).

- **`int8` quantization on CPU**: ~2× faster and half the memory of float32, with no noticeable
  loss.
- **Pre-warmed singleton in the `lifespan`** ([core/lifespan.py](app/core/lifespan.py)): the
  model loads at startup → **zero cold-start** on the first voice request.
- **Privacy**: being local, the user's audio is **never sent to third parties**.

### 6. Real-world grounding — `world_context`

[nodes.py](app/features/butler/graph/nodes.py). The butler receives the player's world state
(position, inventory, chests, nearby mobs and crops) and formats it as text for the prompt. The
classifier decides `needs_world_context`, so context is **injected only when needed**: it tells
"how do I craft a sword?" (general knowledge → RAG) apart from "do I have iron?" (world state →
context). This is real agentic grounding, not a generic chatbot.

### 7. Platform & operations

- **API**: FastAPI with slice architecture (`router`/`schemas`/`service`/`repository`), thin
  routers and logic in services.
- **Security**: **JWT** auth with roles, **argon2** hashing (pwdlib), production secret
  validation via Pydantic Settings.
- **Resilience**: **rate-limiting** with SlowAPI (20/min on butler endpoints).
- **Data**: async PostgreSQL (asyncpg/SQLAlchemy) + **Alembic** migrations; **Qdrant** for
  vectors; **Redis** for conversational state.
- **Observability**: optional per-run graph tracing with **LangSmith**.
