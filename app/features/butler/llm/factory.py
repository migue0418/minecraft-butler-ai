from functools import lru_cache
from typing import Literal

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.settings import get_settings

LLMRole = Literal["classifier", "responder"]


def _apply_hf_ssl_bypass_if_needed() -> None:
    """Aplica bypass SSL para HuggingFace Hub cuando ssl_verify=False.

    Necesario en entornos con proxy corporativo: sentence_transformers comprueba
    adapter_config.json en HF Hub al cargar el modelo, aunque esté en caché local.
    """
    settings = get_settings()
    if settings.ssl_verify:
        return
    try:
        import httpx
        from huggingface_hub.utils._http import set_client_factory

        set_client_factory(lambda: httpx.Client(verify=False))
    except Exception:
        pass


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


@lru_cache(maxsize=1)
def get_embedding_model() -> Embeddings:
    """Devuelve una instancia de Embeddings configurada según Settings.

    Usa lru_cache para crear el modelo una sola vez por proceso (carga ~150MB).
    Aplica bypass SSL si ssl_verify=False (proxy corporativo).

    Raises:
        ValueError: Si embedding_provider no está soportado.
    """
    _apply_hf_ssl_bypass_if_needed()
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
