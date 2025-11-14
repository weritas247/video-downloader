#!/usr/bin/env python3
"""Shared helpers for generating transcripts with OpenAI Whisper."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal, Optional

_MODEL_LOCK = threading.Lock()
_WHISPER_MODEL = None

TranscriptFormat = Literal["txt", "srt"]


def _format_timestamp(value: float) -> str:
    total_ms = max(0, int(value * 1000))
    hours, remainder = divmod(total_ms, 3600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def _segments_to_srt(segments) -> str:
    lines = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        start = float(segment.get("start") or 0.0)
        end = float(segment.get("end") or start)
        lines.append(str(index))
        lines.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


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
    transcript_format: TranscriptFormat = "txt",
    language: Optional[str] = None,
) -> Optional[Path]:
    """
    Generate a transcript for `audio_path` using Whisper and return the saved text file path.

    The transcript is saved alongside the audio file unless `output_path` is provided.
    """
    audio_path = audio_path.expanduser().resolve()
    if not audio_path.exists():
        return None

    fmt = transcript_format.lower()
    if fmt not in ("txt", "srt"):
        raise ValueError(f"Unsupported transcript format: {transcript_format}")

    target = (
        output_path.expanduser().resolve()
        if output_path is not None
        else audio_path.with_suffix(".srt" if fmt == "srt" else ".txt")
    )

    model = _load_model(model_name)
    transcribe_kwargs = {"fp16": False}
    if language:
        transcribe_kwargs["language"] = language
    result = model.transcribe(str(audio_path), **transcribe_kwargs)
    if fmt == "srt":
        segments = result.get("segments")
        if not segments:
            fallback_text = (result.get("text") or "").strip()
            if not fallback_text:
                return None
            segments = [
                {
                    "start": 0.0,
                    "end": max(len(fallback_text) * 0.03, 0.1),
                    "text": fallback_text,
                }
            ]
        content = _segments_to_srt(segments)
    else:
        content = (result.get("text") or "").strip()
    if not content:
        return None
    target.write_text(content, encoding="utf-8")
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
