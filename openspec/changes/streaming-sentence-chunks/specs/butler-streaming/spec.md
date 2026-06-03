## MODIFIED Requirements

### Requirement: Las acciones llegan conforme el grafo las genera
El endpoint `POST /api/butler/ask-stream` SHALL emitir cada chunk de texto del LLM como un evento SSE `data: {"type":"speak","message":"..."}` en cuanto se detecta una frontera natural en el flujo de tokens (fin de frase, salto de línea, encabezado). El cliente SHALL recibir múltiples eventos `speak` para una sola respuesta del LLM en lugar de un único evento con todo el texto. El evento final SHALL seguir siendo `data: [DONE]`.

#### Scenario: Respuesta larga llega frase a frase
- **WHEN** el LLM genera una respuesta de 4 frases para `/api/butler/ask-stream`
- **THEN** el cliente recibe al menos 2 eventos `speak` distintos antes de `[DONE]`, con el texto dividido en fronteras naturales

#### Scenario: Frase corta llega como un único chunk
- **WHEN** el LLM genera una respuesta de una sola frase sin saltos de línea
- **THEN** el cliente recibe un único evento `speak` (posiblemente precedido del echo) y luego `[DONE]`

#### Scenario: Acción move_to_position llega intacta
- **WHEN** el grafo genera una acción `move_to_position` (sin LLM, vía regex)
- **THEN** el cliente recibe un evento `{"type":"move_to_position","message":"...","x":...,"y":...,"z":...}` completo y correcto

#### Scenario: El primer evento es siempre el echo
- **WHEN** se llama a `/api/butler/ask-stream`
- **THEN** el primer evento SSE sigue siendo `{"type":"echo","message":"[Tú] ..."}` antes de cualquier chunk del LLM
