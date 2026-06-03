## ADDED Requirements

### Requirement: Session-scoped conversation memory
The system SHALL persist conversation state per session using LangGraph's Redis checkpointer, keyed by `thread_id = session_id`. A subsequent request with the same `session_id` SHALL resume the persisted state so the assistant can use prior turns as context.

#### Scenario: Second turn remembers the first
- **GIVEN** a request with `session_id = "player-123"` and message "¿cómo fabrico una espada de diamante?"
- **WHEN** a second request arrives with the same `session_id` and message "¿y si no tengo suficientes materiales?"
- **THEN** the assistant's answer takes into account the diamond-sword context from the first turn

#### Scenario: Different sessions are isolated
- **GIVEN** two requests with different `session_id` values
- **WHEN** each is processed
- **THEN** neither sees the other's conversation history

### Requirement: Optional session_id in the ask contract
The `POST /api/butler/ask` request SHALL accept an optional `session_id` field. When present, the conversation is persisted under that id. When absent, the request SHALL be processed with an ephemeral thread id and SHALL NOT persist memory across requests, preserving the previous (stateless) contract.

#### Scenario: Request without session_id still works
- **WHEN** a request is sent with only `message` and no `session_id`
- **THEN** the endpoint responds 200 with valid actions and no memory is persisted

#### Scenario: Request with session_id persists memory
- **WHEN** a request includes a non-empty `session_id`
- **THEN** the resulting conversation state is stored in Redis under that id

### Requirement: Accumulated message history in graph state
The butler graph state SHALL include a `messages` field that accumulates user and assistant messages across turns of the same session (via an additive reducer). The answering node SHALL build the LLM input from this history, not only from the latest message.

#### Scenario: History grows across turns
- **WHEN** two turns are processed under the same `session_id`
- **THEN** the second turn's graph state contains the messages from both turns

### Requirement: Session expiration via TTL
Persisted session state in Redis SHALL expire after a configurable TTL (default 24 hours) so inactive sessions are cleaned up automatically. Within the TTL window the full history is available.

#### Scenario: Inactive session expires
- **GIVEN** a session whose last activity is older than the configured TTL
- **WHEN** its keys are checked in Redis
- **THEN** they have expired and the session no longer carries history

#### Scenario: TTL is configurable
- **WHEN** `REDIS_SESSION_TTL_SECONDS` is set
- **THEN** session keys are written with that expiration

### Requirement: Redis checkpointer lifecycle
The system SHALL initialize the Redis checkpointer at application startup (including any required index setup) and SHALL compile the butler graph with that checkpointer. The connection SHALL be closed on shutdown. The Redis connection target SHALL come from `Settings` (`REDIS_URL`), not read from the environment in domain code.

#### Scenario: Checkpointer ready before serving
- **WHEN** the application starts
- **THEN** the Redis checkpointer is created and its setup completed before the first request is served

#### Scenario: Redis URL comes from Settings
- **WHEN** the checkpointer is created
- **THEN** its connection target is `settings.redis_url`
