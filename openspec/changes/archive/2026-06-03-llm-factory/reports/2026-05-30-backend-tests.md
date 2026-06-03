# Informe de tests — llm-factory — 2026-05-30

## Comando ejecutado

```
uv run pytest -q
```

## Resultado

```
33 passed, 3 warnings in 13.92s
```

## Desglose

| Módulo | Tests | Resultado |
|--------|-------|-----------|
| `tests/features/butler/test_llm_factory.py` | 17 | ✅ todos pasan |
| `tests/test_api.py` | 16 | ✅ todos pasan |

## Tests nuevos añadidos (17)

### `TestSettingsLLMValidation` (7 tests)
- Validación de API key vacía en development para Anthropic, OpenAI y embeddings OpenAI
- Validación se omite en environment=test
- Providers válidos pasan sin error
- Defaults de nuevos campos verificados

### `TestGetLlm` (6 tests)
- Anthropic → ChatAnthropic
- OpenAI → ChatOpenAI
- Provider desconocido → ValueError
- Rol classifier usa classifier_model
- Rol responder usa responder_model
- Rol desconocido → ValueError

### `TestGetEmbeddingModel` (4 tests)
- HuggingFace → HuggingFaceEmbeddings (mockeado, sin descarga de red)
- OpenAI → OpenAIEmbeddings
- Provider desconocido → ValueError
- HuggingFace usa el modelo configurado

## Mutaciones de BD

Ninguna — este cambio no toca el modelo de datos.

## Notas

- Los tests de HuggingFaceEmbeddings usan mock de `langchain_huggingface.HuggingFaceEmbeddings`
  para evitar descarga del modelo (SSL proxy corporativo).
- El fixture `build_client` en `test_api.py` añade `ENVIRONMENT=test` para evitar
  que el nuevo validador `validate_llm_api_keys` rompa los tests de integración existentes.
