#!/usr/bin/env python3
"""Web UI for downloader.py built with Flask."""

from __future__ import annotations

import threading
import uuid
import base64
import subprocess
import tempfile
from functools import partial
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from downloader import download_urls, resolve_output_dir

app = Flask(__name__)

JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
WHISPER_MODEL = None


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Video Downloader</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0d17;
      --panel: #1b1f2f;
      --panel-border: #2d334a;
      --text: #e3e5ec;
      --muted: #b3b8d4;
      --accent: #5a8dee;
      --accent-strong: #7fa6ff;
      --error: #ff6b6b;
    }
    body { font-family: system-ui, sans-serif; min-height: 100vh; margin: 0; line-height: 1.5; background: var(--bg); color: var(--text); padding: 2rem; box-sizing: border-box; }
    .container { max-width: 760px; margin: 0 auto; }
    textarea, input { width: 100%; padding: 0.75rem; border: 1px solid var(--panel-border); border-radius: 8px; background: var(--panel); color: var(--text); }
    textarea::placeholder, input::placeholder { color: var(--muted); }
    button { padding: 0.6rem 1.4rem; font-size: 1rem; border-radius: 999px; border: none; background: var(--accent); color: #fff; cursor: pointer; transition: background 0.2s ease; }
    button:hover { background: var(--accent-strong); }
    .secondary-btn { background: transparent; border: 1px solid var(--panel-border); color: var(--muted); border-radius: 8px; padding: 0.4rem 0.8rem; font-size: 0.85rem; margin-left: auto; display: inline-flex; align-items: center; gap: 0.35rem; }
    .secondary-btn:hover { color: var(--text); border-color: var(--accent); }
    label { display: block; font-weight: 600; margin-bottom: 0.35rem; color: var(--muted); }
    .row { display: flex; gap: 1rem; }
    .row > label { flex: 1; }
    form { background: var(--panel); padding: 1.75rem; border-radius: 16px; border: 1px solid var(--panel-border); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45); display: flex; flex-direction: column; gap: 1.25rem; }
    .form-group { display: flex; flex-direction: column; gap: 0.4rem; }
    .form-group small { color: var(--muted); font-weight: 400; }
    .inline-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }
    .options { display: flex; flex-wrap: wrap; gap: 1rem; }
    .checkbox-pill { display: flex; align-items: center; gap: 0.5rem; padding: 0.55rem 0.9rem; border-radius: 999px; border: 1px solid var(--panel-border); background: rgba(255,255,255,0.02); font-weight: 500; color: var(--text); }
    .checkbox-pill input { width: auto; margin: 0; }
    .form-actions { display: flex; justify-content: flex-end; }
    #status { white-space: pre-wrap; background: var(--panel); padding: 1rem; margin-top: 1rem; border-radius: 12px; border: 1px solid var(--panel-border); min-height: 3rem; }
    #history { margin-top: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
    .history-entry { background: var(--panel); border-radius: 12px; border: 1px solid var(--panel-border); padding: 1rem; display: flex; gap: 1rem; align-items: flex-start; }
    .history-entry.warning { border-color: var(--error); background: #2a1c1f; }
    .history-thumb { width: 96px; height: 54px; border-radius: 8px; object-fit: cover; background: #0f111c; flex-shrink: 0; border: 1px solid var(--panel-border); cursor: pointer; }
    .history-content { flex: 1; white-space: pre-wrap; }
    #modal-backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.8); display: none; align-items: center; justify-content: center; z-index: 999; }
    #modal-backdrop.active { display: flex; }
    #modal-content { max-width: 90vw; max-height: 90vh; }
    #modal-content img { width: 100%; height: auto; border-radius: 12px; border: 2px solid var(--panel-border); }
    #progress-wrapper { margin-top: 1rem; }
    .progress { width: 100%; height: 16px; background: #0f111c; border-radius: 999px; overflow: hidden; border: 1px solid var(--panel-border); }
    .progress-bar { height: 100%; width: 0%; background: linear-gradient(90deg, var(--accent), var(--accent-strong)); transition: width 0.3s ease; }
    #progress-text { margin-top: 0.4rem; color: var(--muted); font-size: 0.95rem; }
    #transcript-status { margin-top: 0.4rem; color: var(--muted); font-size: 0.95rem; }
    .hidden { display: none; }
    @media (max-width: 640px) {
      body { padding: 1rem; }
      form { padding: 1.25rem; }
      button { width: 100%; }
      textarea { min-height: 120px; }
      .container { width: 100%; }
      .form-actions { justify-content: center; }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Video &amp; Reels Downloader</h1>
    <p>Paste one or more URLs (YouTube / Instagram Reels, one per line) and press download.</p>
    <form id="download-form">
      <div class="form-group">
        <label for="urls">Video URLs</label>
        <textarea id="urls" rows="6"></textarea>
        <small>엔터 또는 쉼표로 여러 링크를 입력하면 일괄 다운로드 됩니다.</small>
      </div>
      <div class="inline-fields">
        <div class="form-group">
          <label for="output">Output directory</label>
          <input id="output" type="text" placeholder="downloads" />
          <small>지정하지 않으면 기본 downloads 폴더를 사용합니다.</small>
        </div>
      </div>
      <div class="options">
        <label class="checkbox-pill"><input id="audio-only" type="checkbox" /> Audio only (MP3)</label>
        <label class="checkbox-pill"><input id="quiet" type="checkbox" checked /> Quiet mode</label>
      </div>
      <div class="form-actions">
        <button type="submit">Download</button>
      </div>
    </form>
    <div id="progress-wrapper" class="hidden">
      <div class="progress">
        <div class="progress-bar" id="progress-bar"></div>
      </div>
      <div id="progress-text"></div>
      <div id="current-video"></div>
      <div id="transcript-status" class="hidden"></div>
    </div>
    <div id="status"></div>
    <div style="display:flex; align-items:center; gap:0.5rem; margin-top:1rem;">
      <h2 style="margin:0; font-size:1.2rem;">다운로드 기록</h2>
      <button id="clear-history" type="button" class="secondary-btn">기록 초기화</button>
    </div>
    <div id="history"></div>
    <div id="modal-backdrop">
      <div id="modal-content">
        <img id="modal-image" src="" alt="preview" />
      </div>
    </div>
  </div>
  <script>
    const STORAGE_KEY = "video-downloader-history";
    const form = document.getElementById("download-form");
    const statusBox = document.getElementById("status");
    const historyBox = document.getElementById("history");
    const clearHistoryBtn = document.getElementById("clear-history");
    const audioOnlyField = document.getElementById("audio-only");
    const modalBackdrop = document.getElementById("modal-backdrop");
    const modalImage = document.getElementById("modal-image");
    const urlsField = document.getElementById("urls");
    const progressWrapper = document.getElementById("progress-wrapper");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const transcriptStatus = document.getElementById("transcript-status");
    const PLACEHOLDER_THUMB = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="120" height="68" viewBox="0 0 120 68"%3E%3Crect width="120" height="68" rx="8" fill="%232d334a"/%3E%3Cpath d="M48 22l26 12-26 12z" fill="%235a8dee"/%3E%3C/svg%3E';
    audioOnlyField.checked = false;

    let pollTimer = null;
    let activeJobId = null;
    let autoStartTimer = null;
    let historyEntries = [];

    const resetProgress = () => {
      progressBar.style.width = "0%";
      progressText.textContent = "";
      progressWrapper.classList.add("hidden");
      activeJobId = null;
    };

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };

    const cancelAutoStart = () => {
      if (autoStartTimer) {
        clearTimeout(autoStartTimer);
        autoStartTimer = null;
      }
    };

    const scheduleAutoStart = () => {
      cancelAutoStart();
      autoStartTimer = setTimeout(() => {
        if (!urlsField.value.trim()) return;
        form.requestSubmit();
      }, 3000);
    };

    const normalizeCompletedItem = (item) => {
      if (item && typeof item === "object") {
        const name = typeof item.name === "string" && item.name ? item.name : "(파일명 정보 없음)";
        const thumbnail = typeof item.thumbnail === "string" && item.thumbnail ? item.thumbnail : null;
        return { name, thumbnail };
      }
      if (typeof item === "string") {
        return { name: item, thumbnail: null };
      }
      return { name: "(파일명 정보 없음)", thumbnail: null };
    };

    const normalizeTranscriptItem = (item) => {
      if (item && typeof item === "object") {
        return {
          name: item.name || "(스크립트)",
          path: item.path || "",
          source: item.source || "",
        };
      }
      if (typeof item === "string") {
        return { name: item, path: "", source: "" };
      }
      return { name: "(스크립트)", path: "", source: "" };
    };

    const getThumbnailSrc = (entry) => {
      const items = Array.isArray(entry.items) ? entry.items : [];
      const match = items.find((item) => item && item.thumbnail);
      return match ? match.thumbnail : PLACEHOLDER_THUMB;
    };

    const openModal = (src) => {
      modalImage.src = src || PLACEHOLDER_THUMB;
      modalBackdrop.classList.add("active");
    };

    const closeModal = () => {
      modalBackdrop.classList.remove("active");
      modalImage.src = "";
    };

    const updateProgressUI = (data) => {
      const percentage = Math.round((data.progress || 0) * 100);
      progressBar.style.width = `${percentage}%`;
      const label = `${percentage}% (${data.completed}/${data.total}) ${data.current_title || ""}`;
      progressText.textContent = label.trim();
      const currentVideo = document.getElementById("current-video");
      if (currentVideo) {
        currentVideo.textContent = data.current_title ? `다운로드 중: ${data.current_title}` : "";
      }
    };

    const updateTranscriptStatus = (data) => {
      if (!transcriptStatus) return;
      if (data.status === "transcribing") {
        const done = data.transcript_completed || 0;
        const total = data.transcript_total || 0;
        transcriptStatus.classList.remove("hidden");
        transcriptStatus.textContent = total
          ? `스크립트 추출 중... (${done}/${total})`
          : "스크립트 추출 중...";
      } else {
        transcriptStatus.classList.add("hidden");
        transcriptStatus.textContent = "";
      }
    };

    const formatHistoryText = (entry) => {
      const filenames = Array.isArray(entry.items) && entry.items.length
        ? entry.items.map((item) => item.name || "(파일명 정보 없음)")
        : ["(파일명 정보 없음)"];
      const transcripts = Array.isArray(entry.transcripts) ? entry.transcripts : [];
      const timestamp = entry.timestamp || Date.now();
      const lines = [
        "파일명:",
        ...filenames.map((name) => `- ${name}`),
        `결과: ${entry.success}/${entry.total}`,
      ];
      if (transcripts.length) {
        lines.push("스크립트 파일:");
        transcripts.forEach((item) => {
          const label = item.path ? `${item.name} (${item.path})` : item.name;
          lines.push(`- ${label}`);
        });
      }
      lines.push(`완료 시각: ${new Date(timestamp).toLocaleString()}`);
      return lines.join("\\n");
    };

    const saveHistory = () => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(historyEntries));
      } catch (error) {
        console.warn("히스토리 저장 실패", error);
      }
    };

    const renderHistory = () => {
      historyBox.innerHTML = "";
      historyEntries.forEach((entry) => {
        historyBox.appendChild(createHistoryElement(entry));
      });
    };

    const loadHistory = () => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed)) {
            historyEntries = parsed.map((entry) => {
              const items = Array.isArray(entry.items)
                ? entry.items.map((item) => normalizeCompletedItem(item))
                : Array.isArray(entry.filenames)
                  ? entry.filenames.map((name) => normalizeCompletedItem(name))
                  : [];
              const transcripts = Array.isArray(entry.transcripts)
                ? entry.transcripts.map((item) => normalizeTranscriptItem(item))
                : [];
              return {
                ...entry,
                items,
                transcripts,
                failed: Array.isArray(entry.failed) ? entry.failed : [],
              };
            });
          } else {
            historyEntries = [];
          }
        }
      } catch (error) {
        console.warn("히스토리 불러오기 실패", error);
        historyEntries = [];
      }
      historyEntries = historyEntries.slice(0, 50);
      renderHistory();
    };

    const addHistoryEntry = (data) => {
      const successCount = data.total - data.failed.length;
      const entry = {
        outputDir: data.output_dir,
        success: successCount,
        total: data.total,
        failed: data.failed,
        items: (data.completed_files || []).map((item) => normalizeCompletedItem(item)),
        transcripts: (data.transcripts || []).map((item) => normalizeTranscriptItem(item)),
        timestamp: Date.now(),
      };
      historyEntries.unshift(entry);
      historyEntries = historyEntries.slice(0, 50);
      saveHistory();
      renderHistory();
    };

    const pollProgress = (jobId) => {
      stopPolling();
      pollTimer = setInterval(async () => {
        try {
          const response = await fetch(`/api/progress/${jobId}`);
          if (!response.ok) {
            throw new Error("Progress polling failed");
          }
          const data = await response.json();
          progressWrapper.classList.remove("hidden");
          updateProgressUI(data);
          updateTranscriptStatus(data);

          if (data.status === "transcribing") {
            statusBox.textContent = "스크립트 추출 중...";
          } else if (data.status === "completed") {
            stopPolling();
            statusBox.textContent = "다운로드 완료!";
            addHistoryEntry(data);
            progressBar.style.width = "100%";
            progressText.textContent = `100% (${data.total}/${data.total}) 완료`;
          } else if (data.status === "error") {
            stopPolling();
            statusBox.textContent = data.error || "다운로드 중 오류가 발생했습니다.";
            updateTranscriptStatus({});  // hide
          }
        } catch (error) {
          stopPolling();
          statusBox.textContent = error.message;
          updateTranscriptStatus({});
        }
      }, 1500);
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      cancelAutoStart();
      stopPolling();
      resetProgress();
      statusBox.textContent = "다운로드 준비 중...";
      const payload = {
        urls: document.getElementById("urls").value,
        output: document.getElementById("output").value,
        audio_only: audioOnlyField.checked,
        quiet: document.getElementById("quiet").checked,
      };

      try {
        const response = await fetch("/api/download", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Download failed");
        }
        activeJobId = data.job_id;
        urlsField.value = "";
        progressWrapper.classList.remove("hidden");
        progressText.textContent = `0% (0/${data.total}) 대기 중`;
        pollProgress(data.job_id);
      } catch (error) {
        statusBox.textContent = error.message;
      }
    });

    urlsField.addEventListener("paste", () => {
      scheduleAutoStart();
    });

    urlsField.addEventListener("input", (event) => {
      if (!urlsField.value.trim()) {
        cancelAutoStart();
      }
    });

    const createHistoryElement = (entry) => {
      const hasFailure = Array.isArray(entry.failed) && entry.failed.length > 0;
      const wrapper = document.createElement("div");
      wrapper.className = hasFailure ? "history-entry warning" : "history-entry";
      const thumb = document.createElement("img");
      thumb.className = "history-thumb";
      thumb.loading = "lazy";
      const firstName = entry.items && entry.items.length ? entry.items[0].name : "thumbnail";
      thumb.alt = firstName || "thumbnail";
      thumb.src = getThumbnailSrc(entry);
      thumb.addEventListener("click", () => openModal(thumb.src));
      const content = document.createElement("div");
      content.className = "history-content";
      content.textContent = formatHistoryText(entry);
      wrapper.appendChild(thumb);
      wrapper.appendChild(content);
      return wrapper;
    };

    loadHistory();
    modalBackdrop.addEventListener("click", (event) => {
      if (event.target === modalBackdrop || event.target === modalImage) {
        closeModal();
      }
    });
    clearHistoryBtn.addEventListener("click", () => {
      if (!confirm("저장된 다운로드 기록을 모두 삭제할까요?")) return;
      historyEntries = [];
      saveHistory();
      renderHistory();
      statusBox.textContent = "기록을 초기화했습니다.";
    });
  </script>
</body>
</html>
"""


def _split_urls(url_blob: str) -> List[str]:
    return [item.strip() for item in url_blob.replace(",", "\n").splitlines() if item.strip()]


def _create_job(total: int, output_dir: Path, audio_only: bool) -> str:
    job_id = uuid.uuid4().hex
    job_payload: Dict[str, Any] = {
        "status": "pending",
        "total": total,
        "completed": 0,
        "current_progress": 0.0,
        "current_title": "",
        "current_url": "",
        "failed": [],
        "completed_files": [],
        "transcripts": [],
        "audio_only": audio_only,
        "transcript_total": 0,
        "transcript_completed": 0,
        "error": None,
        "output_dir": str(output_dir.resolve()),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job_payload
    return job_id


def _extract_fileinfo(info: dict) -> tuple[str | None, Path | None]:
    path_candidates = [
        info.get("_filename"),
        info.get("filepath"),
        info.get("filename"),
    ]
    for candidate in path_candidates:
        if candidate:
            candidate_path = Path(candidate)
            return candidate_path.name, candidate_path

    requested = info.get("requested_downloads") or []
    for item in requested:
        if not isinstance(item, dict):
            continue
        for key in ("filepath", "_filename", "filename"):
            candidate = item.get(key)
            if candidate:
                candidate_path = Path(candidate)
                return candidate_path.name, candidate_path

    title = info.get("title") or info.get("fulltitle")
    ext = info.get("ext")
    if title and ext:
        return f"{title}.{ext}", None
    return title, None


def _generate_thumbnail_data(video_path: Path) -> str | None:
    if not video_path.exists():
        return None


def _load_whisper_model():
    global WHISPER_MODEL
    if WHISPER_MODEL is not None:
        return WHISPER_MODEL
    try:
        import whisper
    except ImportError:
        app.logger.warning("Whisper 모델을 불러올 수 없습니다. `pip install openai-whisper` 실행 후 다시 시도하세요.")
        return None
    WHISPER_MODEL = whisper.load_model("base")
    return WHISPER_MODEL


def _transcribe_audio(file_path: Path) -> str | None:
    if not file_path.exists():
        return None
    model = _load_whisper_model()
    if model is None:
        return None
    try:
        result = model.transcribe(str(file_path), fp16=False)
    except Exception as exc:
        app.logger.warning("오디오 스크립트 생성 실패: %s", exc)
        return None
    text = (result.get("text") or "").strip()
    if not text:
        return None
    transcript_path = file_path.with_suffix(".txt")
    transcript_path.write_text(text, encoding="utf-8")
    return str(transcript_path)
    thumb_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            thumb_path = Path(tmp_file.name)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            "00:00:01",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=240:-1",
            str(thumb_path),
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if proc.returncode != 0 or not thumb_path.exists():
            if thumb_path:
                thumb_path.unlink(missing_ok=True)
            return None
        data = thumb_path.read_bytes()
        if thumb_path:
            thumb_path.unlink(missing_ok=True)
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        try:
            if thumb_path:
                thumb_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _progress_hook(job_id: str, data: dict) -> None:
    info = data.get("info_dict") or {}
    title = info.get("fulltitle") or info.get("title") or ""
    url = info.get("webpage_url") or info.get("original_url") or ""
    status = data.get("status")
    total_bytes = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
    downloaded_bytes = data.get("downloaded_bytes") or 0
    progress = downloaded_bytes / total_bytes if total_bytes else 0.0
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job["current_title"] = title
        job["current_url"] = url
        if status == "downloading":
            job["current_progress"] = progress
            if job["status"] == "pending":
                job["status"] = "running"
        elif status == "finished":
            job["current_progress"] = 1.0
            filename, file_path = _extract_fileinfo(info)
            if filename:
                thumbnail = info.get("thumbnail")
                if not thumbnail:
                    thumbnails = info.get("thumbnails")
                    if isinstance(thumbnails, list) and thumbnails:
                        thumbnail = thumbnails[-1].get("url")
                if not thumbnail and file_path:
                    thumbnail = _generate_thumbnail_data(file_path)
                job.setdefault("completed_files", []).append(
                    {"name": filename, "thumbnail": thumbnail, "path": str(file_path) if file_path else None}
                )


def _item_complete(job_id: str, _url: str, _success: bool) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job["completed"] = min(job["total"], job["completed"] + 1)
        job["current_progress"] = 0.0


def _run_download_job(
    job_id: str,
    urls: List[str],
    output_dir: Path,
    audio_only: bool,
    template: str | None,
    quiet: bool,
) -> None:
    try:
        failed = download_urls(
            urls=urls,
            output_dir=output_dir,
            audio_only=audio_only,
            filename_template=template,
            quiet=quiet,
            progress_hook=partial(_progress_hook, job_id),
            item_complete_hook=partial(_item_complete, job_id),
        )
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            job["failed"] = failed
            completed_files = list(job.get("completed_files", []))
            if audio_only and completed_files:
                job["status"] = "transcribing"
                job["transcript_total"] = len(completed_files)
                job["transcript_completed"] = 0
        transcripts: List[Dict[str, str]] = []
        if audio_only and completed_files:
            for file_info in completed_files:
                path_str = file_info.get("path")
                if not path_str:
                    continue
                transcript_file = _transcribe_audio(Path(path_str))
                if transcript_file:
                    transcripts.append(
                        {
                            "name": Path(transcript_file).name,
                            "path": transcript_file,
                            "source": file_info.get("name", ""),
                        }
                    )
                with JOBS_LOCK:
                    job = JOBS.get(job_id)
                    if job:
                        job["transcript_completed"] = len(transcripts)
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            if transcripts:
                job["transcripts"] = transcripts
            job["status"] = "completed"
            job["completed"] = job["total"]
            job["current_progress"] = 0.0
    except Exception as exc:  # pragma: no cover - runtime guardrail
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            job["status"] = "error"
            job["error"] = str(exc)


@app.get("/")
def index() -> str:
    return HTML_PAGE


@app.post("/api/download")
def api_download():
    payload = request.get_json(silent=True) or {}
    urls_blob = str(payload.get("urls", ""))
    urls = _split_urls(urls_blob)
    if not urls:
        return jsonify({"error": "At least one URL is required."}), 400

    output_dir = resolve_output_dir(payload.get("output") or None)
    template = payload.get("template") or None
    audio_only = bool(payload.get("audio_only"))
    quiet = bool(payload.get("quiet", True))

    job_id = _create_job(len(urls), output_dir, audio_only)
    thread = threading.Thread(
        target=_run_download_job,
        args=(job_id, urls, output_dir, audio_only, template, quiet),
        daemon=True,
    )
    thread.start()

    return jsonify(
        {
            "job_id": job_id,
            "total": len(urls),
            "output_dir": str(output_dir.resolve()),
        }
    )


@app.get("/api/progress/<job_id>")
def job_progress(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify({"error": "Unknown job id"}), 404
        snapshot = job.copy()
    total = snapshot.get("total", 0) or 0
    if total <= 0:
        progress_value = 0.0
    else:
        progress_value = (snapshot.get("completed", 0) + snapshot.get("current_progress", 0.0)) / total
    progress_value = max(0.0, min(1.0, progress_value))
    raw_completed = snapshot.get("completed_files", [])
    normalized_completed = []
    for item in raw_completed:
        if isinstance(item, dict):
            normalized_completed.append(
                {
                    "name": item.get("name") or "",
                    "thumbnail": item.get("thumbnail"),
                }
            )
        else:
            normalized_completed.append({"name": str(item), "thumbnail": None})
    raw_transcripts = snapshot.get("transcripts", [])
    normalized_transcripts = []
    for entry in raw_transcripts:
        if isinstance(entry, dict):
            normalized_transcripts.append(
                {
                    "name": entry.get("name") or "",
                    "source": entry.get("source") or "",
                    "path": entry.get("path"),
                }
            )
        else:
            normalized_transcripts.append({"name": str(entry), "source": "", "path": None})

    return jsonify(
        {
            "job_id": job_id,
            "status": snapshot.get("status"),
            "total": total,
            "completed": snapshot.get("completed", 0),
            "progress": progress_value,
            "current_title": snapshot.get("current_title", ""),
            "current_url": snapshot.get("current_url", ""),
            "failed": list(snapshot.get("failed", [])),
            "completed_files": normalized_completed,
            "transcripts": normalized_transcripts,
            "transcript_total": snapshot.get("transcript_total", 0),
            "transcript_completed": snapshot.get("transcript_completed", 0),
            "error": snapshot.get("error"),
            "output_dir": snapshot.get("output_dir"),
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=8080)
