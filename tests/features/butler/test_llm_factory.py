"""Tests TDD para app/features/butler/llm/factory.py y Settings.validate_llm_api_keys."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings(**overrides):
    """Construye un objeto Settings aislado con los valores mínimos necesarios."""
    from app.core.settings import Settings

    base = {
        "environment": "test",
        "secret_key": "x" * 32,
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "anthropic_api_key": "sk-ant-test",
        "openai_api_key": "",
    }
    base.update(overrides)
    return Settings.model_validate(base)


# ── Settings: validate_llm_api_keys ──────────────────────────────────────────


class TestSettingsLLMValidation:
    def test_anthropic_provider_with_empty_key_raises_in_development(self):
        with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
            from app.core.settings import Settings

            Settings.model_validate(
                {
                    "environment": "development",
                    "secret_key": "x" * 32,
                    "database_url": "postgresql+asyncpg://x:x@localhost/x",
                    "llm_provider": "anthropic",
                    "anthropic_api_key": "",
                },
            )

    def test_openai_provider_with_empty_key_raises_in_development(self):
        with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
            from app.core.settings import Settings

            Settings.model_validate(
                {
                    "environment": "development",
                    "secret_key": "x" * 32,
                    "database_url": "postgresql+asyncpg://x:x@localhost/x",
                    "llm_provider": "openai",
                    "anthropic_api_key": "",
                    "openai_api_key": "",
                },
            )

    def test_openai_embedding_with_empty_key_raises_in_development(self):
        with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
            from app.core.settings import Settings

            Settings.model_validate(
                {
                    "environment": "development",
                    "secret_key": "x" * 32,
                    "database_url": "postgresql+asyncpg://x:x@localhost/x",
                    "llm_provider": "anthropic",
                    "anthropic_api_key": "sk-ant-test",
                    "embedding_provider": "openai",
                    "openai_api_key": "",
                },
            )

    def test_validation_skipped_in_test_environment(self):
        settings = _make_settings(
            environment="test",
            anthropic_api_key="",
            openai_api_key="",
        )
        assert settings.environment == "test"

    def test_anthropic_provider_with_valid_key_passes(self):
        settings = _make_settings(
            environment="development",
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-real-key",
        )
        assert settings.llm_provider == "anthropic"

    def test_openai_provider_with_valid_key_passes(self):
        settings = _make_settings(
            environment="development",
            llm_provider="openai",
            anthropic_api_key="",
            openai_api_key="sk-openai-real-key",
        )
        assert settings.llm_provider == "openai"

    def test_default_values(self):
        settings = _make_settings()
        assert settings.llm_provider == "anthropic"
        assert settings.classifier_model == "claude-haiku-4-5-20251001"
        assert settings.responder_model == "claude-sonnet-4-6"
        assert settings.embedding_provider == "huggingface"
        assert settings.embedding_model == "paraphrase-multilingual-MiniLM-L12-v2"
        assert settings.openai_api_key == ""

    def test_default_qdrant_settings(self):
        settings = _make_settings()
        assert settings.qdrant_url == "http://localhost:6333"
        assert settings.qdrant_collection == "minecraft_knowledge"
        assert settings.qdrant_api_key == ""
        assert settings.qdrant_top_k == 5
        assert settings.qdrant_prefetch_limit == 20


# ── get_llm ───────────────────────────────────────────────────────────────────


class TestGetLlm:
    def setup_method(self):
        from app.features.butler.llm.factory import get_llm

        get_llm.cache_clear()

    def teardown_method(self):
        from app.features.butler.llm.factory import get_llm

        get_llm.cache_clear()

    def test_anthropic_provider_returns_chat_anthropic(self):
        from langchain_anthropic import ChatAnthropic

        from app.features.butler.llm import get_llm

        settings = _make_settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            model = get_llm("classifier")
        assert isinstance(model, ChatAnthropic)

    def test_openai_provider_returns_chat_openai(self):
        from langchain_openai import ChatOpenAI

        from app.features.butler.llm import get_llm

        settings = _make_settings(
            llm_provider="openai",
            openai_api_key="sk-openai-test",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            model = get_llm("responder")
        assert isinstance(model, ChatOpenAI)

    def test_unknown_provider_raises_value_error(self):
        from app.features.butler.llm import get_llm

        settings = _make_settings()
        object.__setattr__(settings, "llm_provider", "cohere")

        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            with pytest.raises(ValueError, match="cohere"):
                get_llm("classifier")

    def test_classifier_role_uses_classifier_model(self):
        from langchain_anthropic import ChatAnthropic

        from app.features.butler.llm import get_llm

        settings = _make_settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
            classifier_model="claude-haiku-4-5-20251001",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            model = get_llm("classifier")
        assert isinstance(model, ChatAnthropic)
        assert model.model == "claude-haiku-4-5-20251001"

    def test_responder_role_uses_responder_model(self):
        from langchain_anthropic import ChatAnthropic

        from app.features.butler.llm import get_llm

        settings = _make_settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
            responder_model="claude-sonnet-4-6",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            model = get_llm("responder")
        assert isinstance(model, ChatAnthropic)
        assert model.model == "claude-sonnet-4-6"

    def test_unknown_role_raises_value_error(self):
        from app.features.butler.llm import get_llm

        settings = _make_settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            with pytest.raises(ValueError, match="unknown_role"):
                get_llm("unknown_role")  # type: ignore[arg-type]


# ── get_embedding_model ───────────────────────────────────────────────────────


class TestGetEmbeddingModel:
    def setup_method(self):
        from app.features.butler.llm.factory import get_embedding_model

        get_embedding_model.cache_clear()

    def test_huggingface_provider_returns_huggingface_embeddings(self):
        from app.features.butler.llm import get_embedding_model

        settings = _make_settings(
            embedding_provider="huggingface",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            with patch("langchain_huggingface.HuggingFaceEmbeddings") as mock_cls:
                get_embedding_model()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert "model_kwargs" in call_kwargs

    def test_openai_provider_returns_openai_embeddings(self):
        from langchain_openai import OpenAIEmbeddings

        from app.features.butler.llm import get_embedding_model

        settings = _make_settings(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            openai_api_key="sk-openai-test",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            model = get_embedding_model()
        assert isinstance(model, OpenAIEmbeddings)

    def test_unknown_embedding_provider_raises_value_error(self):
        from app.features.butler.llm import get_embedding_model

        settings = _make_settings()
        object.__setattr__(settings, "embedding_provider", "cohere")

        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            with pytest.raises(ValueError, match="cohere"):
                get_embedding_model()

    def test_huggingface_uses_configured_model(self):
        from app.features.butler.llm import get_embedding_model

        settings = _make_settings(
            embedding_provider="huggingface",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        )
        with patch(
            "app.features.butler.llm.factory.get_settings",
            return_value=settings,
        ):
            with patch("langchain_huggingface.HuggingFaceEmbeddings") as mock_cls:
                get_embedding_model()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert "model_kwargs" in call_kwargs


# ── get_llm cache ─────────────────────────────────────────────────────────────


class TestGetLLMCache:
    def setup_method(self):
        from app.features.butler.llm.factory import get_llm

        get_llm.cache_clear()

    def teardown_method(self):
        from app.features.butler.llm.factory import get_llm

        get_llm.cache_clear()

    def test_same_role_returns_same_instance(self):
        from app.features.butler.llm.factory import get_llm

        settings = _make_settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
        )
        with (
            patch(
                "app.features.butler.llm.factory.get_settings",
                return_value=settings,
            ),
            patch("langchain_anthropic.ChatAnthropic") as mock_cls,
        ):
            mock_cls.return_value = object()
            first = get_llm("responder")
            second = get_llm("responder")

        assert first is second
        assert mock_cls.call_count == 1

    def test_different_roles_return_different_instances(self):
        from app.features.butler.llm.factory import get_llm

        settings = _make_settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
        )
        with (
            patch(
                "app.features.butler.llm.factory.get_settings",
                return_value=settings,
            ),
            patch(
                "langchain_anthropic.ChatAnthropic",
                side_effect=lambda **kw: object(),
            ),
        ):
            classifier = get_llm("classifier")
            responder = get_llm("responder")

        assert classifier is not responder
