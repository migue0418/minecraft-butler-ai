## ADDED Requirements

### Requirement: LLM factory resolves provider by configuration
The system SHALL instantiate `BaseChatModel` using `settings.llm_provider` and return the correct provider implementation without the caller knowing the concrete class.

#### Scenario: Anthropic provider selected
- **WHEN** `settings.llm_provider` is `"anthropic"` and `get_llm("classifier")` is called
- **THEN** the factory returns a `ChatAnthropic` instance configured with `settings.classifier_model` and `settings.anthropic_api_key`

#### Scenario: OpenAI provider selected
- **WHEN** `settings.llm_provider` is `"openai"` and `get_llm("responder")` is called
- **THEN** the factory returns a `ChatOpenAI` instance configured with `settings.responder_model` and `settings.openai_api_key`

#### Scenario: Unknown provider raises error
- **WHEN** `settings.llm_provider` is an unsupported value
- **THEN** the factory raises `ValueError` with a descriptive message listing valid providers

### Requirement: LLM factory resolves role to correct model
The system SHALL use distinct model identifiers for the `"classifier"` and `"responder"` roles, driven entirely by `Settings`.

#### Scenario: Classifier role uses classifier_model
- **WHEN** `get_llm("classifier")` is called
- **THEN** the returned instance uses `settings.classifier_model`

#### Scenario: Responder role uses responder_model
- **WHEN** `get_llm("responder")` is called
- **THEN** the returned instance uses `settings.responder_model`

### Requirement: Embedding factory resolves provider by configuration
The system SHALL instantiate an `Embeddings` implementation using `settings.embedding_provider`, returning the correct class without the caller coupling to a concrete provider.

#### Scenario: HuggingFace provider (default)
- **WHEN** `settings.embedding_provider` is `"huggingface"` and `get_embedding_model()` is called
- **THEN** the factory returns a `HuggingFaceEmbeddings` instance using `settings.embedding_model`

#### Scenario: OpenAI embedding provider
- **WHEN** `settings.embedding_provider` is `"openai"` and `get_embedding_model()` is called
- **THEN** the factory returns an `OpenAIEmbeddings` instance using `settings.embedding_model` and `settings.openai_api_key`

#### Scenario: Unknown embedding provider raises error
- **WHEN** `settings.embedding_provider` is an unsupported value
- **THEN** the factory raises `ValueError` with a descriptive message

### Requirement: Butler nodes use factory, not direct provider imports
The system SHALL NOT import `ChatAnthropic` or `ChatOpenAI` directly in `nodes.py`; all LLM instantiation MUST go through the factory.

#### Scenario: Provider swap via config only
- **WHEN** `settings.llm_provider` is changed from `"anthropic"` to `"openai"` (with valid `openai_api_key`)
- **THEN** the butler graph operates with the OpenAI provider without any code change

### Requirement: Missing API key raises error at startup
The system SHALL raise a `ValueError` during settings validation when the required API key for the configured provider is empty.

#### Scenario: Anthropic provider with empty key
- **WHEN** `settings.llm_provider` is `"anthropic"` and `settings.anthropic_api_key` is `""`
- **THEN** `Settings` validation raises `ValueError` indicating the missing key

#### Scenario: OpenAI provider with empty key
- **WHEN** `settings.llm_provider` is `"openai"` and `settings.openai_api_key` is `""`
- **THEN** `Settings` validation raises `ValueError` indicating the missing key
