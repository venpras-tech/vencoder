import tempfile
from pathlib import Path

_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


def transcribe_audio(audio_bytes: bytes, language: str | None = None) -> str:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        model = _get_model()
        segments, info = model.transcribe(
            path,
            beam_size=1,
            language=language or "en",
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
    finally:
        Path(path).unlink(missing_ok=True)
