## Context

El mod Java envía `world_context` como campo adicional en cada petición al butler. Para `/ask` llega en el JSON body; para `/ask-voice` llega como form field de texto (JSON serializado) junto al multipart de audio. El backend actual ignora ambos campos.

El grafo LangGraph tiene tres nodos que llaman al LLM: `classify_intent`, `speak_action` y `answer_question`. El clasificador ya usa structured output (`IntentOutput`). El contexto del mundo es útil en `speak_action` y `answer_question`, no en `classify_intent` (que solo necesita el mensaje para clasificar).

## Goals / Non-Goals

**Goals:**
- Recibir `world_context` en ambos endpoints sin romper clientes que no lo envíen.
- Propagar el contexto hasta los nodos del grafo a través de `ButlerState`.
- Decidir con el clasificador (sin coste extra de latencia) si el contexto es necesario.
- Formatear el contexto como texto compacto con IDs de Minecraft tal cual (el LLM los conoce).
- Inyectar el texto solo en el system prompt del request actual, no en el historial de mensajes.

**Non-Goals:**
- Persistir el `world_context` en Redis junto al historial de conversación.
- Traducir IDs de Minecraft a nombres legibles.
- Filtrar qué partes del contexto (inventario vs. cofres vs. nearby) inyectar por separado; el texto compacto completo basta.
- Migraciones de BD (no hay cambios de modelo de datos).

## Decisions

### D1 — `WorldContextDTO` como modelo Pydantic en `schemas.py`

Se define `WorldContextDTO` con sub-modelos que reflejan la estructura del mod Java. Esto valida la entrada, da autocompletado en los tests y hace explícito el contrato. El campo en `AskRequest` es `world_context: WorldContextDTO | None = None`.

**Alternativa descartada:** aceptar `world_context` como `dict` libre. Permite datos malformados y no documenta el contrato.

### D2 — `needs_world_context: bool` en `IntentOutput`

El clasificador ya recibe el mensaje completo y produce structured output. Añadir un booleano es gratis en latencia (misma llamada al LLM) y da routing preciso. El clasificador decide mejor que cualquier heurística de keywords porque entiende contexto semántico ("¿me queda trigo?" vs. "¿cómo se planta trigo?").

**Alternativa descartada:** heurística de keywords en Python. Más frágil, no maneja sinónimos ni preguntas complejas.

### D3 — Contexto inyectado solo en system prompt, nunca en `messages`

El `world_context` es un snapshot efímero del instante de la petición. Guardarlo en el historial `messages` contaminaría turnos futuros con datos desactualizados (el jugador puede haberse movido, haber vaciado cofres, etc.). Se construye el system prompt dinámicamente en cada nodo y se descarta.

### D4 — Formato de texto compacto con IDs de Minecraft

```
Contexto del mundo:
- Posición: (102, 64, -45)
- Inventario: 64× minecraft:dirt, 5× minecraft:iron_ingot (y 12 tipos más)
- Cofre "despensa": 20× minecraft:bread, 16× minecraft:carrot
- Animales cercanos: 8 minecraft:cow, 3 minecraft:sheep
- Cultivos: minecraft:wheat (12 maduros, 8 creciendo)
```

Se limitan los items mostrados (top 10 del inventario, top 5 por cofre, top 5 animales) para acotar el máximo de tokens incluso con mundos grandes. El formato usa `×` para contar y es legible tanto para el LLM como para debugging.

### D5 — `world_context` en `ButlerState` como `dict | None`

Se almacena como dict (el modelo Pydantic se convierte con `.model_dump()`) para que LangGraph lo serialice sin friction. `needs_world_context: bool` también se añade al estado para que los nodos downstream lo lean sin recalcular.

### D6 — Voz: `world_context` como form field de texto opcional

FastAPI acepta `world_context: str | None = Form(None)` junto a `audio: UploadFile` en el mismo multipart. En el router se parsea con `json.loads(world_context)` si no es None, y se valida contra `WorldContextDTO`. Si el JSON está malformado se ignora silenciosamente (el campo es opcional).

## Risks / Trade-offs

- **Coste del boolean extra en el clasificador** → prácticamente cero; el structured output ya genera un JSON; añadir un campo booleano no cambia el número de tokens de salida de forma apreciable.
- **Clasificador se equivoca en `needs_world_context`** → impacto bajo: si lo marca `false` cuando sería útil, Alfred responde sin contexto (igual que hoy). Si lo marca `true` innecesariamente, se añaden ~80 tokens al prompt sin daño funcional.
- **Formato compacto trunca información** → el límite de 10 items de inventario puede omitir items relevantes en inventarios muy grandes. Mitigation: ordenar por count descendente; los items en mayor cantidad son estadísticamente los más relevantes para preguntas de recursos.
- **JSON malformado en `world_context` del form** → ignorado silenciosamente con log de warning. No rompe la llamada de voz.
