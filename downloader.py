#!/usr/bin/env python3
"""
Simple YouTube & Instagram Reels downloader built on top of yt-dlp.

Usage:
    python downloader.py <url1> <url2> ... [-o OUTPUT] [--audio-only]

Make sure yt-dlp is installed first:
    pip install yt-dlp
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Iterable, List, Optional


def import_yt_dlp():
    try:
        import yt_dlp  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - user error path
        print(
            "The yt-dlp package is required. Install it with `pip install yt-dlp`.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return yt_dlp


def resolve_output_dir(output: Optional[str]) -> Path:
    path = Path(output) if output else Path("downloads")
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_yt_dlp_opts(
    output_dir: Path,
    audio_only: bool,
    filename_template: Optional[str],
    quiet: bool,
) -> tuple[dict, str]:
    if audio_only:
        format_selector = "bestaudio/best"
    else:
        format_selector = (
            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
        )
    template = filename_template or (
        "[%(uploader)s]%(title)s(%(epoch>%Y년%m월%d일%H시)s).%(ext)s"
    )
    output_template = str(output_dir / template)

    opts = {
        "format": format_selector,
        "outtmpl": {"default": output_template},
        "quiet": quiet,
        "noplaylist": True,
        "ignoreerrors": False,
        "merge_output_format": "mp3" if audio_only else "mp4",
    }
    if audio_only:
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    return opts, template


ProgressHook = Callable[[dict], None]
ItemCompleteHook = Callable[[str, bool], None]


def platform_subdirectory(url: str) -> Optional[str]:
    lower = url.lower()
    if "instagram.com" in lower or "instagr.am" in lower:
        return "insta"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "Youtube"
    return None


def download_urls(
    urls: Iterable[str],
    output_dir: Path,
    audio_only: bool,
    filename_template: Optional[str],
    quiet: bool,
    progress_hook: Optional[ProgressHook] = None,
    item_complete_hook: Optional[ItemCompleteHook] = None,
) -> List[str]:
    yt_dlp = import_yt_dlp()
    options, template = build_yt_dlp_opts(output_dir, audio_only, filename_template, quiet)
    if progress_hook is not None:
        options["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(options) as ydl:
        failed: List[str] = []
        for url in urls:
            try:
                subdir = platform_subdirectory(url)
                base_dir = output_dir / subdir if subdir else output_dir
                base_dir.mkdir(parents=True, exist_ok=True)
                ydl.params["outtmpl"]["default"] = str(base_dir / template)
                ydl.download([url])
                if item_complete_hook:
                    item_complete_hook(url, True)
            except Exception:  # pragma: no cover - network path
                failed.append(url)
                if item_complete_hook:
                    item_complete_hook(url, False)
    return failed


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download YouTube videos and Instagram Reels via yt-dlp.",
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="Video/Reel URLs to download.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory. Defaults to ./downloads",
    )
    parser.add_argument(
        "-t",
        "--template",
        help="Custom filename template understood by yt-dlp.",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Download audio track only (MP3).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce yt-dlp output noise.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    output_dir = resolve_output_dir(args.output)
    failed = download_urls(
        urls=args.urls,
        output_dir=output_dir,
        audio_only=args.audio_only,
        filename_template=args.template,
        quiet=args.quiet,
    )
    if failed:
        raise SystemExit(
            f"Failed to download {len(failed)} item(s):\n" + "\n".join(failed)
        )


if __name__ == "__main__":
    main()
