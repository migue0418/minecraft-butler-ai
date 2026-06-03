# Informe de tests — init-butler-graph — 2026-05-30

## Comando ejecutado
```
uv run pytest -q
```

## Resultado
```
16 passed, 3 warnings in 8.02s
```
✅ 16/16 en verde.

## Tests nuevos añadidos

### `test_butler_service_question_intent`
Verifica que `ButlerService.run` convierte correctamente el estado del grafo con intención `question` en una `ButlerAction(type="speak")`. Mock de `_graph.ainvoke` para aislar del LLM.

### `test_butler_service_move_intent`
Verifica que `ButlerService.run` convierte el estado con intención `move` en una `ButlerAction(type="move_to_position")` con coordenadas correctas.

## Tests actualizados

Los 4 tests de butler existentes se actualizaron para mockear `ButlerService.run` o `_graph.ainvoke`, eliminando las llamadas reales a la API de Anthropic durante los tests.

También se corrigió `test_ask_with_valid_token`: el assert `"hola Alfred" in message` era específico del comportamiento de eco de la implementación anterior.

## Pruebas manuales (curl)

- `POST /api/butler/ask {"message": "como fabrico una espada de diamante"}` → 200, `type=speak`, respuesta de Claude sobre crafteo ✅
- `POST /api/butler/ask {"message": "ve a 100 64 -200"}` → 200, `type=move_to_position`, x=100, y=64, z=-200 ✅
- Sin token → 401 ✅

**Nota SSL**: el entorno tiene certificado corporativo (Zscaler). Se añadió dependencia `truststore` que inyecta el almacén de certificados de Windows en el módulo `ssl` de Python. Activado con `SSL_VERIFY=false` en `.env`. Para producción en un servidor sin proxy, `SSL_VERIFY=true` (default).

## Estado de BD
- No hay cambios de schema → no se verifica estado de BD
