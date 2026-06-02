from functools import lru_cache
from typing import Literal

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.settings import get_settings

LLMRole = Literal["classifier", "responder"]


def _apply_hf_ssl_bypass_if_needed() -> None:
    """Fuerza carga offline de HuggingFace cuando ssl_verify=False.

    En entornos con proxy corporativo, sentence_transformers hace una llamada
    de red a HF Hub para comprobar adapter_config.json aunque el modelo esté
    en caché local. Con TRANSFORMERS_OFFLINE=1 ese check se omite y el modelo
    carga directamente del caché.
    """
    import os

    settings = get_settings()
    if settings.ssl_verify:
        return
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    try:
        import httpx
        from huggingface_hub.utils._http import set_client_factory

        set_client_factory(lambda: httpx.Client(verify=False))
    except Exception:
        pass


@lru_cache(maxsize=None)
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
    Con ssl_verify=False (proxy corporativo) fuerza carga desde caché local para
    evitar que sentence_transformers intente conectar a HuggingFace Hub.

    Raises:
        ValueError: Si embedding_provider no está soportado.
    """
    _apply_hf_ssl_bypass_if_needed()
    settings = get_settings()

    if settings.embedding_provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        # local_files_only=True evita cualquier llamada de red a HF Hub,
        # necesario en entornos con proxy SSL corporativo.
        model_kwargs = {"local_files_only": not settings.ssl_verify}
        return HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs=model_kwargs,
        )

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
