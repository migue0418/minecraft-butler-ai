## MODIFIED Requirements

### Requirement: Session-scoped conversation memory
The system SHALL persist conversation state per session using LangGraph's Redis checkpointer.
The `thread_id` SHALL be resolved as follows: the request `session_id` when present; otherwise an
id derived from the authenticated user (`user-{user_id}`). A subsequent request that resolves to
the same `thread_id` SHALL resume the persisted state so the assistant can use prior turns as
context.

#### Scenario: Second turn remembers the first
- **GIVEN** a request with `session_id = "player-123"` and message "¿cómo fabrico una espada de diamante?"
- **WHEN** a second request arrives with the same `session_id` and message "¿y si no tengo suficientes materiales?"
- **THEN** the assistant's answer takes into account the diamond-sword context from the first turn

#### Scenario: Different sessions are isolated
- **GIVEN** two requests with different `session_id` values
- **WHEN** each is processed
- **THEN** neither sees the other's conversation history

#### Scenario: Authenticated user without session_id remembers across turns
- **GIVEN** an authenticated user that sends two consecutive requests **without** `session_id`
- **WHEN** the first says "recuerda esto: me llamo Miguel" and the second asks "¿cómo me llamo?"
- **THEN** both requests resolve to the same `thread_id` (`user-{user_id}`) and the second answer recalls "Miguel"

### Requirement: Optional session_id in the ask contract
The `POST /api/butler/ask` request (and the voice/streaming variants) SHALL accept an optional
`session_id` field. When present, the conversation is persisted under that id. When absent, the
request SHALL be processed under a `thread_id` derived from the authenticated user
(`user-{user_id}`) and SHALL persist memory across that user's requests. Only when no authenticated
user is available SHALL the request fall back to an ephemeral, non-persisted thread id.

#### Scenario: Request without session_id persists memory under the user
- **WHEN** an authenticated request is sent with only `message` and no `session_id`
- **THEN** the endpoint responds 200 with valid actions and the conversation state is stored in Redis under `user-{user_id}`

#### Scenario: Request with session_id persists memory
- **WHEN** a request includes a non-empty `session_id`
- **THEN** the resulting conversation state is stored in Redis under that id (taking precedence over the user-derived id)
