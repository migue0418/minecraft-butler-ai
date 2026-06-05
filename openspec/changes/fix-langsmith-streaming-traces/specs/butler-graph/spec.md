## MODIFIED Requirements

### Requirement: Observabilidad con LangSmith
El sistema MUST enviar trazas de todas las ejecuciones del grafo a LangSmith cuando `LANGCHAIN_TRACING_V2=true` está configurado. Cada run incluye: el mensaje de entrada, la intención clasificada, los tokens usados y la latencia de cada nodo. El **árbol completo de nodos** (p. ej. `classify_intent`, `retrieve_context`, `answer_question`, `speak_action`, `move_action`) MUST aparecer anidado bajo el run raíz tanto en las invocaciones síncronas (`ainvoke`, endpoints `/api/butler/ask` y `/api/butler/ask-voice`) como en las invocaciones de **streaming** (`astream_events`, endpoints `/api/butler/ask-stream` y `/api/butler/ask-voice-stream`). Una traza de streaming MUST NOT quedar plana (solo run raíz con input→output, sin nodos hijos).

#### Scenario: Tracing activado
- **WHEN** `LANGCHAIN_TRACING_V2=true` y `LANGSMITH_API_KEY` están en el entorno
- **THEN** cada invocación del grafo aparece como un run en el proyecto LangSmith configurado

#### Scenario: Tracing desactivado (desarrollo sin API key)
- **WHEN** `LANGCHAIN_TRACING_V2` no está configurado o es `false`
- **THEN** el grafo funciona normalmente sin enviar trazas; no lanza error

#### Scenario: Traza completa en endpoint de streaming
- **WHEN** `LANGCHAIN_TRACING_V2=true` y un cliente invoca `/api/butler/ask-stream` o `/api/butler/ask-voice-stream`
- **THEN** el run raíz `butler-{mode}-stream` muestra anidados los runs hijos de los nodos del grafo visitados (con su latencia), igual que el camino `ainvoke`, y no aparece como una traza plana input→output

#### Scenario: Equivalencia de árbol entre streaming y no-streaming
- **WHEN** se envía el mismo mensaje a `/api/butler/ask` (síncrono) y a `/api/butler/ask-stream` (streaming) con tracing activado
- **THEN** ambas trazas contienen el mismo conjunto de nodos visitados anidados bajo su run raíz
