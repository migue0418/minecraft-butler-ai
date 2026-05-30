## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Crear rama `feature/llm-factory` desde main

## 1. Dependencias

- [x] 1.1 `uv add langchain-openai langchain-huggingface` (langchain-anthropic ya existe)
- [x] 1.2 `uv lock` para regenerar el lock file

## 2. Settings (TDD)

- [x] 2.1 Escribir tests que fallan: validación de API key requerida según proveedor activo (`anthropic_api_key` vacío con provider anthropic → `ValueError`; `openai_api_key` vacío con provider openai → `ValueError`)
- [x] 2.2 Ampliar `app/core/settings.py`: añadir `llm_provider`, `classifier_model`, `responder_model`, `embedding_provider`, `embedding_model`, `openai_api_key`; añadir `model_validator` que valide la API key del proveedor activo
- [x] 2.3 Actualizar `.example.env` con las nuevas variables

## 3. LLM Factory (TDD)

- [x] 3.1 Escribir tests que fallan para `get_llm`: provider anthropic → `ChatAnthropic`; provider openai → `ChatOpenAI`; provider desconocido → `ValueError`; rol classifier usa `classifier_model`; rol responder usa `responder_model`
- [x] 3.2 Escribir tests que fallan para `get_embedding_model`: provider huggingface → `HuggingFaceEmbeddings`; provider openai → `OpenAIEmbeddings`; provider desconocido → `ValueError`
- [x] 3.3 Crear `app/features/butler/llm/__init__.py` exportando `get_llm`, `get_embedding_model`
- [x] 3.4 Crear `app/features/butler/llm/factory.py` con la implementación del factory (ver design.md)
- [x] 3.5 Verificar que todos los tests del factory pasan

## 4. Refactor nodes.py

- [x] 4.1 Eliminar importación directa de `ChatAnthropic` y la función `_get_llm` de `nodes.py`
- [x] 4.2 Sustituir `_get_llm(model)` por `get_llm("classifier")` y `get_llm("responder")` en `classify_intent` y `answer_question`
- [x] 4.3 Eliminar constantes `_CLASSIFIER_MODEL` y `_RESPONDER_MODEL` de `nodes.py` (ahora en Settings)

## 5. Tests y verificación (OBLIGATORIO)

- [x] 5.1 Ejecutar `uv run pytest -q` — suite completa en verde; no hay mutaciones de BD en este cambio
- [x] 5.2 Guardar informe en `openspec/changes/llm-factory/reports/YYYY-MM-DD-backend-tests.md`

## 6. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 6.1 Arrancar backend: `uv run uvicorn app.main:app --reload`
- [x] 6.2 Login: `POST /api/auth/login` → obtener token
- [x] 6.3 Pregunta de Minecraft: `POST /api/butler/ask` con `{"message": "¿cómo fabrico una espada de diamante?"}` → 200, respuesta coherente, proveedor correcto en traza LangSmith
- [x] 6.4 Sin token → 401
- [x] 6.5 Verificar en LangSmith que el modelo activo corresponde al configurado en `.env`
- [x] 6.6 Documentar comandos y respuestas en el informe de reports/

## 7. Cierre (OBLIGATORIO)

- [x] 7.1 Actualizar `docs/backend-standards.md` con la sección del LLM factory (cómo añadir un nuevo proveedor)
- [x] 7.2 PR con `gh` usando la skill `write-pr-report`
