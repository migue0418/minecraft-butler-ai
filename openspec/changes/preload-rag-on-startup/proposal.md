## Why

La primera pregunta de tipo `question` que llega al butler es lenta: el modelo de embeddings de HuggingFace (~150 MB, `paraphrase-multilingual-MiniLM-L12-v2`) y el cliente Qdrant se cargan **perezosamente** en la primera llamada a `retrieve_context`. El `lifespan` ya precalienta `faster-whisper` y compila el grafo con ese mismo objetivo (cero cold-start), pero el RAG quedó fuera. Replicar ese patrón elimina la latencia de arranque en frío de la primera consulta con recuperación.

## What Changes

- En `app/core/lifespan.py`, tras compilar el grafo y precalentar Whisper, **precalentar el RAG**:
  - Invocar `get_embedding_model()` y ejecutar un **embed de calentamiento** (`embed_query` de un texto corto) para forzar la carga del modelo y su primera inferencia.
  - Inicializar `get_qdrant_client()` para abrir la conexión (opcionalmente una comprobación ligera de la colección).
- Respetar el **bypass SSL** existente (`ssl_verify=False`, proxy corporativo): el calentamiento debe ocurrir después de `_configure_ssl_bypass()` y reutilizar la lógica de carga offline ya presente en el factory.
- **No romper el arranque** si Qdrant/HuggingFace no están disponibles: registrar un `warning` y continuar (el RAG seguirá cargándose perezosamente en la primera petición), coherente con un arranque resiliente.

## Capabilities

### New Capabilities
<!-- Ninguna. -->

### Modified Capabilities
- `rag-pipeline`: se añade una requirement de **precalentamiento en el arranque** del modelo de embeddings y del cliente Qdrant (análoga a la de `voice-stt-input` para Whisper), para evitar latencia por petición en la primera consulta con RAG.

## Impact

- **Slice afectado**: `core` (lifespan) del backend.
  - `app/core/lifespan.py` → añadir el bloque de precalentamiento del RAG.
- **Contrato HTTP**: sin cambios.
- **Datos**: ninguno. Sin modelos SQLAlchemy ni migración Alembic.
- **Dependencias**: ninguna nueva (reutiliza `get_embedding_model` y `get_qdrant_client` existentes).
- **Arranque**: el tiempo de startup aumenta ligeramente (se paga la carga del modelo al arrancar en lugar de en la primera petición); es el trade-off deseado, idéntico al de Whisper.
