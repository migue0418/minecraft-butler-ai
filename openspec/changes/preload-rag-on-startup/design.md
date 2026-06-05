## Context

`app/core/lifespan.py` ya ejecuta, en orden, durante el arranque: bypass SSL (si
`ssl_verify=False`), configuración de tracing, init de BD + seed admin, compilación del grafo
(`get_compiled_graph()`) y precalentamiento de Whisper (`get_whisper_model()`). El RAG, en
cambio, se carga perezosamente: `get_embedding_model()` y `get_qdrant_client()`
(ambos en `app/features/butler/`) usan `lru_cache` y se materializan en la primera llamada a
`retrieve_context`. La primera consulta `question` paga así ~150 MB de carga de modelo más la
primera inferencia y la apertura de conexión a Qdrant.

## Goals / Non-Goals

**Goals:**
- Eliminar el cold-start del RAG en la primera petición, precalentándolo en el `lifespan`.
- Mantener el arranque resiliente: si el calentamiento falla (Qdrant caído, modelo no
  descargable), registrar `warning` y arrancar igualmente.
- Reutilizar el bypass SSL y la carga offline ya existentes (entornos con proxy).

**Non-Goals:**
- No cambiar el pipeline de recuperación ni la configuración de Qdrant/embeddings.
- No precargar el corpus ni reindexar (eso es el script de ingesta, fuera de alcance).
- No introducir healthchecks nuevos ni readiness endpoints.

## Decisions

### Decisión 1: Precalentar tras compilar el grafo, reutilizando los factories
Añadir el bloque de calentamiento en `lifespan()` justo después de `get_compiled_graph()` y
`get_whisper_model()`. Llamar a `get_embedding_model()` y ejecutar `embed_query("...")` con un
texto corto para forzar la carga del modelo y su primera inferencia (la inferencia inicial es
parte del coste de cold-start, no solo la carga de pesos). Inicializar `get_qdrant_client()`.

**Por qué reutilizar los factories:** `get_embedding_model()` ya aplica el bypass SSL/offline
(`_apply_hf_ssl_bypass_if_needed`, `local_files_only`) y `lru_cache` garantiza que la misma
instancia caliente se reutiliza en `retrieve_context`. No se duplica lógica.

### Decisión 2: Calentamiento tolerante a fallos (no bloquea el arranque)
Envolver el bloque en `try/except Exception` con `logging.warning`. Si Qdrant no está disponible
o el modelo no puede cargarse, el servidor arranca y el RAG vuelve a su carga perezosa en la
primera petición. Esto evita acoplar la disponibilidad del servicio a la de Qdrant en startup,
coherente con un arranque robusto. El precalentamiento es una optimización, no un requisito duro.

**Alternativa considerada:** fallar el arranque si Qdrant no responde. Descartada: haría el
backend indisponible por un servicio que hoy es opcional en el arranque y degradaría la
resiliencia sin beneficio claro.

### Decisión 3: Comprobación ligera de Qdrant opcional
Tras crear el cliente, una llamada barata (p. ej. existencia/conteo de la colección) abre la
conexión y valida conectividad. Si se incluye, va dentro del mismo `try/except`. Es opcional y
de bajo coste; su único fin es abrir el socket y detectar problemas pronto (en el log).

### Capas afectadas (backend)
- **core/lifespan.py** — único archivo modificado: bloque de precalentamiento del RAG.
- **router / service / repository / models** — sin cambios.
- **Migraciones Alembic** — ninguna.

> Nota de proceso: por el tamaño trivial del cambio (un bloque en `lifespan.py` análogo al de
> Whisper), el plan técnico a nivel de archivos se documenta de forma breve en
> `.claude/doc/preload-rag-on-startup/backend.md` antes de `/opsx:apply`.

## Risks / Trade-offs

- **[Mayor tiempo de arranque]** → Aceptado y deseado: se paga la carga una vez al arrancar en
  lugar de penalizar la primera petición; idéntico trade-off que Whisper. El embed de
  calentamiento es de un único texto corto (coste despreciable frente a la carga del modelo).
- **[Qdrant/HuggingFace no disponibles en startup]** → `try/except` + `warning`; el arranque no
  se rompe y el RAG cae a carga perezosa.
- **[Doble carga si algo no respeta `lru_cache`]** → Se usan exclusivamente los factories
  cacheados (`get_embedding_model`, `get_qdrant_client`), garantizando una sola instancia.
