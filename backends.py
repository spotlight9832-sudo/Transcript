"""
Pluggable speech-to-text backends, used for sources (like RedNote) that
don't expose ready-made captions.

Default is local_whisper: free, runs on this machine's own CPU, no API
key or ongoing cost. To add a paid/cloud backend later: write a new class
implementing TranscriptionBackend.transcribe(), add an elif branch in
get_transcription_backend(), and switch TRANSCRIPTION_BACKEND in .env —
nothing else in the bot needs to change.
"""

import os
from abc import ABC, abstractmethod


class TranscriptionBackend(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Returns the transcript of the audio file as plain text."""


class LocalWhisperBackend(TranscriptionBackend):
    """Free, runs entirely on this machine's CPU via faster-whisper.
    Downloads model weights from Hugging Face the first time it runs
    (needs internet for that one-time download; nothing after, since the
    weights are cached locally)."""

    _model = None  # shared across instances/calls so the model loads only once

    def __init__(self, model_size: str = "base", task: str = "transcribe"):
        self.model_size = model_size
        self.task = task

    def _get_model(self):
        if LocalWhisperBackend._model is None:
            from faster_whisper import WhisperModel

            LocalWhisperBackend._model = WhisperModel(
                self.model_size, device="cpu", compute_type="int8"
            )
        return LocalWhisperBackend._model

    def transcribe(self, audio_path: str) -> str:
        model = self._get_model()
        segments, _info = model.transcribe(audio_path, task=self.task)
        return " ".join(segment.text.strip() for segment in segments).strip()


def get_transcription_backend() -> TranscriptionBackend:
    """Reads TRANSCRIPTION_BACKEND from .env and returns the matching
    backend. Defaults to the free local one."""
    backend_name = os.environ.get("TRANSCRIPTION_BACKEND", "local_whisper")

    if backend_name == "local_whisper":
        return LocalWhisperBackend(
            model_size=os.environ.get("WHISPER_MODEL_SIZE", "base"),
            task=os.environ.get("WHISPER_TASK", "transcribe"),
        )

    # Add new backends here later, e.g.:
    # if backend_name == "openai_api":
    #     return OpenAIWhisperAPIBackend(api_key=os.environ["OPENAI_API_KEY"])

    raise ValueError(
        f"Unknown TRANSCRIPTION_BACKEND '{backend_name}'. "
        "Add a matching class + branch in transcription/backends.py."
    )
