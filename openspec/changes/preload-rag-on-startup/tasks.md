## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Crear y cambiar a la rama `feature/preload-rag-on-startup` **desde `main`** (no desde la rama del PR anterior)
- [x] 0.2 Plan técnico breve en `.claude/doc/preload-rag-on-startup/backend.md` (cambio trivial; `/opsx:apply` debe leerlo)

## 1. Backend: tests del precalentamiento (TDD)

- [x] 1.1 Test: el `lifespan` invoca `get_embedding_model()` (con un embed de calentamiento) y `get_qdrant_client()` durante el arranque (mockear ambos factories y `app.state`/dependencias pesadas; verificar que se llaman antes del `yield`)
- [x] 1.2 Test: si el precalentamiento del RAG lanza una excepción (p. ej. Qdrant caído), el `lifespan` **no** propaga el error y el arranque completa (se registra `warning`)
- [x] 1.3 Ejecutar los tests y confirmar que fallan (rojo) contra el `lifespan` actual

## 2. Backend: implementación (core/lifespan)

- [x] 2.1 En `app/core/lifespan.py`: tras `get_compiled_graph()` y `get_whisper_model()`, añadir bloque de precalentamiento del RAG: `get_embedding_model()` + `embed_query("<texto corto>")` e inicialización de `get_qdrant_client()` (opcional comprobación ligera de la colección)
- [x] 2.2 Envolver el bloque en `try/except Exception` con `logging.warning` para no romper el arranque si el RAG no está disponible
- [x] 2.3 Verificar que el bloque va **después** de `_configure_ssl_bypass()` y reutiliza los factories cacheados (sin duplicar lógica SSL/offline)

## 3. Backend: tests y estado de BD (OBLIGATORIO)

- [x] 3.1 `uv run pytest -q` en verde (suite completa). El cambio NO muta la BD; sin baseline ni restauración. Dejar constancia en el informe
- [x] 3.2 Guardar informe en `openspec/changes/preload-rag-on-startup/reports/YYYY-MM-DD-backend-tests.md`

## 4. Backend: verificación de arranque (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 4.1 Arrancar el backend con servicios disponibles y confirmar en los logs que el RAG se precalienta en el arranque (sin error)
- [x] 4.2 Medir/observar que la **primera** petición a `/api/butler/ask-stream` con una pregunta `question` ya no paga la carga del modelo (comparar latencia de la primera consulta vs. el comportamiento previo, o verificar por logs que el modelo ya estaba cargado)
- [x] 4.3 Caso resiliente: arrancar con Qdrant detenido y confirmar que el servidor arranca con `warning` y sin crash. Restaurar Qdrant al terminar
- [x] 4.4 Documentar observaciones en el informe del cambio

## 5. Cierre (OBLIGATORIO)

- [x] 5.1 Actualizar documentación técnica afectada en `docs/` y la nota de arranque/observabilidad en `ARCHITECTURE.md` si procede
- [x] 5.2 Generar la descripción del PR con la skill `write-pr-report` y abrir el PR con `gh pr create`
