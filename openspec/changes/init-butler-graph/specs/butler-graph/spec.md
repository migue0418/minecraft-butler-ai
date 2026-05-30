## ADDED Requirements

### Requirement: Clasificación de intención
El sistema MUST clasificar el mensaje del usuario en una intención estructurada mediante el nodo `classify_intent` del grafo. Las intenciones válidas en el MVP son: `question`, `move`, `speak`. El clasificador usa Claude con salida estructurada (enum restringido) para garantizar que la intención sea uno de los valores permitidos.

#### Scenario: Mensaje de pregunta sobre Minecraft
- **WHEN** el mensaje del usuario es una pregunta sobre el juego ("¿cómo fabrico una espada?")
- **THEN** `classify_intent` emite `intent = "question"`
- **AND** el grafo enruta al nodo `answer_question`

#### Scenario: Mensaje de movimiento con coordenadas
- **WHEN** el mensaje contiene coordenadas o instrucción de desplazamiento ("ve a 100 64 -200")
- **THEN** `classify_intent` emite `intent = "move"`
- **AND** el grafo enruta al nodo de movimiento

#### Scenario: Mensaje genérico / saludo
- **WHEN** el mensaje no encaja en ninguna intención específica
- **THEN** `classify_intent` emite `intent = "speak"`
- **AND** el grafo devuelve una respuesta de tipo `speak`

### Requirement: Respuesta a preguntas sobre Minecraft
El sistema MUST responder preguntas sobre Minecraft mediante el nodo `answer_question`, usando Claude como LLM. La respuesta se devuelve como `ButlerAction` de tipo `speak` con el texto de respuesta en `message`.

#### Scenario: Pregunta sobre crafteo
- **WHEN** la intención es `question` y el mensaje pregunta cómo fabricar un objeto
- **THEN** el nodo `answer_question` devuelve una `ButlerAction(type="speak", message=<respuesta de Claude>)`

#### Scenario: Pregunta sobre mecánicas del juego
- **WHEN** la intención es `question` y el mensaje pregunta sobre mecánicas (spawns, biomas, etc.)
- **THEN** el nodo devuelve una `ButlerAction(type="speak", message=<respuesta de Claude>)`

### Requirement: Routing condicional del grafo
El sistema MUST enrutar el flujo desde `classify_intent` al nodo correcto según la intención detectada. El routing es una función pura que lee `state["intent"]` y devuelve el nombre del siguiente nodo.

#### Scenario: Routing a answer_question
- **WHEN** `state["intent"] == "question"`
- **THEN** el grafo ejecuta el nodo `answer_question`

#### Scenario: Routing a speak/move (stubs en MVP)
- **WHEN** `state["intent"]` es `"move"` o `"speak"`
- **THEN** el grafo ejecuta el nodo correspondiente (stub que devuelve la acción sin llamar al LLM)

### Requirement: Observabilidad con LangSmith
El sistema MUST enviar trazas de todas las ejecuciones del grafo a LangSmith cuando `LANGCHAIN_TRACING_V2=true` está configurado. Cada run incluye: el mensaje de entrada, la intención clasificada, los tokens usados y la latencia de cada nodo.

#### Scenario: Tracing activado
- **WHEN** `LANGCHAIN_TRACING_V2=true` y `LANGSMITH_API_KEY` están en el entorno
- **THEN** cada invocación del grafo aparece como un run en el proyecto LangSmith configurado

#### Scenario: Tracing desactivado (desarrollo sin API key)
- **WHEN** `LANGCHAIN_TRACING_V2` no está configurado o es `false`
- **THEN** el grafo funciona normalmente sin enviar trazas; no lanza error
