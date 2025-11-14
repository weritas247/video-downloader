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
import os
import time
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
    *,
    keep_video_when_audio_only: bool = False,
) -> tuple[dict, str, str]:
    video_format = (
        "bv*[ext=mp4][vcodec^=avc]+ba[ext=m4a]/"
        "bv*[ext=mp4][vcodec^=h264]+ba[ext=m4a]/"
        "b[ext=mp4][vcodec^=avc]/"
        "b[ext=mp4][vcodec^=h264]/"
        "bv*[ext=mp4]+ba[ext=m4a]/"
        "b[ext=mp4]/"
        "bv*+ba/b"
    )
    if audio_only and not keep_video_when_audio_only:
        format_selector = "bestaudio/best"
        merge_ext = "mp3"
    else:
        format_selector = video_format
        merge_ext = "mp4"
    template = filename_template or (
        "[%(uploader)s]%(title)s(%(epoch>%Y년%m월%d일%H시)s).%(ext)s"
    )
    output_template = str(output_dir / template)

    postprocessors: list[dict] = []
    opts = {
        "format": format_selector,
        "outtmpl": {"default": output_template},
        "quiet": quiet,
        "noplaylist": True,
        "ignoreerrors": False,
        "merge_output_format": merge_ext,
    }
    if audio_only:
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        )
        if keep_video_when_audio_only:
            opts["keepvideo"] = True
            postprocessors.append(
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            )
    else:
        postprocessors.append(
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        )
    if postprocessors:
        opts["postprocessors"] = postprocessors
    return opts, template, merge_ext


def _ensure_kst_timezone() -> None:
    if os.environ.get("TZ") == "Asia/Seoul":
        return
    os.environ["TZ"] = "Asia/Seoul"
    if hasattr(time, "tzset"):
        try:
            time.tzset()
        except Exception:
            pass


_ensure_kst_timezone()

ProgressHook = Callable[[dict], None]
ItemCompleteHook = Callable[[str, bool], None]


def platform_subdirectory(url: str) -> Optional[str]:
    lower = url.lower()
    if "instagram.com" in lower or "instagr.am" in lower:
        return "Instagram"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "Youtube"
    return None


def _remove_existing_outputs(
    ydl: "yt_dlp.YoutubeDL", info: dict, merge_ext: str
) -> None:
    """Remove existing files that would conflict with the download target."""
    try:
        base_path = Path(ydl.prepare_filename(info))
    except Exception:
        return
    candidates = {base_path}
    if merge_ext:
        candidates.add(base_path.with_suffix(f".{merge_ext}"))
    for candidate in candidates:
        try:
            candidate.unlink(missing_ok=True)
        except Exception:
            pass


def download_urls(
    urls: Iterable[str],
    output_dir: Path,
    audio_only: bool,
    filename_template: Optional[str],
    quiet: bool,
    *,
    keep_video_when_audio_only: bool = False,
    progress_hook: Optional[ProgressHook] = None,
    item_complete_hook: Optional[ItemCompleteHook] = None,
) -> List[str]:
    yt_dlp = import_yt_dlp()
    options, template, merge_ext = build_yt_dlp_opts(
        output_dir,
        audio_only,
        filename_template,
        quiet,
        keep_video_when_audio_only=keep_video_when_audio_only,
    )
    if progress_hook is not None:
        options["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(options) as ydl:
        failed: List[str] = []
        for url in urls:
            subdir = platform_subdirectory(url)
            base_dir = output_dir / subdir if subdir else output_dir
            base_dir.mkdir(parents=True, exist_ok=True)
            ydl.params["outtmpl"]["default"] = str(base_dir / template)
            try:
                info = ydl.extract_info(url, download=False)
                _remove_existing_outputs(ydl, info, merge_ext)
                ydl.process_ie_result(info, download=True)
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
