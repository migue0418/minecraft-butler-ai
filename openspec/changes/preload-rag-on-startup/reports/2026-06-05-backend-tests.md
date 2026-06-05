# Informe de tests y verificación — preload-rag-on-startup

Fecha: 2026-06-05
Rama: `feature/preload-rag-on-startup` (desde `main` con el PR #12 ya mergeado)

## Alcance
Precalentamiento del RAG (modelo de embeddings + cliente Qdrant) en el `lifespan`, para evitar
cold-start en la primera petición con recuperación. Solo toca `app/core/lifespan.py`. Sin BD.

## Estado de la BD
**Sin mutación de datos.** Sin modelos ni migraciones. No procede baseline ni restauración.

## Tests unitarios (TDD)
- `test_preload_rag_warms_embedding_and_qdrant`: `_preload_rag()` invoca `get_embedding_model()`,
  fuerza `embed_query` (primera inferencia) e inicializa `get_qdrant_client()`.
  Pre-implementación: ROJO (`_preload_rag` no existía). Post: verde.
- `test_preload_rag_swallows_errors`: si el precalentamiento lanza (Qdrant caído), `_preload_rag()`
  no propaga y registra `warning`. Pre: ROJO. Post: verde.

Suite completa:
```
uv run pytest -q
→ 130 passed, 8 warnings   (8 warnings preexistentes de SlowAPI)
```
El fixture `build_client` de `tests/test_api.py` parchea `app.core.lifespan._preload_rag` para no
cargar el modelo real (~150MB) ni conectar a Qdrant durante el lifespan de los tests.

## Verificación de arranque en vivo (EL AGENTE LO EJECUTA)

### Precalentamiento OK (Qdrant disponible) — puerto 8012
- Log de arranque muestra la carga del modelo de embeddings: `Loading weights: 100% 199/199`.
- Sin warning de precalentamiento → embeddings + Qdrant precalentados antes de servir.
- Primera pregunta RAG (`POST /api/butler/ask`, "Que dropea un creeper?"): **7.1s**, dominada por
  las dos llamadas a Anthropic (clasificador Haiku + respondedor Sonnet) y la query a Qdrant; ya
  **no** incluye la carga del modelo (ocurrió en el arranque).

### Arranque resiliente (Qdrant caído) — puerto 8013, `QDRANT_URL=http://127.0.0.1:6999`
- El servidor **arranca igualmente** (docs `200`), sin crash.
- Log: `No se pudo precalentar el RAG en el arranque: [WinError 10061] ... conexión denegada`.
- Confirma el camino tolerante a fallos: warning + arranque completo (el RAG caería a carga
  perezosa en la primera petición).

## Conclusión
- Precalentamiento del RAG operativo: el modelo se carga en el arranque (verificado por log).
- Arranque resiliente ante Qdrant no disponible (verificado en vivo + test unitario).
- Suite completa en verde (130), sin mutación de BD.
