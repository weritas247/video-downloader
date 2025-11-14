# video-downloader

Simple YouTube / Instagram Reels downloader powered by `yt-dlp`. Use either the CLI script or the bundled Flask web page.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You also need `ffmpeg` installed if you plan to extract MP3 audio. For automatic audio transcripts (generated whenever Audio-only mode is enabled in the web UI), the bundled requirements already include `openai-whisper`, which will download the necessary speech-to-text model on first use.

## CLI usage

```bash
python downloader.py <url1> <url2> ... [--audio-only] [-o OUTPUT_DIR]
```

Run `python downloader.py --help` to see all options.
By default each file is saved as `[채널명]동영상제목(년월일시).mp4` (or `.mp3` when audio-only), using the download time for the timestamp.

## Web interface

```bash
python web_app.py
```

Open http://127.0.0.1:5000 in your browser, paste URLs (one per line), tweak options, and click **Download**. The web UI now shows a progress bar for the batch download, automatically clears the URL field after completion, and saves files under the `downloads/` directory by default. When **Audio only (MP3)** is checked, each MP3 is processed with Whisper and an accompanying transcript (`.txt`) is saved alongside the audio file.
