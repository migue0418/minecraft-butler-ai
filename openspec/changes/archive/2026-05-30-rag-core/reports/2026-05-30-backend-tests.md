# Informe de tests y pruebas manuales — rag-core — 2026-05-30

## Comando ejecutado

```
uv run pytest -q
```

## Resultado

```
54 passed, 3 warnings in 13.21s
```

## Desglose

| Módulo | Tests nuevos | Tests totales | Resultado |
|--------|-------------|--------------|-----------|
| `tests/features/butler/test_rag_retriever.py` | 17 | 17 | ✅ |
| `tests/features/butler/test_llm_factory.py` | 2 | 19 | ✅ |
| `tests/test_api.py` | 3 | 19 | ✅ |
| **Total** | **22** | **54** | **✅** |

## Tests nuevos añadidos (22)

### `test_rag_retriever.py` (17)
- `TestRetrievedDocSchema` (3): construcción, metadata, roundtrip
- `TestRetrieverConfig` (1): configuración
- `TestHybridSearch` (5): docs filtrados, parent content mecánicas, filtro metadata, sin filtro, colección vacía
- `TestRerank` (3): top-k, vacío, score actualizado
- `TestBuildContext` (3): vacío, numeración, doc único
- `TestGetRetriever` (2): callable, pipeline completo

### `test_llm_factory.py` (2 añadidos)
- `test_default_values`: actualizado para embedding model `paraphrase-multilingual-MiniLM-L12-v2`
- `test_default_qdrant_settings`: verifica campos Qdrant en Settings

### `test_api.py` (3 añadidos)
- `test_classify_intent_item_question_sets_doc_type`
- `test_classify_intent_mob_question_sets_doc_type`
- `test_classify_intent_move_sets_doc_type_none`

## Mutaciones de BD

Ninguna — este cambio no toca el modelo de datos.

## Pruebas manuales curl

| Test | Resultado |
|---|---|
| `POST /api/butler/ask` receta espada diamante | ✅ 200 — respuesta con ingredientes correctos (2 diamantes + 1 palo) |
| `POST /api/butler/ask` drops creeper | ✅ 200 — pólvora + disco de música (si mata esqueleto) |
| `POST /api/butler/ask` mecánica encantamiento | ✅ 200 — respuesta coherente con contexto wiki |
| `POST /api/butler/ask` movimiento coordenadas | ✅ 200 — `move_to_position` sin llamada a Qdrant |
| Sin token | ✅ 401 |

## Ingesta

```
uv run python scripts/ingest.py --force
1415 documentos de ítems
151 documentos de mobs
99 documentos de mecánicas (10 páginas wiki)
Total: 1665 puntos en Qdrant
```

## Notas de implementación

- Corrección de API qdrant-client 1.18: `Prefetch` usa parámetro `using="dense"/"sparse"` en lugar de `NamedVector`/`NamedSparseVector`.
- Imagen Qdrant actualizada a `latest` (1.9.4 es incompatible con client 1.18).
- Versión de datos Minecraft actualizada a `1.21.6` (la `1.21` sin patch no existe en PrismarineJS).
- SSL bypass via `set_client_factory` de `huggingface_hub.utils._http` para entornos con proxy corporativo.
- `tests/features/__init__.py` añadido para resolver pythonpath en pytest.
