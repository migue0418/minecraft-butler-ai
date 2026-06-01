## MODIFIED Requirements

### Requirement: Endpoint de voz POST /api/butler/ask-voice
El sistema SHALL exponer un endpoint `POST /api/butler/ask-voice` protegido por JWT que acepte un fichero de audio, un `session_id` opcional y un `world_context` opcional (JSON serializado como form field de texto) vía `multipart/form-data`, transcriba el audio y devuelva la misma respuesta que `POST /api/butler/ask`. Si `world_context` está presente y es JSON válido, SHALL propagarse al grafo igual que en el endpoint de texto. Si está ausente o malformado, SHALL ignorarse silenciosamente (log de warning).

#### Scenario: Petición de voz autenticada devuelve acciones del butler
- **WHEN** un cliente autenticado envía un audio válido a `POST /api/butler/ask-voice`
- **THEN** el servidor responde 200 con una lista de `ButlerAction` idéntica en formato a la del endpoint de texto

#### Scenario: Petición sin autenticar devuelve 401
- **WHEN** se llama a `POST /api/butler/ask-voice` sin token JWT
- **THEN** el servidor responde 401

#### Scenario: Audio inválido o vacío devuelve 422
- **WHEN** se envía un fichero de audio vacío o con formato no soportado
- **THEN** el servidor responde 422 con un mensaje de error en español

#### Scenario: session_id opcional propaga la sesión de conversación
- **WHEN** se envía un audio con `session_id="player-uuid"`
- **THEN** el historial Redis de esa sesión incluye el turno de voz transcrito

#### Scenario: world_context válido en petición de voz activa el contexto
- **WHEN** se envía audio junto a un form field `world_context` con JSON válido de WorldContext
- **THEN** el contexto se propaga al grafo y se inyecta en el prompt si `needs_world_context=True`

#### Scenario: world_context malformado en petición de voz no rompe la llamada
- **WHEN** se envía audio junto a un form field `world_context` con JSON inválido
- **THEN** el servidor responde 200 (ignorando el contexto malformado) y Alfred responde sin contexto del mundo
