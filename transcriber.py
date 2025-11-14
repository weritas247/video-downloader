#!/usr/bin/env python3
"""CLI utility to generate transcripts from audio files using Whisper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

from transcription import iter_audio_files, transcribe_audio


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate transcripts for MP3/other audio files using OpenAI Whisper."
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="Audio files or directories containing audio files.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Optional directory to store transcripts. Defaults to each audio file's folder.",
    )
    parser.add_argument(
        "--model",
        default="base",
        help="Whisper model name to load (default: %(default)s).",
    )
    return parser.parse_args(argv)


def collect_audio_paths(targets: Iterable[str]) -> List[Path]:
    resolved_targets = [Path(path) for path in targets]
    audio_files = list(iter_audio_files(*resolved_targets))
    if not audio_files:
        raise SystemExit("No audio files found in the provided paths.")
    return audio_files


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    audio_files = collect_audio_paths(args.targets)
    output_dir = args.output_dir
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    successes = []
    failures = []
    for audio_file in audio_files:
        destination = (
            (output_dir / (audio_file.stem + ".txt")) if output_dir else None
        )
        try:
            transcript_path = transcribe_audio(
                audio_file,
                output_path=destination,
                model_name=args.model,
            )
        except RuntimeError as exc:
            print(f"Failed to load Whisper model: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # pragma: no cover - runtime runtime guardrail
            failures.append((audio_file, str(exc)))
            continue

        if transcript_path:
            successes.append((audio_file, transcript_path))
        else:
            failures.append((audio_file, "Empty transcript"))

    for src, transcript in successes:
        print(f"[OK] {src} -> {transcript}")
    for src, reason in failures:
        print(f"[FAIL] {src}: {reason}", file=sys.stderr)

    if failures:
        print(f"Completed with errors: {len(failures)} failure(s).", file=sys.stderr)
        return 2
    print(f"Transcribed {len(successes)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
