# bengali_tts_engine.py  — ADAS Voice AI  (LOCAL-ONLY EDITION)
# ══════════════════════════════════════════════════════════════════
#  ALL TTS IS FULLY LOCAL — zero internet required after first run.
#
#  ENGINE CASCADE (tried in order):
#  1. facebook/mms-tts-ben  — VITS neural TTS, ~400 MB,
#                             16 kHz, excellent Bengali quality.
#                             Runs on CPU via PyTorch.
#  2. espeak-ng  (if installed)  — rule-based, very fast, basic quality
#                                  Linux:   sudo apt install espeak-ng
#                                  Windows: github.com/espeak-ng releases
#  3. pyttsx3  — system TTS, last resort, no real Bengali voice
#
#  WHAT WAS REMOVED vs cloud version:
#  ✗ edge-tts      (Microsoft Azure — internet)
#  ✗ gTTS          (Google TTS — internet)
#  ✗ Gemini TTS    (Google Gemini API — internet + API key)
#  ✗ pygame        (replaced by sounddevice already in project)
#  ✗ aiohttp/SSL patches  (no internet → no SSL needed)
#  ✗ asyncio persistent-loop manager (was only for edge-tts)
#
#  FIRST RUN: facebook/mms-tts-ben is downloaded once (~400 MB)
#             into ~/.cache/huggingface/hub/ and reused forever.
#  OFFLINE:   Set env var TRANSFORMERS_OFFLINE=1 to prevent any
#             network check once models are cached.
# ══════════════════════════════════════════════════════════════════

import os
import re
import threading
import time
import unicodedata
import warnings
import subprocess
from typing import Optional, List

import numpy as np
import sounddevice as sd

warnings.filterwarnings("ignore")

# ── Stop-event reference (injected by main.py) ─────────────────────
_stop_event_ref: Optional[threading.Event] = None


def set_stop_event(ev: threading.Event) -> None:
    global _stop_event_ref
    _stop_event_ref = ev


def _is_stopped() -> bool:
    return _stop_event_ref is not None and _stop_event_ref.is_set()


# ── Shared state (exported to main.py) ────────────────────────────
_tts_mode       = "none"          # updated once engine loads
_tts_sr         = 16000           # MMS sample rate
_tts_play_lock  = threading.Lock()
_is_tts_playing = threading.Event()

# ══════════════════════════════════════════════════════════════════
#  MMS-TTS  (facebook/mms-tts-ben)  — PRIMARY ENGINE
# ══════════════════════════════════════════════════════════════════
_mms_model        = None
_mms_tokenizer    = None
_mms_model_lock   = threading.Lock()   # serialise synthesis (CPU safety)
_mms_ready        = threading.Event()  # set once load attempt finishes
_mms_load_started = threading.Event()

_MMS_MODEL_NAME  = "facebook/mms-tts-ben"
_CHUNK_MAX_WORDS = 30               # words per synthesis chunk
_CHUNK_MIN_CHARS = 3                # skip very short fragments


def _load_mms() -> None:
    """Download (first run) or load MMS-TTS model from local cache."""
    global _mms_model, _mms_tokenizer, _tts_mode, _tts_sr
    try:
        # transformers + torch must be installed
        from transformers import VitsModel, AutoTokenizer  # type: ignore
        import torch  # noqa: F401

        print(f"[TTS] Loading {_MMS_MODEL_NAME}  "
              "(first run downloads ~400 MB — subsequent runs are instant)…")
        _mms_tokenizer = AutoTokenizer.from_pretrained(_MMS_MODEL_NAME)
        _mms_model     = VitsModel.from_pretrained(_MMS_MODEL_NAME)
        _mms_model.eval()

        _tts_mode = "mms"
        _tts_sr   = _mms_model.config.sampling_rate
        print(f"[TTS] ✅ MMS-TTS ready — {_MMS_MODEL_NAME}  "
              f"| sr={_tts_sr} Hz | CPU-only")
    except ImportError as ie:
        print(f"[TTS] ❌ transformers/torch missing: {ie}")
        print("      Fix:  pip install transformers torch sentencepiece")
        _try_fallback_engines()
    except Exception as exc:
        print(f"[TTS] ❌ MMS load failed: {exc}")
        _try_fallback_engines()
    finally:
        _mms_ready.set()


def _try_fallback_engines() -> None:
    """Try espeak-ng then pyttsx3 when MMS is unavailable."""
    global _tts_mode

    # espeak-ng ── very fast, zero dependencies, decent Bengali phonetics
    try:
        result = subprocess.run(
            ["espeak-ng", "--version"],
            capture_output=True, timeout=5, text=True
        )
        if result.returncode == 0:
            _tts_mode = "espeak"
            print("[TTS] ✅ espeak-ng ready as fallback")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # pyttsx3 ── last resort, system TTS, no real Bengali voice
    try:
        import pyttsx3  # noqa: F401
        _tts_mode = "pyttsx3"
        print("[TTS] ⚠️  pyttsx3 ready — last resort (no Bengali voice)")
    except ImportError:
        print("[TTS] ❌ No TTS engine available.")
        print("      Install MMS:     pip install transformers torch sentencepiece")
        print("      Install espeak:  sudo apt install espeak-ng  (Linux)")
        print("                       https://github.com/espeak-ng  (Windows)")


# ══════════════════════════════════════════════════════════════════
#  TEXT NORMALISATION & CHUNKING
# ══════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """NFC-normalise and strip invisible Unicode characters."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    # Remove zero-width characters that break Bengali conjuncts in TTS
    for zw in ('\u200C', '\u200D', '\u200B', '\uFEFF'):
        text = text.replace(zw, '')
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _split_chunks(text: str) -> List[str]:
    """
    Split on sentence-ending punctuation (। ? !) only — NEVER on commas
    because Bengali comma-like characters appear inside conjuncts.
    Each chunk is at most _CHUNK_MAX_WORDS words long.
    """
    if not text:
        return []

    raw_parts = re.split(r'(?<=[।?!])\s*', text)
    chunks: List[str] = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        words = part.split()
        for i in range(0, len(words), _CHUNK_MAX_WORDS):
            chunk = ' '.join(words[i: i + _CHUNK_MAX_WORDS])
            if chunk:
                chunks.append(chunk)

    # If no sentence boundary was found, treat whole text as one chunk
    if not chunks and text.strip():
        chunks = [text.strip()]

    return [c for c in chunks if len(c) >= _CHUNK_MIN_CHARS]


# ══════════════════════════════════════════════════════════════════
#  ENGINE IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════

# ── 1. MMS-TTS ─────────────────────────────────────────────────────

def _synthesize_mms_chunk(text: str) -> Optional[np.ndarray]:
    """
    Synthesise one text chunk with MMS-TTS.
    Returns float32 numpy array or None on failure.
    Thread-safe via _mms_model_lock.
    """
    if _mms_model is None or _mms_tokenizer is None:
        return None
    try:
        import torch
        with _mms_model_lock:
            inputs = _mms_tokenizer(
                text,
                return_tensors="pt",
                padding=True,
            )
            with torch.no_grad():
                output = _mms_model(**inputs)
            # waveform shape: (batch=1, time)
            waveform = output.waveform[0].squeeze().float().numpy()
        return waveform if len(waveform) > 0 else None
    except Exception as exc:
        print(f"[MMS synth] ❌ {exc} | text='{text[:40]}'")
        return None


def _play_mms(text_bn: str) -> None:
    """Full MMS-TTS pipeline: wait-for-ready → normalise → chunk → synthesise → play."""
    # Wait until model is ready (covers first-time download)
    if not _mms_ready.wait(timeout=300):
        print("[MMS] ⚠️  Model not ready after 5 min — skipping")
        return

    if _tts_mode != "mms":
        return

    normalized = _normalize(text_bn)
    if not normalized:
        return

    chunks = _split_chunks(normalized)
    if not chunks:
        return

    print(f"[MMS-TTS] Speaking {len(chunks)} chunk(s)…")
    for chunk in chunks:
        if _is_stopped():
            break
        audio = _synthesize_mms_chunk(chunk)
        if audio is not None:
            try:
                sd.play(audio, samplerate=_tts_sr)
                sd.wait()
            except Exception as exc:
                print(f"[MMS play] ❌ {exc}")
        else:
            print(f"[MMS] No audio for chunk: '{chunk[:40]}'")


# ── 2. espeak-ng ───────────────────────────────────────────────────

def _play_espeak(text_bn: str) -> None:
    """
    Speak Bengali text via espeak-ng.
    Requires espeak-ng to be installed and on PATH.
    """
    normalized = _normalize(text_bn)
    if not normalized:
        return
    chunks = _split_chunks(normalized)
    for chunk in chunks:
        if _is_stopped():
            break
        try:
            subprocess.run(
                ["espeak-ng", "-v", "bn", "-s", "125", "--ipa=0", chunk],
                timeout=30,
                capture_output=True,
            )
        except FileNotFoundError:
            print("[espeak] ❌ espeak-ng not found on PATH")
            break
        except subprocess.TimeoutExpired:
            print(f"[espeak] ⚠️  Timeout on chunk: '{chunk[:40]}'")
        except Exception as exc:
            print(f"[espeak] ❌ {exc}")


# ── 3. pyttsx3 (last resort) ───────────────────────────────────────

def _play_pyttsx3(text_bn: str) -> None:
    """System TTS via pyttsx3. No Bengali voice on most systems."""
    try:
        import pyttsx3  # noqa: F811
        eng = pyttsx3.init()
        eng.setProperty("rate", 150)
        eng.say(text_bn)
        eng.runAndWait()
    except Exception as exc:
        print(f"[pyttsx3] ❌ {exc}")


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API  (imported by main.py)
# ══════════════════════════════════════════════════════════════════

def speak_bengali_blocking(text_bn: str) -> None:
    """
    Synthesise and play Bengali text.
    Blocks until playback is complete.
    Thread-safe: only one utterance plays at a time.
    """
    if not text_bn or not text_bn.strip():
        return
    if _tts_mode == "none":
        print(f"[TTS] No engine loaded — cannot speak: '{text_bn[:40]}'")
        return

    _is_tts_playing.set()
    try:
        with _tts_play_lock:
            if _tts_mode == "mms":
                _play_mms(text_bn)
            elif _tts_mode == "espeak":
                _play_espeak(text_bn)
            elif _tts_mode == "pyttsx3":
                _play_pyttsx3(text_bn)
            else:
                print(f"[TTS] Unknown mode: {_tts_mode!r}")
    finally:
        _is_tts_playing.clear()


def preload_model_async() -> None:
    """
    Kick off MMS model loading in a background thread.
    Call this once at startup so the model is ready before the first utterance.
    Non-blocking — returns immediately.
    """
    if not _mms_load_started.is_set():
        _mms_load_started.set()
        t = threading.Thread(target=_load_mms, daemon=True, name="mms_loader")
        t.start()
    print(f"[TTS] Mode  : {_tts_mode}  (MMS loading in background…)")
    print(f"[TTS] Voice : {_MMS_MODEL_NAME}")
    print(f"[TTS] SR    : {_tts_sr} Hz")


# Auto-start model loading when module is imported
preload_model_async()
