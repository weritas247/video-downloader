#!/usr/bin/env python3
"""Web UI for downloader.py built with Flask."""

from __future__ import annotations

import threading
import uuid
import base64
import subprocess
import tempfile
import time
from functools import partial
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, abort, jsonify, request, send_from_directory

from downloader import download_urls, resolve_output_dir
from transcription import transcribe_audio

app = Flask(__name__)

JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
SOUND_DIR = Path(__file__).resolve().parent / "sound"


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
    textarea, input, select { width: 100%; padding: 0.75rem; border: 1px solid var(--panel-border); border-radius: 8px; background: var(--panel); color: var(--text); }
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
    #history { margin-top: 1rem; display: flex; flex-direction: column; gap: 1rem; }
    .history-entry {
      position: relative;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.04);
      border-radius: 22px;
      padding: 1.1rem;
      display: flex;
      gap: 1rem;
      align-items: flex-start;
      border: 1px solid rgba(255, 255, 255, 0.04);
      box-shadow: 0 12px 30px rgba(5, 5, 10, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.04);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .history-entry::before {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
      opacity: 0.6;
      pointer-events: none;
    }
    .history-entry:hover {
      transform: translateY(-6px);
      box-shadow: 0 15px 32px rgba(5, 5, 10, 0.55);
    }
    .history-entry.warning {
      border: 1px solid rgba(255, 107, 107, 0.3);
      box-shadow: 0 15px 32px rgba(255, 107, 107, 0.25);
    }
    .history-thumb {
      width: 110px;
      height: 62px;
      border-radius: 16px;
      object-fit: cover;
      background: #0f111c;
      flex-shrink: 0;
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: inset 0 1px 2px rgba(255,255,255,0.05);
      cursor: pointer;
    }
    .history-content {
      flex: 1;
      white-space: pre-wrap;
      position: relative;
      z-index: 1;
      line-height: 1.45;
    }
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
      <div class="options">
        <label class="checkbox-pill"><input id="audio-only" type="checkbox" /> 스크립트 추출 (MP4 + MP3 + 자막)</label>
        <label class="checkbox-pill"><input id="quiet" type="checkbox" checked /> Quiet mode</label>
      </div>
      <div class="form-group" id="transcript-format-group">
        <label for="transcript-format">스크립트 파일 형식</label>
        <select id="transcript-format">
          <option value="srt" selected>자막 (.srt)</option>
          <option value="txt">텍스트 (.txt)</option>
        </select>
        <small>스크립트를 추출하는 경우, 생성할 파일 형식을 선택하세요.</small>
      </div>
      <div class="form-group" id="transcript-language-group">
        <label for="transcript-language">스크립트 언어</label>
        <select id="transcript-language">
          <option value="auto" selected>자동 감지</option>
          <option value="ko">한국어 고정</option>
          <option value="en">영어 고정</option>
        </select>
        <small>특정 언어로 강제 추출하고 싶을 때 선택하세요.</small>
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
    const transcriptFormatField = document.getElementById("transcript-format");
    const transcriptFormatGroup = document.getElementById("transcript-format-group");
    const transcriptLanguageField = document.getElementById("transcript-language");
    const transcriptLanguageGroup = document.getElementById("transcript-language-group");
    const modalBackdrop = document.getElementById("modal-backdrop");
    const modalImage = document.getElementById("modal-image");
    const urlsField = document.getElementById("urls");
    const progressWrapper = document.getElementById("progress-wrapper");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const transcriptStatus = document.getElementById("transcript-status");
    const PLACEHOLDER_THUMB = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="120" height="68" viewBox="0 0 120 68"%3E%3Crect width="120" height="68" rx="8" fill="%232d334a"/%3E%3Cpath d="M48 22l26 12-26 12z" fill="%235a8dee"/%3E%3C/svg%3E';
    const createSound = (path) => {
      const audio = new Audio(path);
      audio.preload = "auto";
      audio.crossOrigin = "anonymous";
      return audio;
    };
    const playSound = (audio) => {
      if (!audio) return;
      try {
        audio.currentTime = 0;
        const playPromise = audio.play();
        if (playPromise && typeof playPromise.catch === "function") {
          playPromise.catch(() => {});
        }
      } catch (error) {
        console.warn("사운드 재생 실패", error);
      }
    };
    const downloadSuccessSound = createSound("/sound/download_success.mp3");
    const downloadFailSound = createSound("/sound/downalod_fail.mp3");
    const transcriptSuccessSound = createSound("/sound/transscript_success.mp3");
    const transcriptFailSound = createSound("/sound/transscript_fail.mp3");
    audioOnlyField.checked = false;

    const formatEta = (ms) => {
      if (!Number.isFinite(ms) || ms <= 0) return "";
      const totalSeconds = Math.round(ms / 1000);
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = totalSeconds % 60;
      if (minutes > 0) {
        return `${minutes}분 ${seconds}초`;
      }
      return `${seconds}초`;
    };

    const updateTranscriptFormatVisibility = () => {
      if (!transcriptFormatGroup) return;
      if (audioOnlyField.checked) {
        transcriptFormatGroup.classList.remove("hidden");
        if (transcriptLanguageGroup) {
          transcriptLanguageGroup.classList.remove("hidden");
        }
      } else {
        transcriptFormatGroup.classList.add("hidden");
        if (transcriptLanguageGroup) {
          transcriptLanguageGroup.classList.add("hidden");
        }
      }
    };
    updateTranscriptFormatVisibility();

    let pollTimer = null;
    let activeJobId = null;
    let autoStartTimer = null;
    let historyEntries = [];
    let transcriptStartTimestamp = null;
    let downloadSoundPlayed = false;
    let downloadFailSoundPlayed = false;
    let transcriptSoundPlayed = false;
    let transcriptFailSoundPlayed = false;

    const resetProgress = () => {
      progressBar.style.width = "0%";
      progressText.textContent = "";
      progressWrapper.classList.add("hidden");
      activeJobId = null;
      downloadSoundPlayed = false;
      downloadFailSoundPlayed = false;
      transcriptSoundPlayed = false;
      transcriptFailSoundPlayed = false;
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
        if (typeof data.transcript_started_at === "number" && data.transcript_started_at > 0) {
          transcriptStartTimestamp = data.transcript_started_at * 1000;
        }
        transcriptStatus.classList.remove("hidden");
        let message = total
          ? `스크립트 추출 중... (${done}/${total})`
          : "스크립트 추출 중...";
        const remaining = total - done;
        if (transcriptStartTimestamp && done > 0 && remaining > 0) {
          const elapsed = Date.now() - transcriptStartTimestamp;
          if (elapsed > 0) {
            const perItem = elapsed / done;
            const etaMs = perItem * remaining;
            const etaText = formatEta(etaMs);
            if (etaText) {
              message += ` · 예상 남은 시간: 약 ${etaText}`;
            }
          }
        }
        transcriptStatus.textContent = message;
      } else {
        transcriptStatus.classList.add("hidden");
        transcriptStatus.textContent = "";
        transcriptStartTimestamp = null;
      }
    };

    const formatHistoryText = (entry) => {
      const filenames = Array.isArray(entry.items) && entry.items.length
        ? entry.items.map((item) => item.name || "(파일명 정보 없음)")
        : ["(파일명 정보 없음)"];
      const transcripts = Array.isArray(entry.transcripts) ? entry.transcripts : [];
      const transcriptErrors = Array.isArray(entry.transcriptErrors) ? entry.transcriptErrors : [];
      const timestamp = entry.timestamp || Date.now();
      const lines = [
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
      if (transcriptErrors.length) {
        lines.push("스크립트 실패:");
        transcriptErrors.forEach((err) => {
          const label = err.file ? `${err.file}: ${err.error}` : err.error;
          lines.push(`- ${label}`);
        });
      }
      return {
        body: lines.join("\\n"),
        timestampLabel: `완료 시각: ${new Date(timestamp).toLocaleString()}`,
      };
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
              const transcriptErrors = Array.isArray(entry.transcriptErrors)
                ? entry.transcriptErrors
                : [];
              return {
                ...entry,
                items,
                transcripts,
                transcriptErrors,
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
        transcriptErrors: Array.isArray(data.transcript_errors) ? data.transcript_errors : [],
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

          if (data.status === "reencoding") {
            const done = data.reencode_completed || 0;
            const total = data.reencode_total || 0;
            const progressLabel = total ? ` (${done}/${total})` : "";
            statusBox.textContent = `릴스 호환성 변환 중${progressLabel}`;
          } else if (data.status === "transcribing") {
            statusBox.textContent = "스크립트 추출 중...";
          } else if (data.status === "completed_with_warnings") {
            stopPolling();
            statusBox.textContent = "다운로드 완료 (스크립트 에러 확인 필요)";
            addHistoryEntry(data);
            progressBar.style.width = "100%";
            progressText.textContent = `100% (${data.total}/${data.total}) 완료`;
            if (!downloadSoundPlayed) {
              downloadSoundPlayed = true;
              playSound(downloadSuccessSound);
            }
          } else if (data.status === "completed") {
            stopPolling();
            statusBox.textContent = "다운로드 완료!";
            addHistoryEntry(data);
            progressBar.style.width = "100%";
            progressText.textContent = `100% (${data.total}/${data.total}) 완료`;
            if (!downloadSoundPlayed) {
              downloadSoundPlayed = true;
              playSound(downloadSuccessSound);
            }
          } else if (data.status === "error") {
            stopPolling();
            statusBox.textContent = data.error || "다운로드 중 오류가 발생했습니다.";
            updateTranscriptStatus({});  // hide
            if (!downloadFailSoundPlayed) {
              downloadFailSoundPlayed = true;
              playSound(downloadFailSound);
            }
          }
          if (
            !transcriptSoundPlayed &&
            data.transcript_total > 0 &&
            data.transcript_completed >= data.transcript_total &&
            data.status !== "transcribing" &&
            (!data.transcript_errors || data.transcript_errors.length === 0)
          ) {
            transcriptSoundPlayed = true;
            playSound(transcriptSuccessSound);
          }
          if (
            !transcriptFailSoundPlayed &&
            Array.isArray(data.transcript_errors) &&
            data.transcript_errors.length > 0 &&
            data.status !== "transcribing"
          ) {
            transcriptFailSoundPlayed = true;
            playSound(transcriptFailSound);
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
        audio_only: audioOnlyField.checked,
        quiet: document.getElementById("quiet").checked,
        transcript_format: audioOnlyField.checked ? transcriptFormatField.value : null,
        transcript_language: audioOnlyField.checked ? transcriptLanguageField.value : null,
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

    audioOnlyField.addEventListener("change", () => {
      updateTranscriptFormatVisibility();
      if (!audioOnlyField.checked && transcriptStatus) {
        transcriptStatus.classList.add("hidden");
        transcriptStatus.textContent = "";
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
      const { body, timestampLabel } = formatHistoryText(entry);
      const textWrapper = document.createElement("div");
      textWrapper.textContent = body;
      const timestampEl = document.createElement("div");
      timestampEl.textContent = timestampLabel;
      timestampEl.style.fontSize = "0.75rem";
      timestampEl.style.color = "rgba(255,255,255,0.55)";
      timestampEl.style.position = "absolute";
      timestampEl.style.top = "0.75rem";
      timestampEl.style.right = "1rem";
      content.appendChild(textWrapper);
      content.appendChild(timestampEl);
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


def _create_job(
    total: int,
    output_dir: Path,
    audio_only: bool,
    transcript_format: str | None,
    transcript_language: str | None,
) -> str:
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
        "transcript_started_at": None,
        "error": None,
        "output_dir": str(output_dir.resolve()),
        "transcript_format": transcript_format,
        "transcript_language": transcript_language,
        "reencode_h264": False,
        "reencode_total": 0,
        "reencode_completed": 0,
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


def _is_instagram_path(path: Path, output_dir: Path) -> bool:
    try:
        rel = path.resolve().relative_to(output_dir.resolve())
    except Exception:
        parts = [part.lower() for part in path.parts]
        return "instagram" in parts
    if not rel.parts:
        return False
    return rel.parts[0].lower() == "instagram"


def _reencode_video_to_h264(video_path: Path) -> bool:
    """Re-encode a video in-place to H.264 for broader compatibility."""
    if not video_path.exists():
        return False
    if video_path.suffix.lower() != ".mp4":
        return False

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            prefix=f"{video_path.stem}_h264_",
            dir=str(video_path.parent),
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
    except Exception:
        return False

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(temp_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if proc.returncode != 0 or not temp_path.exists():
            temp_path.unlink(missing_ok=True)
            return False
        video_path.unlink(missing_ok=True)
        temp_path.replace(video_path)
        return True
    except Exception as exc:
        app.logger.warning("릴스 호환성 변환 실패 (%s): %s", video_path, exc)
        if temp_path:
            temp_path.unlink(missing_ok=True)
        return False


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
    transcript_format: str | None,
    transcript_language: str | None,
) -> None:
    try:
        failed = download_urls(
            urls=urls,
            output_dir=output_dir,
            audio_only=audio_only,
            filename_template=template,
            quiet=quiet,
            keep_video_when_audio_only=audio_only,
            progress_hook=partial(_progress_hook, job_id),
            item_complete_hook=partial(_item_complete, job_id),
        )
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            job["failed"] = failed
            completed_files = list(job.get("completed_files", []))

        reencode_targets: List[tuple[dict, Path]] = []
        if not audio_only and completed_files:
            for file_info in completed_files:
                path_str = file_info.get("path")
                if not path_str:
                    continue
                candidate = Path(path_str)
                if (
                    candidate.exists()
                    and candidate.suffix.lower() == ".mp4"
                    and _is_instagram_path(candidate, output_dir)
                ):
                    reencode_targets.append((file_info, candidate))
        if reencode_targets:
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if job:
                    job["status"] = "reencoding"
                    job["reencode_total"] = len(reencode_targets)
                    job["reencode_completed"] = 0
                    job["reencode_h264"] = True
            for idx, (file_info, target_path) in enumerate(reencode_targets, start=1):
                _reencode_video_to_h264(target_path)
                file_info["path"] = str(target_path)
                with JOBS_LOCK:
                    job = JOBS.get(job_id)
                    if job:
                        job["reencode_completed"] = idx

        if audio_only and completed_files:
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if job:
                    job["status"] = "transcribing"
                    job["transcript_total"] = len(completed_files)
                    job["transcript_completed"] = 0
                    job["transcript_started_at"] = time.time()
        transcripts: List[Dict[str, str]] = []
        if audio_only and completed_files:
            for file_info in completed_files:
                path_str = file_info.get("path")
                target_path = None
                if path_str:
                    candidate = Path(path_str)
                    if candidate.exists():
                        target_path = candidate
                    else:
                        alt = candidate.with_suffix(".mp3")
                        if alt.exists():
                            target_path = alt
                if target_path is None:
                    filename = file_info.get("name") or ""
                    if filename:
                        direct = output_dir / filename
                        if direct.exists():
                            target_path = direct
                        else:
                            alt = direct.with_suffix(".mp3")
                            if alt.exists():
                                target_path = alt
                if target_path is None or not target_path.exists():
                    continue
                file_info["path"] = str(target_path)
                try:
                    transcript_path = transcribe_audio(
                        target_path,
                        transcript_format=transcript_format or "srt",
                        language=transcript_language,
                    )
                except RuntimeError as exc:
                    with JOBS_LOCK:
                        job = JOBS.get(job_id)
                        if job:
                            job["status"] = "error"
                            job["error"] = f"Whisper 모델 로딩 실패: {exc}"
                    return
                except Exception as exc:  # pragma: no cover - runtime guardrail
                    app.logger.warning("오디오 스크립트 생성 실패 (%s): %s", target_path, exc)
                    with JOBS_LOCK:
                        job = JOBS.get(job_id)
                        if job:
                            job.setdefault("transcript_errors", []).append(
                                {"file": str(target_path), "error": str(exc)}
                            )
                    continue
                if transcript_path:
                    transcripts.append(
                        {
                            "name": Path(transcript_path).name,
                            "path": str(transcript_path),
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
            if "transcript_errors" in job and job["transcript_errors"]:
                job["status"] = "completed_with_warnings"
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


@app.get("/sound/<path:filename>")
def sound_file(filename: str):
    target = SOUND_DIR / filename
    if not target.exists() or not target.is_file():
        abort(404)
    return send_from_directory(SOUND_DIR, filename)


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
    if audio_only:
        transcript_format = str(payload.get("transcript_format") or "srt").lower()
        if transcript_format not in {"txt", "srt"}:
            return jsonify({"error": "Unsupported script format."}), 400
        raw_language = str(payload.get("transcript_language") or "auto").lower()
        if raw_language not in {"auto", "ko", "en"}:
            return jsonify({"error": "Unsupported language option."}), 400
        transcript_language = None if raw_language == "auto" else raw_language
    else:
        transcript_format = None
        transcript_language = None

    job_id = _create_job(
        len(urls),
        output_dir,
        audio_only,
        transcript_format,
        transcript_language,
    )
    thread = threading.Thread(
        target=_run_download_job,
        args=(
            job_id,
            urls,
            output_dir,
            audio_only,
            template,
            quiet,
            transcript_format,
            transcript_language,
        ),
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
    transcript_errors = []
    for entry in snapshot.get("transcript_errors", []):
        if isinstance(entry, dict):
            transcript_errors.append(
                {"file": entry.get("file") or "", "error": entry.get("error") or ""}
            )
        else:
            transcript_errors.append({"file": "", "error": str(entry)})

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
            "transcript_started_at": snapshot.get("transcript_started_at"),
            "transcript_errors": transcript_errors,
            "transcript_language": snapshot.get("transcript_language"),
            "reencode_total": snapshot.get("reencode_total", 0),
            "reencode_completed": snapshot.get("reencode_completed", 0),
            "reencode_h264": snapshot.get("reencode_h264", False),
            "error": snapshot.get("error"),
            "output_dir": snapshot.get("output_dir"),
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=8080)
