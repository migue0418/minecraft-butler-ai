"""Tests TDD para app/features/butler/stt/service.py."""

from unittest.mock import MagicMock, patch

import pytest


class TestGetWhisperModelSingleton:
    def test_returns_same_instance_on_repeated_calls(self):
        from app.features.butler.stt.service import (
            get_whisper_model,
            reset_whisper_model,
        )

        reset_whisper_model()
        with patch("app.features.butler.stt.service.WhisperModel") as mock_cls:
            mock_cls.return_value = MagicMock()
            first = get_whisper_model()
            second = get_whisper_model()

        assert first is second
        assert mock_cls.call_count == 1

    def test_uses_settings_model_and_device(self):
        from app.features.butler.stt.service import (
            get_whisper_model,
            reset_whisper_model,
        )

        reset_whisper_model()
        with (
            patch("app.features.butler.stt.service.WhisperModel") as mock_cls,
            patch(
                "app.features.butler.stt.service.get_settings",
                return_value=MagicMock(whisper_model="small", whisper_device="cpu"),
            ),
        ):
            mock_cls.return_value = MagicMock()
            get_whisper_model()

        call_kwargs = mock_cls.call_args
        assert call_kwargs[0][0] == "small"
        assert call_kwargs[1]["device"] == "cpu"


class TestTranscribeAudio:
    def _make_mock_model(self, text: str = "hola mundo") -> MagicMock:
        seg = MagicMock()
        seg.text = text
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg], MagicMock())
        return mock_model

    def test_returns_concatenated_segment_text(self):
        from app.features.butler.stt.service import transcribe_audio

        mock_model = self._make_mock_model("hola mundo")
        with patch(
            "app.features.butler.stt.service.get_whisper_model",
            return_value=mock_model,
        ):
            result = transcribe_audio(b"fake_audio_bytes")

        assert result == "hola mundo"
        mock_model.transcribe.assert_called_once()

    def test_multiple_segments_are_joined(self):
        from app.features.butler.stt.service import transcribe_audio

        seg1, seg2 = MagicMock(), MagicMock()
        seg1.text = "como fabrico"
        seg2.text = "una espada"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg1, seg2], MagicMock())
        with patch(
            "app.features.butler.stt.service.get_whisper_model",
            return_value=mock_model,
        ):
            result = transcribe_audio(b"audio")

        assert result == "como fabrico una espada"

    def test_empty_bytes_raises_value_error(self):
        from app.features.butler.stt.service import transcribe_audio

        with pytest.raises(ValueError, match="vacío"):
            transcribe_audio(b"")

    def test_tempfile_deleted_even_on_transcribe_failure(self, tmp_path):
        import os

        from app.features.butler.stt.service import transcribe_audio

        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("model error")
        created_paths: list[str] = []

        original_ntf = __import__("tempfile").NamedTemporaryFile

        def tracking_ntf(**kwargs):
            f = original_ntf(**kwargs)
            created_paths.append(f.name)
            return f

        with (
            patch(
                "app.features.butler.stt.service.get_whisper_model",
                return_value=mock_model,
            ),
            patch(
                "app.features.butler.stt.service.tempfile.NamedTemporaryFile",
                side_effect=tracking_ntf,
            ),
            pytest.raises(RuntimeError),
        ):
            transcribe_audio(b"audio")

        for path in created_paths:
            assert not os.path.exists(path), f"Tempfile not deleted: {path}"

    def test_uses_autodetect_language(self):
        from app.features.butler.stt.service import transcribe_audio

        seg = MagicMock()
        seg.text = "test"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg], MagicMock())
        with patch(
            "app.features.butler.stt.service.get_whisper_model",
            return_value=mock_model,
        ):
            transcribe_audio(b"audio")

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get("language") is None
