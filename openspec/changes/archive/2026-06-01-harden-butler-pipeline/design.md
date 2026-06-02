## Context

Cuatro mejoras independientes al slice `butler`, todas de bajo riesgo y sin cambios de modelo de datos. Se agrupan porque comparten objetivo (robustez + coste + tokens del pipeline butler) y tamaño (cada una es un cambio pequeño y localizado).

Estado actual relevante:
- `router.py::ask_voice` llama `transcribe_audio(audio_bytes)` de forma síncrona (bloquea el event loop).
- `router.py::ask` y `ask_voice` no tienen `@limiter.limit` (los de auth sí).
- `llm/factory.py::get_llm` construye un cliente nuevo cada llamada; `get_embedding_model` ya usa `lru_cache`.
- `rag/retriever.py::dense_search` devuelve `top_k` sin filtrar por score.

## Goals / Non-Goals

**Goals:**
- No bloquear el event loop durante la transcripción.
- Proteger el coste de tokens con rate limiting por IP en los endpoints del butler.
- Reutilizar el cliente LLM entre nodos/peticiones.
- Reducir tokens y ruido descartando documentos RAG poco relevantes.

**Non-Goals:**
- Caché de respuestas del LLM (es un change aparte, mayor).
- Cambiar el modelo de embeddings o la estrategia de retrieval (sigue dense-only).
- Streaming, resiliencia/retry del grafo, o mejoras de `move_action` (changes futuros).

## Decisions

### D1 — STT no bloqueante con `asyncio.to_thread`
En `ask_voice`, envolver la llamada: `transcript = await asyncio.to_thread(transcribe_audio, audio_bytes)`. `transcribe_audio` sigue siendo síncrona (no se toca); el wrapper la mueve a un thread del pool por defecto.

**Alternativa descartada:** convertir `transcribe_audio` en async. faster-whisper es CPU-bound; marcarla `async` no la haría no bloqueante. `to_thread` es la herramienta correcta para CPU-bound síncrono en un endpoint async.

### D2 — Rate limiting en endpoints del butler
Añadir `@limiter.limit("20/minute")` a `ask` y `ask_voice`. SlowAPI exige `request: Request` en la firma del endpoint decorado. El límite es permisivo (uso normal de un jugador no lo alcanza) pero corta bucles de reintento o abuso.

**Alternativa descartada:** límite más agresivo (p. ej. 5/min). Penalizaría ráfagas legítimas (varias preguntas seguidas). 20/min protege el coste sin molestar.

### D3 — `get_llm` cacheado por rol
Aplicar `@lru_cache(maxsize=None)` (o `maxsize=4`) a `get_llm`, con `role` como clave. Como `role` es el único argumento y es hashable (`Literal`), `lru_cache` funciona directamente.

**Cuidado:** `lru_cache` cachea el resultado para la vida del proceso. Si en el futuro se quiere recargar config en caliente, habrá que exponer un `.cache_clear()` (igual que ya pasa con `get_embedding_model` y `get_settings`). En tests, limpiar la caché si se mockea el provider.

**Alternativa descartada:** memoizar en un dict global manual. `lru_cache` es idiomático y consistente con `get_embedding_model`.

### D4 — Umbral de score en RAG
Nuevo setting `qdrant_score_threshold: float = 0.0` (default 0.0 = comportamiento actual, no rompe nada). `dense_search` filtra `point.score >= threshold` al construir la lista de `RetrievedDoc`. El umbral efectivo (p. ej. 0.3) se fija por entorno tras observar los scores reales; arrancar en 0.0 hace el cambio seguro por defecto.

`RetrieverConfig` añade `score_threshold` para mantener la config inyectable en tests.

**Alternativa descartada:** umbral hardcoded en el código. Romper el patrón config-driven del proyecto; un setting es consistente y permite tuning sin redeploy de código.

## Risks / Trade-offs

- **Umbral mal calibrado descarta documentos válidos** → mitigado con default 0.0 (no filtra). El valor productivo se elige tras inspeccionar scores; documentar el rango observado.
- **`lru_cache` en `get_llm` retiene config obsoleta tras cambiar env vars** → mismo patrón ya aceptado en el proyecto (`get_settings`, `get_embedding_model`); los tests que cambian provider deben llamar `get_llm.cache_clear()`.
- **Rate limit 429 inesperado en tests de integración** → los tests existentes del butler hacen pocas llamadas; 20/min no se alcanza. Si algún test envía ráfagas, ajustar o resetear el limiter como ya se hace en `tests/test_api.py`.
- **`to_thread` usa el threadpool por defecto (limitado)** → suficiente para uso local single-user; en alta concurrencia se podría dimensionar, fuera de alcance aquí.
