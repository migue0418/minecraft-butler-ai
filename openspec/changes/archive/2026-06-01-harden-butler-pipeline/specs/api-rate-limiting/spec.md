## ADDED Requirements

### Requirement: Rate limiting en endpoints del butler
El sistema MUST limitar la tasa de peticiones en los endpoints del butler que invocan al LLM, para proteger el coste de tokens frente a bucles de reintento o abuso. Se usa SlowAPI con `key_func=get_remote_address`. El límite es 20 peticiones/minuto para `POST /api/butler/ask` y `POST /api/butler/ask-voice`. Cuando se supera el límite, el sistema responde 429.

#### Scenario: Límite superado en ask
- **WHEN** una IP envía más de 20 peticiones a `POST /api/butler/ask` en un minuto
- **THEN** la petición número 21 o superior responde 429 Too Many Requests

#### Scenario: Límite superado en ask-voice
- **WHEN** una IP envía más de 20 peticiones a `POST /api/butler/ask-voice` en un minuto
- **THEN** la petición número 21 o superior responde 429

#### Scenario: Petición dentro del límite
- **WHEN** una IP no ha superado el límite en la ventana de tiempo
- **THEN** el endpoint procesa la petición normalmente y devuelve la lista de `ButlerAction`
