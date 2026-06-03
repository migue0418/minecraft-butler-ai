## MODIFIED Requirements

### Requirement: Procesar petición del mayordomo
El sistema MUST procesar el mensaje del usuario mediante `POST /api/butler/ask` y devolver una lista de `ButlerAction`. La lógica de procesamiento se delega al grafo LangGraph (`ButlerService.run`), que clasifica la intención y ejecuta el nodo correspondiente. El contrato de la API no cambia: la respuesta es `list[ButlerAction]` con los mismos campos (`type`, `message`, `x?`, `y?`, `z?`).

#### Scenario: Pregunta sobre Minecraft
- **WHEN** un usuario autenticado envía `{"message": "¿cómo fabrico una espada de diamante?"}`
- **THEN** responde 200 con `[{"type": "speak", "message": "<respuesta de Claude>"}]`

#### Scenario: Mensaje con coordenadas
- **WHEN** un usuario autenticado envía `{"message": "ve a 100 64 -200"}`
- **THEN** responde 200 con `[{"type": "move_to_position", "message": "...", "x": 100, "y": 64, "z": -200}]`

#### Scenario: Saludo o mensaje genérico
- **WHEN** un usuario autenticado envía `{"message": "hola"}`
- **THEN** responde 200 con `[{"type": "speak", "message": "<respuesta de saludo>"}]`

#### Scenario: Sin autenticación
- **WHEN** la petición no incluye token de acceso válido
- **THEN** responde 401
