## Context

El endpoint `POST /api/butler/ask` actualmente usa regex hardcoded. Se reemplaza esa lógica por un grafo LangGraph que clasifica la intención del usuario y la enruta al nodo handler correcto. El grafo vive en el slice `butler`, desacoplado del router.

Objetivo del MVP: **dos nodos funcionales** + observabilidad en LangSmith. El grafo debe ser fácilmente extensible para añadir nodos de RAG, STT, acciones en el juego, etc.

---

## Goals / Non-Goals

**Goals:**
- Grafo LangGraph con estado tipado, routing condicional y tracing LangSmith.
- Nodo `classify_intent` que usa Claude para emitir una intención estructurada.
- Nodo `answer_question` que usa Claude para responder preguntas sobre Minecraft.
- Router `butler` delega al grafo; contrato de la API (`list[ButlerAction]`) no cambia.
- Configuración limpia: `ANTHROPIC_API_KEY`, `LANGSMITH_*` en `Settings`.

**Non-Goals:**
- RAG, GraphRAG, STT, acciones de inventario — se añaden en cambios posteriores.
- Persistencia del historial de conversación en BD.
- Streaming de respuestas.

---

## Decisions

### Decisión 1: Estructura de ficheros en `butler/graph/`

```
app/features/butler/
    graph/
        __init__.py      # exporta compile_graph()
        state.py         # ButlerState (TypedDict)
        nodes.py         # classify_intent, answer_question
        routing.py       # función de routing condicional
        graph.py         # construcción y compilación del grafo
    router.py            # llama a graph.ainvoke(...)
    schemas.py           # sin cambios
    service.py           # nuevo: ButlerService.run(message) → list[ButlerAction]
```

**Alternativa descartada**: meter todo en un único fichero `graph.py`. Con dos nodos ya tiene suficiente complejidad como para justificar la separación, y facilita que los futuros nodos (RAG, acciones) añadan ficheros propios.

### Decisión 2: Estado del grafo (`ButlerState`)

```python
class ButlerState(TypedDict):
    message: str            # input del usuario
    intent: str             # "question" | "move" | "speak" | ...
    actions: list[dict]     # lista de ButlerAction-like dicts (salida final)
```

Estado mínimo. En el futuro se añadirán: `chat_history`, `retrieved_docs`, `audio_bytes`.

### Decisión 3: LLM — `ChatAnthropic` de `langchain-anthropic`

Se usa `langchain-anthropic` en lugar de `anthropic` directamente porque:
- LangChain gestiona el tracing LangSmith de forma automática para todas las llamadas al LLM.
- El nodo `classify_intent` usa `.with_structured_output()` para emitir la intención como objeto Pydantic.
- El cambio de proveedor (a Ollama u otro) solo requiere cambiar el LLM en un punto.

### Decisión 4: Tracing LangSmith

LangSmith se activa automáticamente cuando `LANGCHAIN_TRACING_V2=true` está en el entorno. No requiere código extra; LangChain + LangGraph instrumentan todas las llamadas. Solo hay que añadir las vars de entorno a `Settings` y `.example.env`.

### Decisión 5: Routing condicional

```
START → classify_intent → (condicional) → answer_question → END
                                        ↘ speak_action     → END
                                        ↘ move_action      → END
```

En el MVP solo `answer_question` está implementado. Los demás nodos (move, speak) son stubs que devuelven la acción directamente sin llamar al LLM.

### Decisión 6: `ButlerService` como capa intermedia

El router no llama al grafo directamente. `ButlerService.run(message, user)` encapsula la invocación del grafo y convierte el resultado a `list[ButlerAction]`. Esto sigue el patrón del proyecto (router delgado) y facilita testear el servicio aislado del grafo.

---

## Risks / Trade-offs

- [Latencia] Las llamadas a Claude añaden latencia (~1-3 s). Mitigación: aceptable para MVP; streaming se añadirá más adelante.
- [Coste API] Cada petición hace al menos 2 llamadas a Claude (clasificar + responder). Mitigación: el nodo `speak` y `move` se implementan como stubs sin LLM cuando la intención es obvia.
- [Fiabilidad del clasificador] Si Claude clasifica mal, el usuario recibe una respuesta del nodo incorrecto. Mitigación: el clasificador usa `.with_structured_output()` con un enum restringido, lo que minimiza errores de formato.

---

## Migration Plan

1. Crear rama `feature/init-butler-graph`.
2. Añadir dependencias: `uv add langgraph langchain-anthropic langchain-core langsmith`.
3. Crear `app/features/butler/graph/` con los 4 ficheros.
4. Crear `app/features/butler/service.py`.
5. Actualizar `butler/router.py` para usar `ButlerService`.
6. Actualizar `app/core/settings.py` y `.example.env`.
7. Tests + curl.

**Sin rollback de BD** (no hay cambios de schema).

---

## Open Questions

- ¿El clasificador debe devolver también `confidence`? Por ahora no; se añade si hay problemas de routing.
- ¿`ButlerService` debe recibir el historial de conversación? Para el MVP: no. Se añade cuando se implemente memoria de sesión.
