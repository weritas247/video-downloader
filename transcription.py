#!/usr/bin/env python3
"""Shared helpers for generating transcripts with OpenAI Whisper."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

_MODEL_LOCK = threading.Lock()
_WHISPER_MODEL = None


def _load_model(model_name: str = "base"):
    """Lazy-load and cache the Whisper model."""
    global _WHISPER_MODEL
    with _MODEL_LOCK:
        if _WHISPER_MODEL is not None:
            return _WHISPER_MODEL
        try:
            import whisper
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Whisper model is unavailable. Install dependencies with `pip install -r requirements.txt`."
            ) from exc
        _WHISPER_MODEL = whisper.load_model(model_name)
        return _WHISPER_MODEL


def transcribe_audio(
    audio_path: Path,
    *,
    output_path: Optional[Path] = None,
    model_name: str = "base",
) -> Optional[Path]:
    """
    Generate a transcript for `audio_path` using Whisper and return the saved text file path.

    The transcript is saved alongside the audio file unless `output_path` is provided.
    """
    audio_path = audio_path.expanduser().resolve()
    if not audio_path.exists():
        return None

    target = (
        output_path.expanduser().resolve()
        if output_path is not None
        else audio_path.with_suffix(".txt")
    )

    model = _load_model(model_name)
    result = model.transcribe(str(audio_path), fp16=False)
    text = (result.get("text") or "").strip()
    if not text:
        return None
    target.write_text(text, encoding="utf-8")
    return target


def iter_audio_files(*paths: Path, extensions: Optional[set[str]] = None):
    """Yield audio files from provided paths (files or directories)."""
    if extensions is None:
        extensions = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".webm"}
    normalized_exts = {ext.lower() for ext in extensions}
    for root in paths:
        root = root.expanduser().resolve()
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in normalized_exts:
                yield root
            continue
        for candidate in sorted(root.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in normalized_exts:
                yield candidate
