from typing import Literal

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.settings import get_settings

LLMRole = Literal["classifier", "responder"]


def get_llm(role: LLMRole) -> BaseChatModel:
    """Devuelve un BaseChatModel configurado según el rol semántico y Settings.

    Args:
        role: "classifier" usa settings.classifier_model;
              "responder" usa settings.responder_model.

    Raises:
        ValueError: Si llm_provider no está soportado o el rol es desconocido.
    """
    settings = get_settings()
    model_name = _resolve_model(role, settings)

    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
        )

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
        )

    raise ValueError(
        f"Proveedor LLM no soportado: '{settings.llm_provider}'. "
        "Valores válidos: 'anthropic', 'openai'.",
    )


def get_embedding_model() -> Embeddings:
    """Devuelve una instancia de Embeddings configurada según Settings.

    Raises:
        ValueError: Si embedding_provider no está soportado.
    """
    settings = get_settings()

    if settings.embedding_provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=settings.embedding_model)

    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
        )

    raise ValueError(
        f"Proveedor de embeddings no soportado: '{settings.embedding_provider}'. "
        "Valores válidos: 'huggingface', 'openai'.",
    )


# ── Helpers privados ──────────────────────────────────────────────────────────


def _resolve_model(role: str, settings) -> str:
    if role == "classifier":
        return settings.classifier_model
    if role == "responder":
        return settings.responder_model
    raise ValueError(
        f"Rol LLM desconocido: '{role}'. Valores válidos: 'classifier', 'responder'.",
    )
