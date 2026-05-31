from __future__ import annotations

import os
import tempfile

from faster_whisper import WhisperModel

from app.core.settings import get_settings

_whisper_model: WhisperModel | None = None


def get_whisper_model() -> WhisperModel:
    """Singleton: carga el modelo una sola vez. Llamar en lifespan para precalentar."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    settings = get_settings()
    # int8 en CPU: ~2× más rápido y mitad de memoria vs float32, sin pérdida apreciable.
    compute_type = "int8" if settings.whisper_device == "cpu" else "float16"
    _whisper_model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=compute_type,
    )
    return _whisper_model


def reset_whisper_model() -> None:
    """Limpia el singleton del modelo. Solo para uso en tests."""
    global _whisper_model
    _whisper_model = None


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio_bytes a texto usando faster-whisper.

    Escribe en un fichero temporal porque WhisperModel.transcribe() acepta path,
    no bytes directos. El tempfile se elimina siempre, incluso si la transcripción falla.

    Raises:
        ValueError: si audio_bytes está vacío o la transcripción no produce texto.
    """
    if not audio_bytes:
        raise ValueError("El fichero de audio está vacío.")

    model = get_whisper_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        # language=None → autodetección (ES, EN y +90 idiomas más)
        # Consumir el generador dentro del try para que tmp_path siga existiendo
        segments, _ = model.transcribe(tmp_path, beam_size=5, language=None)
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        os.unlink(tmp_path)

    if not transcript:
        raise ValueError("No se pudo transcribir el audio.")
    return transcript
