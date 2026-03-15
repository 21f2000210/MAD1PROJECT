# ADAS VOICE AI  — BENGALI EDITION  ⚡  LOCAL-ONLY EDITION
# ══════════════════════════════════════════════════════════════════
#
#  WHAT CHANGED vs cloud version
#  ─────────────────────────────────────────────────────────────────
#  TRANSLATION  (was: 3 internet APIs in parallel race)
#  ✗ deep_translator  → Google Translate API  (internet)
#  ✗ MyMemory API     → api.mymemory.translated.net  (internet)
#  ✗ LibreTranslate   → libretranslate.de / argosopentech.com  (internet)
#
#  ✅ facebook/nllb-200-distilled-600M  — local HuggingFace model
#     • ~1.2 GB, downloaded ONCE into ~/.cache/huggingface/hub/
#     • Runs entirely on CPU  (torch, sentencepiece)
#     • ~1-3 s / sentence on a modern laptop CPU
#     • Thread-safe via _nllb_lock
#     • Loaded in a background thread so UI starts instantly
#
#  TTS  (was: edge-tts / gTTS / Gemini — all internet)
#  ✅ facebook/mms-tts-ben — see bengali_tts_engine.py
#
#  EVERYTHING ELSE is unchanged:
#  ✅ faster-whisper STT        — already local
#  ✅ Ollama LLM                — already local
#  ✅ FAISS VectorDB            — already local
#  ✅ sentence-transformers     — already local
#
#  FIRST RUN (internet needed ONCE to download models):
#     python download_models.py
#  After that, set:
#     $env:TRANSFORMERS_OFFLINE = "1"   # Windows PowerShell
#     export TRANSFORMERS_OFFLINE=1     # Linux / macOS
#  and everything works with the network cable unplugged.
# ══════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import scrolledtext
import threading
import os
import time
import json
import queue
import collections
import warnings
import hashlib
import re
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, Future

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import requests

warnings.filterwarnings("ignore")

# Silence urllib3 SSL warnings (Ollama localhost still uses http)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════
SAMPLE_RATE          = 16000
FRAME                = 512
SILENCE_LIVE         = 0.6
SILENCE_CMD          = 0.45
ENERGY_THRESH        = 0.008

OLLAMA_URL           = "http://localhost:11434"
OLLAMA_MODEL         = "gemma2b"
MAX_TOKENS           = 120
TEMPERATURE          = 0.3

CPU_CORES            = os.cpu_count() or 4

BENGALI_WHISPER_PATH = "./arijitx-whisper-small-bn-ct2"
USE_BENGALI_WHISPER  = os.path.exists(BENGALI_WHISPER_PATH)

VECTORDB_DIR         = "faiss_store"
VECTORDB_INDEX       = f"{VECTORDB_DIR}/chat.index"
VECTORDB_META        = f"{VECTORDB_DIR}/metadata.json"
VECTORDB_DIM         = 384
HIT_THRESHOLD        = 0.72
PARTIAL_THRESH       = 0.52

TRANS_CACHE_SIZE     = 500
# Local NLLB is slower than a network call; give it more time
TRANS_TIMEOUT        = 20

_N_STT_WORKERS       = 2
_N_LLM_WORKERS       = 1
# Local model is serialised via lock; 2 workers is plenty
_N_TRANS_WORKERS     = 2
_N_IO_WORKERS        = 6

# ══════════════════════════════════════════════════════════════════
#  OLLAMA AUTO-DETECT
# ══════════════════════════════════════════════════════════════════
_MODEL_PRIORITY = [
    "gemma2b", "gemma2:2b", "gemma:2b", "gemma2",
    "llama3.2:1b", "llama3.2:3b", "llama3.2",
    "llama3:8b", "llama3", "mistral", "phi3",
    "tinyllama", "llama2",
]


def _detect_ollama_model() -> str:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if not r.ok:
            return ""
        models = [m["name"] for m in r.json().get("models", [])]
        if not models:
            print("⚠️  No Ollama models found.  Run: ollama pull gemma2:2b")
            return ""
        print(f"📦 Ollama models: {models}")
        for pref in _MODEL_PRIORITY:
            for m in models:
                if pref.lower() in m.lower():
                    print(f"✅ Selected model: {m}")
                    return m
        print(f"✅ Using: {models[0]}")
        return models[0]
    except Exception as e:
        print(f"⚠️  Ollama unreachable: {e}")
        return ""


# ══════════════════════════════════════════════════════════════════
#  INTENT DETECTION
# ══════════════════════════════════════════════════════════════════
_BN_Q = re.compile(
    r"(কি\b|কী\b|কে\b|কোথায়|কখন|কেন|কীভাবে|কিভাবে|"
    r"কতটুকু|কতটা|কত\b|কোন\b|কোনটি|"
    r"বলো|বলুন|বলতে পারো|বলতে পারেন|"
    r"ব্যাখ্যা|সংজ্ঞা|মানে|কাকে বলে|"
    r"কি জিনিস|কি ধরন|কীভাবে কাজ|"
    r"আবহাওয়া|তাপমাত্রা|বৃষ্টি|রোদ|ঝড়|"
    r"তুমি কি|আপনি কি|তুমি কে|আপনি কে)",
    re.UNICODE,
)
_BN_CO = re.compile(
    r"(চালিয়ে যাও|আরো বলো|আরও বলো|পরবর্তী|চলতে থাকো)",
    re.UNICODE,
)
_BN_SU = re.compile(
    r"(সারসংক্ষেপ|সারাংশ|সংক্ষেপ|সারমর্ম|মূল বিষয়)",
    re.UNICODE,
)
_BN_SC = re.compile(
    r"(রিমাইন্ডার|মনে করিয়ে দাও|মনে করিয়ে দিন|"
    r"মিটিং সেট|অ্যাপয়েন্টমেন্ট|অ্যালার্ম সেট|"
    r"\d+টায়\s*(মিটিং|কল|অ্যাপয়েন্টমেন্ট))",
    re.UNICODE,
)
_EN_Q  = re.compile(
    r"^(who|what|where|when|why|how|did|does|is|are|was|were|can|could|"
    r"should|would|will|tell me|explain|describe|define|weather|temperature)",
    re.I,
)
_EN_CO = re.compile(r"\b(continue|next|go on|keep going|carry on|more)\b", re.I)
_EN_SU = re.compile(r"\b(summary|summarize|recap|overview|key points)\b", re.I)
_EN_SC = re.compile(r"\b(remind me|set reminder|schedule meeting|set alarm)\b", re.I)


def get_intent(text_bn: str, text_en: str = "") -> str:
    if _BN_CO.search(text_bn): return "continue"
    if _BN_SU.search(text_bn): return "summary"
    if _BN_SC.search(text_bn): return "schedule"
    if _BN_Q.search(text_bn):  return "question"
    if text_en:
        if _EN_CO.search(text_en): return "continue"
        if _EN_SU.search(text_en): return "summary"
        if _EN_SC.search(text_en): return "schedule"
        if _EN_Q.match(text_en):   return "question"
    if text_bn.rstrip().endswith("?"): return "question"
    if 2 <= len(text_bn.split()) <= 12: return "question"
    return "transcribe"


# ══════════════════════════════════════════════════════════════════
#  LOCAL TRANSLATION  —  facebook/nllb-200-distilled-600M
# ══════════════════════════════════════════════════════════════════
#
#  Replaces: deep_translator (Google), MyMemory API, LibreTranslate.
#  All three were internet-only.  NLLB runs 100 % locally on CPU.
#
#  Language codes:
#    Bengali → "ben_Beng"
#    English → "eng_Latn"
#
#  Speed (CPU, modern laptop):  ~1-3 s per sentence first call;
#                                cached on subsequent identical calls.
#  Memory: ~1.2 GB RAM once loaded.
# ══════════════════════════════════════════════════════════════════

_NLLB_MODEL_NAME   = "facebook/nllb-200-distilled-600M"
_nllb_model        = None
_nllb_tokenizer    = None
_nllb_lock         = threading.Lock()   # single-thread CPU inference
_nllb_ready        = threading.Event()  # set after load attempt finishes
_nllb_load_started = threading.Event()

_trans_cache_bn2en: collections.OrderedDict = collections.OrderedDict()
_trans_cache_en2bn: collections.OrderedDict = collections.OrderedDict()
_trans_lock        = threading.Lock()
_translation_available = False


def _load_nllb() -> None:
    """
    Download (once) or load NLLB-200 from local HuggingFace cache.
    Runs in a background thread — UI is not blocked on startup.
    """
    global _nllb_model, _nllb_tokenizer, _translation_available
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore
        import torch  # noqa: F401

        print(f"[TRANS] Loading {_NLLB_MODEL_NAME}  "
              "(first run downloads ~1.2 GB — subsequent runs are instant)…")
        _nllb_tokenizer = AutoTokenizer.from_pretrained(_NLLB_MODEL_NAME)
        _nllb_model     = AutoModelForSeq2SeqLM.from_pretrained(_NLLB_MODEL_NAME)
        _nllb_model.eval()
        _translation_available = True
        print("[TRANS] ✅ NLLB-200 ready — fully local, CPU-only")
    except ImportError as ie:
        print(f"[TRANS] ❌ Missing packages: {ie}")
        print("         Fix: pip install transformers torch sentencepiece sacremoses")
    except Exception as exc:
        print(f"[TRANS] ❌ NLLB load failed: {exc}")
        print("         Bengali-direct mode will be used as fallback.")
    finally:
        _nllb_ready.set()


def _start_nllb_loader() -> None:
    if not _nllb_load_started.is_set():
        _nllb_load_started.set()
        threading.Thread(target=_load_nllb, daemon=True,
                         name="nllb_loader").start()


# Kick off model loading immediately at import time
_start_nllb_loader()


def _translate_nllb(text: str, src_lang: str, tgt_lang: str) -> str:
    """
    Core NLLB translation call — thread-safe via _nllb_lock.
    Returns empty string on any failure.
    """
    if _nllb_model is None or _nllb_tokenizer is None:
        return ""
    try:
        import torch
        with _nllb_lock:
            _nllb_tokenizer.src_lang = src_lang
            inputs = _nllb_tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            forced_bos = _nllb_tokenizer.convert_tokens_to_ids(tgt_lang)
            with torch.no_grad():
                tokens = _nllb_model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos,
                    max_new_tokens=256,
                    num_beams=2,           # lower = faster on CPU
                    early_stopping=True,
                )
            result = _nllb_tokenizer.batch_decode(
                tokens, skip_special_tokens=True
            )[0].strip()
        return result
    except Exception as exc:
        print(f"[NLLB] ❌ {exc}")
        return ""


def _ckey(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()[:16]


def translate_bn_to_en(text: str) -> str:
    global _translation_available
    k = _ckey(text)

    # 1. Cache hit
    with _trans_lock:
        if k in _trans_cache_bn2en:
            _trans_cache_bn2en.move_to_end(k)
            return _trans_cache_bn2en[k]

    # 2. If model still loading, fall back to Bengali-direct mode this round
    if not _nllb_ready.is_set():
        print("[BN→EN] NLLB still loading — Bengali-direct mode this round")
        return ""

    t0     = time.monotonic()
    result = _translate_nllb(text, "ben_Beng", "eng_Latn")
    ms     = (time.monotonic() - t0) * 1000

    if result and result.strip() != text.strip():
        _translation_available = True
        print(f"[BN→EN {ms:.0f}ms] '{text[:35]}' → '{result[:35]}'")
        with _trans_lock:
            _trans_cache_bn2en[k] = result
            _trans_cache_bn2en.move_to_end(k)
            if len(_trans_cache_bn2en) > TRANS_CACHE_SIZE:
                _trans_cache_bn2en.popitem(last=False)
        return result

    print(f"[BN→EN FAILED {ms:.0f}ms] '{text[:35]}'")
    return ""


def translate_en_to_bn(text: str) -> str:
    global _translation_available
    k = _ckey(text)

    # 1. Cache hit
    with _trans_lock:
        if k in _trans_cache_en2bn:
            _trans_cache_en2bn.move_to_end(k)
            return _trans_cache_en2bn[k]

    # 2. If model still loading, skip
    if not _nllb_ready.is_set():
        print("[EN→BN] NLLB still loading — skipping this translation")
        return ""

    t0     = time.monotonic()
    result = _translate_nllb(text, "eng_Latn", "ben_Beng")
    ms     = (time.monotonic() - t0) * 1000

    if result and result.strip() != text.strip():
        _translation_available = True
        print(f"[EN→BN {ms:.0f}ms] '{text[:35]}' → '{result[:35]}'")
        with _trans_lock:
            _trans_cache_en2bn[k] = result
            _trans_cache_en2bn.move_to_end(k)
            if len(_trans_cache_en2bn) > TRANS_CACHE_SIZE:
                _trans_cache_en2bn.popitem(last=False)
        return result

    print(f"[EN→BN FAILED {ms:.0f}ms] '{text[:35]}'")
    return ""


def is_bad_answer(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return True
    bad = [
        "could not generate", "i could not", "cannot generate",
        "error:", "[error", "ollama offline", "not found for url",
        "দুঃখিত, এই প্রশ্নের উত্তর এখন দিতে পারছি না",
    ]
    tl = text.lower()
    return any(p in tl for p in bad)


# ══════════════════════════════════════════════════════════════════
#  TTS  —  Import from local bengali_tts_engine
# ══════════════════════════════════════════════════════════════════
from bengali_tts_engine import (
    speak_bengali_blocking,
    preload_model_async,
    _is_tts_playing,
    _tts_play_lock,
    _tts_mode,
    set_stop_event as _tts_set_stop_event,
)

_trans_pool     = ThreadPoolExecutor(max_workers=_N_TRANS_WORKERS,
                                     thread_name_prefix="trans")
_tts_synth_pool = ThreadPoolExecutor(max_workers=2,
                                     thread_name_prefix="tts_synth")

# ══════════════════════════════════════════════════════════════════
#  GLOBALS
# ══════════════════════════════════════════════════════════════════
live_q      = queue.Queue(maxsize=10)
cmd_q       = queue.Queue(maxsize=4)
tts_q       = queue.Queue(maxsize=20)
stop_event  = threading.Event()
live_active = threading.Event()
cmd_mode    = threading.Event()
cmd_busy    = threading.Event()

_tts_set_stop_event(stop_event)

executor  = ThreadPoolExecutor(max_workers=_N_IO_WORKERS,  thread_name_prefix="io")
stt_pool  = ThreadPoolExecutor(max_workers=_N_STT_WORKERS, thread_name_prefix="stt")
llm_pool  = ThreadPoolExecutor(max_workers=_N_LLM_WORKERS, thread_name_prefix="llm")


def _ts(): return datetime.now().strftime("%H:%M:%S")


# ══════════════════════════════════════════════════════════════════
#  CONTEXT
# ══════════════════════════════════════════════════════════════════
class Context:
    def __init__(self):
        self._l = threading.Lock()
        self.segments: List[Dict] = []
        self.full_bn = ""
        self.full_en = ""
        self.schedule: List[Dict] = []

    def add(self, text_bn: str, text_en: str = "", src="live"):
        with self._l:
            self.segments.append({
                "bn": text_bn.strip(), "en": text_en.strip(),
                "ts": _ts(), "src": src,
            })
            self.full_bn = " ".join(s["bn"] for s in self.segments)
            self.full_en = " ".join(s["en"] for s in self.segments if s["en"])

    def recent_en(self, chars=700):
        with self._l: return self.full_en[-chars:]

    def recent_bn(self, chars=700):
        with self._l: return self.full_bn[-chars:]

    def words(self):
        with self._l: return len(self.full_bn.split())

    def add_schedule(self, item):
        with self._l:
            item["ts"] = _ts()
            self.schedule.append(item)

    def get_schedule(self):
        with self._l: return list(self.schedule)

    def clear(self):
        with self._l:
            self.segments.clear()
            self.full_bn = ""
            self.full_en = ""


ctx = Context()

# ══════════════════════════════════════════════════════════════════
#  ANSWER CACHE
# ══════════════════════════════════════════════════════════════════
_cache: collections.OrderedDict = collections.OrderedDict()
_cache_lock = threading.Lock()


def cache_get(key: str) -> Optional[Tuple[str, str]]:
    k = hashlib.md5(key.strip().lower().encode()).hexdigest()[:12]
    with _cache_lock:
        if k in _cache:
            _cache.move_to_end(k)
            return _cache[k]
    return None


def cache_set(key: str, en_ans: str, bn_ans: str):
    if is_bad_answer(en_ans) or is_bad_answer(bn_ans):
        return
    k = hashlib.md5(key.strip().lower().encode()).hexdigest()[:12]
    with _cache_lock:
        _cache[k] = (en_ans, bn_ans)
        _cache.move_to_end(k)
        if len(_cache) > 300:
            _cache.popitem(last=False)


# ══════════════════════════════════════════════════════════════════
#  VECTOR DB
# ══════════════════════════════════════════════════════════════════
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    HAS_VDB = True
except ImportError:
    HAS_VDB = False
    print("VDB disabled — pip install sentence-transformers faiss-cpu")


class VectorDB:
    def __init__(self):
        self.enabled = HAS_VDB
        self.index   = None
        self.records: List[Dict] = []
        self._l      = threading.Lock()
        if not self.enabled:
            return
        print("Loading VDB encoder…")
        self.enc = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2", device="cpu"
        )
        os.makedirs(VECTORDB_DIR, exist_ok=True)
        self._load()
        self._embed("warmup")
        print(f"VDB ready — {len(self.records)} records")

    def _load(self):
        if os.path.exists(VECTORDB_INDEX) and os.path.exists(VECTORDB_META):
            try:
                self.index = faiss.read_index(VECTORDB_INDEX)
                with open(VECTORDB_META) as f:
                    self.records = json.load(f)
                return
            except Exception:
                pass
        self.index = faiss.IndexFlatIP(VECTORDB_DIM)

    def _embed(self, text):
        return self.enc.encode(
            [text], normalize_embeddings=True,
            show_progress_bar=False, batch_size=1,
        ).astype("float32")

    def search(self, query: str, k=3):
        if not self.enabled or self.index.ntotal == 0:
            return []
        try:
            q  = self._embed(query)
            with self._l:
                kk = min(k, self.index.ntotal)
                scores, idxs = self.index.search(q, kk)
            return [
                {"score": float(s), **self.records[i]}
                for s, i in zip(scores[0], idxs[0])
                if 0 <= i < len(self.records)
            ]
        except Exception:
            return []

    def store(self, query: str, answer_en: str, answer_bn: str = ""):
        if not self.enabled or is_bad_answer(answer_en):
            return
        try:
            emb = self._embed(query)
            with self._l:
                self.index.add(emb)
                self.records.append({
                    "query": query, "answer": answer_en,
                    "answer_bn": answer_bn,
                    "ts": datetime.now().isoformat(),
                })
            if len(self.records) % 10 == 0:
                self._save()
        except Exception:
            pass

    def _save(self):
        try:
            faiss.write_index(self.index, VECTORDB_INDEX)
            with open(VECTORDB_META, "w") as f:
                json.dump(self.records, f, separators=(",", ":"))
        except Exception:
            pass

    def count(self): return len(self.records)

    def shutdown(self):
        if self.enabled:
            self._save()


vdb = VectorDB()

# ══════════════════════════════════════════════════════════════════
#  OLLAMA
# ══════════════════════════════════════════════════════════════════
class Ollama:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"Content-Type": "application/json"})
        self.ok    = False
        self.model = ""
        self._init()

    def _init(self):
        global OLLAMA_MODEL
        try:
            r = self.s.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            if not r.ok:
                print("Ollama not reachable"); return
        except Exception as e:
            print(f"Ollama offline: {e}"); return
        self.model = OLLAMA_MODEL = _detect_ollama_model()
        if not self.model:
            print("❌ No model found — run: ollama pull gemma2:2b"); return
        print(f"Pinning {self.model} in RAM…")
        try:
            self.s.post(f"{OLLAMA_URL}/api/generate", json={
                "model": self.model, "prompt": "hi", "stream": False,
                "keep_alive": -1,
                "options": {"num_predict": 1, "num_ctx": 64},
            }, timeout=20)
            self.ok = True
            print(f"✅ Ollama ready: {self.model}")
        except Exception as e:
            print(f"Model pin warning: {e}")
            self.ok = True

    def generate(self, prompt: str, max_tokens=MAX_TOKENS) -> str:
        if not self.ok or not self.model:
            return ""
        try:
            r = self.s.post(f"{OLLAMA_URL}/api/generate", json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": TEMPERATURE,
                    "top_k": 20,
                    "top_p": 0.85,
                    "repeat_penalty": 1.1,
                    "num_ctx": 768,
                    "num_thread": CPU_CORES,
                    "num_batch": 512,
                },
            }, timeout=60)
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except Exception as e:
            print(f"[Ollama err] {e}")
            return ""


ollama = Ollama()

# ══════════════════════════════════════════════════════════════════
#  WHISPER STT
# ══════════════════════════════════════════════════════════════════
if USE_BENGALI_WHISPER:
    print(f"Loading Bengali Whisper from {BENGALI_WHISPER_PATH}…")
    _wm = WhisperModel(BENGALI_WHISPER_PATH, device="cpu", compute_type="int8")
    WHISPER_LANG = "bn"
    print("✅ Bengali Whisper ready")
else:
    print(f"⚠️  Bengali model not at {BENGALI_WHISPER_PATH} — using tiny.en fallback")
    _wm = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    WHISPER_LANG = "en"

for sz in [0.5, 1.0, 2.0]:
    list(_wm.transcribe(
        np.zeros(int(SAMPLE_RATE * sz), np.float32),
        beam_size=1, language=WHISPER_LANG,
    )[0])
print("✅ Whisper warmed up")

_wlock = threading.Lock()


def transcribe(audio: np.ndarray) -> Optional[str]:
    a  = audio.astype(np.float32)
    pk = float(np.max(np.abs(a)))
    if pk < 0.004:
        return None
    if pk > 0:
        a = a / pk
    with _wlock:
        segs, _ = _wm.transcribe(
            a,
            beam_size=1,
            language=WHISPER_LANG,
            vad_filter=True,
            temperature=0.0,
            condition_on_previous_text=False,
            word_timestamps=False,
            initial_prompt="শুদ্ধ বাংলা।" if WHISPER_LANG == "bn" else None,
        )
        out = [s.text.strip() for s in segs if s.text.strip()]
    return out[0] if out else None


def bad_text(text, min_words=1) -> bool:
    if not text or len(text.strip()) < 2:
        return True
    words = [
        w.strip(".,!?;:'\"()[]।")
        for w in text.split()
        if w.strip(".,!?;:'\"()[]।")
    ]
    return len(words) < min_words


# ══════════════════════════════════════════════════════════════════
#  TTS QUEUE
# ══════════════════════════════════════════════════════════════════
def tts_loop():
    while not stop_event.is_set():
        if _is_tts_playing.is_set():
            time.sleep(0.05)
            continue
        try:
            item = tts_q.get(timeout=0.3)
            if item and len(item.strip()) > 1:
                speak_bengali_blocking(item)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[tts_loop] {e}")


def queue_tts(text_bn: str):
    if text_bn and not tts_q.full():
        tts_q.put(text_bn)


# ══════════════════════════════════════════════════════════════════
#  AUDIO CAPTURE
# ══════════════════════════════════════════════════════════════════
_lb: List = []; _lt = 0.0; _ls = False
_cb: List = []; _ct = 0.0; _cs = False
_lb_lock = threading.Lock()
_cb_lock = threading.Lock()


def audio_cb(indata, frames, time_info, status):
    global _lb, _lt, _ls, _cb, _ct, _cs
    if stop_event.is_set():
        return
    if _is_tts_playing.is_set():
        with _lb_lock: _lb = []; _ls = False
        with _cb_lock: _cb = []; _cs = False
        return
    mono = indata[:, 0].copy()
    e    = float(np.sqrt(np.mean(mono ** 2)))
    now  = time.monotonic()

    if live_active.is_set() and not cmd_mode.is_set():
        with _lb_lock:
            if e > ENERGY_THRESH:
                _ls = True; _lt = now; _lb.append(mono)
            elif _ls:
                _lb.append(mono)
                if now - _lt > SILENCE_LIVE and len(_lb) > 3:
                    audio = np.concatenate(_lb); _lb = []; _ls = False
                    if not live_q.full(): live_q.put(audio)
                elif now - _lt > 4.0:
                    _lb = []; _ls = False

    if cmd_mode.is_set():
        with _cb_lock:
            _cb.append(mono)
            if e > ENERGY_THRESH: _ct = now; _cs = True
            if _cs and now - _ct > SILENCE_CMD and len(_cb) > 3:
                audio = np.concatenate(_cb); _cb = []; _cs = False
                cmd_mode.clear()
                if not cmd_q.full(): cmd_q.put(audio)


def flush_cmd():
    global _cb, _cs
    with _cb_lock:
        if len(_cb) >= 3:
            audio = np.concatenate(_cb); _cb = []; _cs = False
            cmd_mode.clear()
            if not cmd_q.full(): cmd_q.put(audio)
        else:
            _cb = []; _cs = False
            cmd_mode.clear()


# ══════════════════════════════════════════════════════════════════
#  CORE Q&A PIPELINE
# ══════════════════════════════════════════════════════════════════
def answer_in_bengali(text_bn: str, log_fn, use_transcript=False) -> str:
    t0 = time.monotonic()

    if WHISPER_LANG == "bn":
        trans_future: Future = executor.submit(translate_bn_to_en, text_bn)
    else:
        trans_future = None

    ctx_bn = ctx.recent_bn(300) if use_transcript else ""
    ctx_en = ctx.recent_en(500) if use_transcript else ""

    text_en = ""
    if trans_future:
        try:
            text_en = trans_future.result(timeout=TRANS_TIMEOUT + 5) or ""
        except Exception:
            text_en = ""
    else:
        text_en = text_bn

    has_translation = bool(text_en and text_en.strip() != text_bn.strip())
    trans_ms = (time.monotonic() - t0) * 1000

    if has_translation:
        log_fn(f"🔤 EN ({trans_ms:.0f}ms): {text_en}\n")
    else:
        log_fn(f"🔤 Bengali-direct mode ({trans_ms:.0f}ms)\n")

    cache_key = text_en if has_translation else text_bn
    cache_hit = cache_get(cache_key)

    if cache_hit:
        _, bn_ans = cache_hit
        ms = (time.monotonic() - t0) * 1000
        log_fn(f"⚡ [CACHE {ms:.0f}ms]\n🤖 {bn_ans}\n")
        queue_tts(bn_ans)
        return bn_ans

    vdb_hits = []
    if has_translation and HAS_VDB:
        try:
            vdb_hits = executor.submit(vdb.search, text_en, 3).result(timeout=2.0) or []
        except Exception:
            vdb_hits = []

    if vdb_hits and vdb_hits[0]["score"] >= HIT_THRESHOLD:
        best   = vdb_hits[0]
        en_ans = best["answer"]
        bn_ans = best.get("answer_bn") or ""
        if not bn_ans:
            bn_ans = translate_en_to_bn(en_ans)
        if bn_ans and not is_bad_answer(bn_ans):
            ms = (time.monotonic() - t0) * 1000
            log_fn(f"⚡ [VDB {best['score']:.0%} | {ms:.0f}ms]\n🤖 {bn_ans}\n")
            cache_set(text_en, en_ans, bn_ans)
            queue_tts(bn_ans)
            return bn_ans

    ms_pre = (time.monotonic() - t0) * 1000

    if has_translation:
        ctx_hint = ""
        if vdb_hits and vdb_hits[0]["score"] >= PARTIAL_THRESH:
            ctx_hint = f"Related: {vdb_hits[0]['answer'][:80]}\n"
        ctx_part = ""
        if use_transcript and ctx_en.strip():
            ctx_part = f"Transcript context:\n{ctx_en}\n\n"

        prompt = (
            "You are a helpful assistant. Answer concisely in 2-3 sentences.\n"
            f"{ctx_part}{ctx_hint}"
            f"Question: {text_en}\nAnswer:"
        )
        log_fn(f"🧠 [LLM+EN @ {ms_pre:.0f}ms…]\n")
        en_ans = ""
        try:
            en_ans = llm_pool.submit(ollama.generate, prompt).result(timeout=65) or ""
        except Exception as e:
            print(f"[LLM future] {e}")

        if en_ans and not is_bad_answer(en_ans):
            ms_llm = (time.monotonic() - t0) * 1000
            log_fn(
                f"✅ EN ({ms_llm:.0f}ms): {en_ans[:70]}…\n"
                if len(en_ans) > 70
                else f"✅ EN ({ms_llm:.0f}ms): {en_ans}\n"
            )
            log_fn("⏳ Translating to Bengali…\n")
            bn_ans = ""
            try:
                bn_ans = _trans_pool.submit(translate_en_to_bn, en_ans).result(
                    timeout=TRANS_TIMEOUT + 5
                ) or ""
            except Exception:
                bn_ans = ""

            if bn_ans and not is_bad_answer(bn_ans):
                ms_total = (time.monotonic() - t0) * 1000
                log_fn(f"🗣 বাংলা ({ms_total:.0f}ms):\n{bn_ans}\n")
                cache_set(text_en, en_ans, bn_ans)
                executor.submit(vdb.store, text_en, en_ans, bn_ans)
                queue_tts(bn_ans)
                return bn_ans
            else:
                log_fn("⚠️ EN→BN failed — Bengali-direct fallback\n")
                has_translation = False
        else:
            has_translation = False

    # Bengali-direct mode — send Bengali text straight to Ollama
    if not has_translation:
        ctx_part_bn = ""
        if use_transcript and ctx_bn.strip():
            ctx_bn_clean = re.sub(r'[a-zA-Z]+', '', ctx_bn).strip()
            if ctx_bn_clean:
                ctx_part_bn = f"প্রসঙ্গ:\n{ctx_bn_clean}\n\n"

        prompt_bn = (
            "তুমি একজন সহায়ক AI। "
            "নিচের প্রশ্নের উত্তর সংক্ষিপ্তভাবে বাংলায় দাও (২-৩ বাক্য)। "
            "শুধু বাংলায় উত্তর দাও।\n\n"
            f"{ctx_part_bn}"
            f"প্রশ্ন: {text_bn}\n"
            "উত্তর:"
        )
        log_fn(f"🧠 [LLM+BN @ {ms_pre:.0f}ms…]\n")
        bn_ans = ""
        try:
            bn_ans = llm_pool.submit(
                ollama.generate, prompt_bn, MAX_TOKENS
            ).result(timeout=65) or ""
        except Exception as e:
            print(f"[LLM BN future] {e}")

        if not bn_ans or is_bad_answer(bn_ans):
            bn_fallback = "দুঃখিত, এই মুহূর্তে উত্তর দিতে পারছি না।"
            log_fn(f"⚠️ LLM failed\n🤖 {bn_fallback}\n")
            queue_tts(bn_fallback)
            return bn_fallback

        ms_total = (time.monotonic() - t0) * 1000
        log_fn(f"🗣 বাংলা ({ms_total:.0f}ms):\n{bn_ans}\n")
        cache_set(text_bn, bn_ans, bn_ans)
        queue_tts(bn_ans)
        return bn_ans

    fallback = "দুঃখিত, উত্তর পাওয়া যায়নি।"
    queue_tts(fallback)
    return fallback


# ══════════════════════════════════════════════════════════════════
#  LIVE TRANSCRIPT WORKER
# ══════════════════════════════════════════════════════════════════
def live_worker(log_fn, stats_fn):
    while not stop_event.is_set():
        try:
            audio = live_q.get(timeout=0.5)
        except queue.Empty:
            continue
        if cmd_busy.is_set():
            continue
        stt_future = stt_pool.submit(transcribe, audio)
        try:
            text_bn = stt_future.result(timeout=10)
        except Exception:
            text_bn = None
        if not text_bn or bad_text(text_bn):
            continue

        def _add(bn=text_bn):
            en_f = (
                _trans_pool.submit(translate_bn_to_en, bn)
                if WHISPER_LANG == "bn" else None
            )
            en = ""
            if en_f:
                try:
                    en = en_f.result(timeout=TRANS_TIMEOUT + 1) or ""
                except Exception:
                    pass
            ctx.add(bn, en, "live")
            stats_fn()

        log_fn(f"[{_ts()}] {text_bn}\n")
        executor.submit(_add)


# ══════════════════════════════════════════════════════════════════
#  COMMAND WORKER
# ══════════════════════════════════════════════════════════════════
def cmd_worker(log_fn, stats_fn, status_fn):
    while not stop_event.is_set():
        try:
            audio = cmd_q.get(timeout=0.5)
        except queue.Empty:
            continue

        cmd_busy.set()
        t0 = time.monotonic()
        status_fn("🎙️ STT চলছে…")

        stt_future = stt_pool.submit(transcribe, audio)
        try:
            text_bn = stt_future.result(timeout=10)
        except Exception:
            text_bn = None

        stt_ms = (time.monotonic() - t0) * 1000
        if not text_bn or bad_text(text_bn, min_words=1):
            log_fn(f"\n⚠️ অস্পষ্ট: {repr(text_bn)}\n")
            status_fn("⚠️ অস্পষ্ট — আবার চেষ্টা করুন")
            cmd_busy.clear()
            continue

        log_fn(f"\n{'─' * 54}\n🎤 বাংলা ({stt_ms:.0f}ms): {text_bn}\n")

        intent_from_bn = get_intent(text_bn, "")
        trans_future   = _trans_pool.submit(translate_bn_to_en, text_bn)
        log_fn(f"📌 Intent (BN): {intent_from_bn.upper()}\n")

        text_en = ""
        try:
            text_en = trans_future.result(timeout=TRANS_TIMEOUT + 1) or ""
        except Exception:
            pass

        intent = intent_from_bn
        if text_en:
            intent2 = get_intent(text_bn, text_en)
            if intent2 != intent:
                intent = intent2
                log_fn(f"📌 Intent refined: {intent.upper()}\n")

        if intent == "question":
            status_fn("🧠 উত্তর তৈরি হচ্ছে…")
            answer_in_bengali(text_bn, log_fn, use_transcript=True)
            executor.submit(ctx.add, text_bn, text_en, "cmd")
            executor.submit(stats_fn)

        elif intent == "continue":
            c_bn = ctx.recent_bn(400)
            c_en = ctx.recent_en(400)
            if not c_bn.strip():
                r = "এখনো কোনো প্রসঙ্গ নেই।"
                log_fn(f"🤖 {r}\n"); queue_tts(r)
            else:
                status_fn("📖 চালিয়ে যাচ্ছে…")
                bn_r = ""
                if c_en.strip():
                    en_r = ""
                    try:
                        en_r = llm_pool.submit(
                            ollama.generate,
                            f"Continue naturally in 3-4 sentences:\n\n{c_en}\n\nContinue:",
                            150,
                        ).result(timeout=65) or ""
                    except Exception:
                        pass
                    if en_r:
                        bn_r = translate_en_to_bn(en_r)
                if not bn_r:
                    try:
                        bn_r = llm_pool.submit(
                            ollama.generate,
                            f"নিচের বিষয়টি বাংলায় ৩-৪ বাক্যে চালিয়ে যাও:\n\n{c_bn}\n\nচালিয়ে যাও:",
                            150,
                        ).result(timeout=65) or ""
                    except Exception:
                        bn_r = ""
                bn_r = bn_r or "চালিয়ে যেতে পারছি না।"
                log_fn(f"🤖 {bn_r}\n"); queue_tts(bn_r)
                executor.submit(ctx.add, bn_r, "", "ai")
                executor.submit(stats_fn)

        elif intent == "summary":
            c_bn = ctx.recent_bn(800)
            c_en = ctx.recent_en(800)
            if not c_bn.strip():
                r = "সারসংক্ষেপ করার মতো কিছু নেই।"
                log_fn(f"🤖 {r}\n"); queue_tts(r)
            else:
                status_fn("📋 সারসংক্ষেপ…")
                bn_s = ""
                if c_en.strip():
                    en_s = ""
                    try:
                        en_s = llm_pool.submit(
                            ollama.generate,
                            f"Summarize in 3-5 bullet points:\n\n{c_en}\n\nSummary:",
                            200,
                        ).result(timeout=65) or ""
                    except Exception:
                        pass
                    if en_s:
                        try:
                            bn_s = _trans_pool.submit(
                                translate_en_to_bn, en_s
                            ).result(timeout=TRANS_TIMEOUT + 5) or ""
                        except Exception:
                            bn_s = ""
                if not bn_s:
                    try:
                        bn_s = llm_pool.submit(
                            ollama.generate,
                            f"নিচের বিষয়টি বাংলায় ৩-৫টি বুলেট পয়েন্টে সারসংক্ষেপ করো:\n\n{c_bn}\n\nসারসংক্ষেপ:",
                            200,
                        ).result(timeout=65) or ""
                    except Exception:
                        bn_s = ""
                bn_s = bn_s or "সারসংক্ষেপ তৈরি করা সম্ভব হয়নি।"
                log_fn(f"📋 {bn_s}\n"); queue_tts(bn_s)

        elif intent == "schedule":
            status_fn("📅 সূচি বিশ্লেষণ…")
            q_text = text_en or text_bn
            en_raw = ""
            try:
                en_raw = llm_pool.submit(
                    ollama.generate,
                    f"Extract schedule. Reply EXACTLY:\n"
                    f"EVENT: <n>\nTIME: <time>\nDETAILS: <details>\n\nRequest: {q_text}",
                    80,
                ).result(timeout=65) or ""
            except Exception:
                pass
            bn_raw = ""
            if en_raw:
                try:
                    bn_raw = _trans_pool.submit(
                        translate_en_to_bn, en_raw
                    ).result(timeout=TRANS_TIMEOUT + 5) or ""
                except Exception:
                    bn_raw = ""
            bn_raw = bn_raw or f"সূচি যোগ করা হয়েছে: {text_bn}"
            log_fn(f"📅 {bn_raw}\n"); queue_tts(bn_raw)
            item: Dict = {"raw": en_raw or text_bn, "raw_bn": bn_raw, "request": text_bn}
            if en_raw:
                for line in en_raw.splitlines():
                    for k2 in ("EVENT", "TIME", "DETAILS"):
                        if line.upper().startswith(f"{k2}:"):
                            item[k2.lower()] = line.split(":", 1)[1].strip()
            ctx.add_schedule(item)
            executor.submit(stats_fn)

        else:
            executor.submit(ctx.add, text_bn, text_en, "cmd")
            executor.submit(stats_fn)
            r = "ট্রান্সক্রিপ্টে যোগ করা হয়েছে।"
            log_fn(f"📝 {r}\n"); status_fn("✅ যোগ করা হয়েছে")
            cmd_busy.clear()
            continue

        ms = (time.monotonic() - t0) * 1000
        log_fn(f"\n⏱️ মোট: {ms:.0f}ms  |  VDB:{vdb.count()}\n{'─' * 54}\n")
        status_fn("✅ সম্পন্ন")
        cmd_busy.clear()


# ══════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════
_TTS_DISPLAY = {
    "mms":     ("MMS-BEN★",  "#3fb950"),
    "espeak":  ("eSPEAK✅",  "#3fb950"),
    "pyttsx3": ("PYTTSX3⚠️", "#f0883e"),
    "none":    ("NONE❌",    "#f85149"),
}


class App:
    def __init__(self, root):
        self.root    = root
        self.stream  = None
        self.live_on = False
        root.title("ADAS Voice AI — বাংলা ⚡ LOCAL EDITION")
        root.geometry("1240x860")
        root.configure(bg="#0d1117")
        self._build()
        self._start()

    def _build(self):
        R = self.root
        tts_label, tts_color = _TTS_DISPLAY.get(
            _tts_mode, (f"{_tts_mode.upper()}⚠️", "#f0883e")
        )

        hdr = tk.Frame(R, bg="#161b22", pady=7)
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr, text="🚗  ADAS VOICE AI  —  বাংলা ⚡ LOCAL  🇧🇩",
            font=("Courier New", 12, "bold"), bg="#161b22", fg="#58a6ff",
        ).pack(side=tk.LEFT, padx=12)
        tk.Label(hdr, text=f"TTS:{tts_label}",
                 font=("Courier New", 8), bg="#161b22", fg=tts_color,
                 ).pack(side=tk.RIGHT, padx=6)
        tk.Label(
            hdr, text=f"STT:{'BN-Whisper' if USE_BENGALI_WHISPER else 'tiny.en'}",
            font=("Courier New", 8), bg="#161b22",
            fg="#3fb950" if USE_BENGALI_WHISPER else "#f0883e",
        ).pack(side=tk.RIGHT, padx=6)
        tk.Label(hdr, text=f"LLM:{OLLAMA_MODEL or 'OFFLINE'}",
                 font=("Courier New", 8), bg="#161b22",
                 fg="#3fb950" if ollama.ok else "#f85149",
                 ).pack(side=tk.RIGHT, padx=6)
        self.trans_lbl = tk.Label(
            hdr, text="TRANS:loading…",
            font=("Courier New", 8), bg="#161b22", fg="#e3b341",
        )
        self.trans_lbl.pack(side=tk.RIGHT, padx=6)
        tk.Label(
            hdr,
            text=f"POOLS:STT{_N_STT_WORKERS}|TRANS{_N_TRANS_WORKERS}|IO{_N_IO_WORKERS}",
            font=("Courier New", 7), bg="#161b22", fg="#6e7681",
        ).pack(side=tk.RIGHT, padx=6)
        self.stats_lbl = tk.Label(
            hdr, text="Words:0  VDB:0  Cache:0",
            font=("Courier New", 8), bg="#161b22", fg="#8b949e",
        )
        self.stats_lbl.pack(side=tk.RIGHT, padx=12)

        cf = tk.Frame(R, bg="#0d1117", pady=7)
        cf.pack(fill=tk.X, padx=10)
        self.live_btn = tk.Button(
            cf, text="▶  লাইভ ট্রান্সক্রিপ্ট শুরু",
            width=24, height=2, bg="#21262d", fg="#8b949e",
            font=("Courier New", 10, "bold"), relief=tk.FLAT, cursor="hand2",
            command=self._toggle_live,
        )
        self.live_btn.pack(side=tk.LEFT, padx=4)
        self.cmd_btn = tk.Button(
            cf, text="🎙️  ধরুন ও কমান্ড করুন",
            width=22, height=2, bg="#238636", fg="white",
            font=("Courier New", 10, "bold"), relief=tk.RAISED, cursor="hand2",
        )
        self.cmd_btn.pack(side=tk.LEFT, padx=4)
        self.cmd_btn.bind("<ButtonPress-1>",   self._cmd_press)
        self.cmd_btn.bind("<ButtonRelease-1>", self._cmd_release)
        tk.Button(cf, text="🗑 Clear", width=8, height=2, command=self._clear,
                  bg="#21262d", fg="#aaa", font=("Courier New", 8), relief=tk.FLAT,
                  ).pack(side=tk.LEFT, padx=4)
        tk.Button(cf, text="📅 সূচি", width=10, height=2, command=self._show_schedule,
                  bg="#1f6feb", fg="white", font=("Courier New", 8), relief=tk.FLAT,
                  ).pack(side=tk.LEFT, padx=4)
        tk.Button(cf, text="⏹ বন্ধ", width=8, height=2, command=self._stop,
                  bg="#da3633", fg="white", font=("Courier New", 9, "bold"),
                  relief=tk.FLAT,
                  ).pack(side=tk.RIGHT, padx=4)

        tk.Label(
            R,
            text="  কি/কী/কে/কোথায়/কেন/কীভাবে → প্রশ্ন  |  "
                 "চালিয়ে যাও → continue  |  সারসংক্ষেপ → summary  |  "
                 "মনে করিয়ে দাও → schedule  |  অন্যান্য → transcript  ",
            font=("Courier New", 7), bg="#1a2a1a", fg="#3fb950",
        ).pack(fill=tk.X)

        self.status = tk.Label(
            R, text="প্রস্তুত — মডেল লোড হচ্ছে…",
            font=("Courier New", 10), bg="#0d1117", fg="#8b949e",
        )
        self.status.pack(pady=3)

        pane = tk.Frame(R, bg="#0d1117")
        pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        lf = tk.Frame(pane, bg="#0d1117")
        lf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(lf, text="📝  বাংলা লাইভ ট্রান্সক্রিপ্ট",
                 font=("Courier New", 8, "bold"), bg="#0d1117", fg="#3fb950",
                 ).pack(anchor=tk.W)
        self.tbox = scrolledtext.ScrolledText(
            lf, state=tk.DISABLED, font=("Courier New", 9),
            bg="#071007", fg="#3fb950", wrap=tk.WORD, width=40,
        )
        self.tbox.pack(fill=tk.BOTH, expand=True)

        rf = tk.Frame(pane, bg="#0d1117")
        rf.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        tk.Label(rf, text="🤖  AI উত্তর — বাংলায় ⚡ LOCAL",
                 font=("Courier New", 8, "bold"), bg="#0d1117", fg="#58a6ff",
                 ).pack(anchor=tk.W)
        self.abox = scrolledtext.ScrolledText(
            rf, state=tk.DISABLED, font=("Courier New", 9),
            bg="#0d1117", fg="#c9d1d9", wrap=tk.WORD,
        )
        self.abox.pack(fill=tk.BOTH, expand=True)

        self._ai("╔══════════════════════════════════════════════════════╗\n")
        self._ai("║   ADAS VOICE AI  —  সম্পূর্ণ স্থানীয় সংস্করণ       ║\n")
        self._ai("║                                                      ║\n")
        self._ai("║  STT  : faster-whisper (local, CPU)                  ║\n")
        self._ai("║  TRANS: NLLB-200-distilled-600M (local, CPU)         ║\n")
        self._ai("║  LLM  : Ollama (local, CPU)                          ║\n")
        self._ai("║  TTS  : facebook/mms-tts-ben (local, CPU)            ║\n")
        self._ai("║  VDB  : FAISS + MiniLM (local, CPU)                  ║\n")
        self._ai("║                                                      ║\n")
        self._ai("║  ⚡  Zero internet required after first-time setup   ║\n")
        self._ai("╚══════════════════════════════════════════════════════╝\n\n")

        if not ollama.ok:
            self._ai("❌ Ollama offline!\n"
                     "   ollama serve && ollama pull gemma2:2b\n\n")
        else:
            self._ai(f"✅ LLM: {OLLAMA_MODEL}\n")

        if not USE_BENGALI_WHISPER:
            self._ai(f"⚠️  Bengali Whisper missing at {BENGALI_WHISPER_PATH}\n"
                     "   Run: python download_models.py\n\n")

        self._ai("⏳ NLLB-200 & MMS-TTS loading in background…\n"
                 "   (first run: downloads ~1.6 GB total)\n\n")
        self._ai("💡 প্রশ্ন উদাহরণ:\n   বিড়াল কি?\n   পৃথিবী কত বড়?\n\n")

        executor.submit(self._poll_model_ready)

    def _poll_model_ready(self):
        _nllb_ready.wait(timeout=300)
        ok = _translation_available
        if ok:
            self.root.after(0, lambda: self.trans_lbl.config(
                text="TRANS:✅ NLLB-200", fg="#3fb950"))
            self._ai("✅ NLLB-200 translation ready!\n\n")
        else:
            self.root.after(0, lambda: self.trans_lbl.config(
                text="TRANS:⚠️ BN-Direct", fg="#e3b341"))
            self._ai("⚠️ NLLB unavailable — Bengali-direct mode active\n\n")

    def _toggle_live(self):
        if not self.live_on:
            self.live_on = True; live_active.set()
            self.live_btn.config(text="⏸  ট্রান্সক্রিপ্ট বিরতি",
                                 bg="#145a32", fg="#3fb950")
            self._set_status("🟢 লাইভ চালু", "#3fb950")
        else:
            self.live_on = False; live_active.clear()
            self.live_btn.config(text="▶  লাইভ ট্রান্সক্রিপ্ট শুরু",
                                 bg="#21262d", fg="#8b949e")
            self._set_status("বিরতি", "#8b949e")

    def _cmd_press(self, e=None):
        if cmd_busy.is_set() or stop_event.is_set() or cmd_mode.is_set():
            return
        global _cb, _cs, _ct
        with _cb_lock:
            _cb = []; _cs = False; _ct = 0.0
        while not cmd_q.empty():
            try: cmd_q.get_nowait()
            except Exception: break
        cmd_mode.set()
        self.cmd_btn.config(text="🔴  রেকর্ড হচ্ছে…",
                            bg="#da3633", relief=tk.SUNKEN)
        self._set_status("🔴 বলুন — ছেড়ে দিন", "#f85149")

    def _cmd_release(self, e=None):
        executor.submit(flush_cmd)
        self.cmd_btn.config(text="🎙️  ধরুন ও কমান্ড করুন",
                            bg="#238636", relief=tk.RAISED)
        self._set_status("⏳ প্রক্রিয়া হচ্ছে…", "#d2a8ff")

    def _show_schedule(self):
        items = ctx.get_schedule()
        w = tk.Toplevel(self.root)
        w.title("সূচি"); w.geometry("520x380"); w.configure(bg="#0d1117")
        tk.Label(w, text="📅  সূচি ও অনুস্মারক",
                 font=("Courier New", 10, "bold"),
                 bg="#0d1117", fg="#e3b341").pack(pady=8)
        b = scrolledtext.ScrolledText(w, font=("Courier New", 9),
                                      bg="#0d1117", fg="#e3b341", wrap=tk.WORD)
        b.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        if not items:
            b.insert(tk.END, "এখনো কোনো সূচি নেই।\n\nউদাহরণ:\n"
                             "'বিকেল ৩টায় মিটিং মনে করিয়ে দাও'")
        else:
            for i, item in enumerate(items, 1):
                b.insert(tk.END, f"[{i}] {item.get('ts', '')}\n")
                b.insert(tk.END,
                         f"  ইভেন্ট : {item.get('event', item.get('raw', '?'))}\n")
                b.insert(tk.END, f"  সময়   : {item.get('time', '—')}\n")
                b.insert(tk.END, f"  বিবরণ : {item.get('details', '—')}\n\n")
        b.config(state=tk.DISABLED)

    def _clear(self):
        ctx.clear()
        self.tbox.config(state=tk.NORMAL)
        self.tbox.delete(1.0, tk.END)
        self.tbox.config(state=tk.DISABLED)
        self._update_stats()

    def _transcript(self, txt):
        def _do():
            self.tbox.config(state=tk.NORMAL)
            self.tbox.insert(tk.END, txt)
            self.tbox.see(tk.END)
            self.tbox.config(state=tk.DISABLED)
        self.root.after(0, _do)

    def _ai(self, txt):
        def _do():
            self.abox.config(state=tk.NORMAL)
            self.abox.insert(tk.END, txt)
            self.abox.see(tk.END)
            self.abox.config(state=tk.DISABLED)
        self.root.after(0, _do)

    def _set_status(self, txt, col="#8b949e"):
        self.root.after(0, lambda: self.status.config(text=txt, fg=col))

    def _status_fn(self, txt):
        cols = {"✅": "#3fb950", "⚡": "#3fb950", "🧠": "#d2a8ff",
                "📋": "#e3b341", "📅": "#e3b341",
                "⚠️": "#f0883e", "⏳": "#d2a8ff", "🔴": "#f85149"}
        col = next((c for k, c in cols.items() if k in txt), "#8b949e")
        self._set_status(txt, col)

    def _update_stats(self):
        with _cache_lock:
            nc = len(_cache)
        self.root.after(0, lambda: self.stats_lbl.config(
            text=f"Words:{ctx.words()}  VDB:{vdb.count()}  Cache:{nc}"))

    def _start(self):
        stop_event.clear()
        preload_model_async()
        threading.Thread(target=tts_loop, daemon=True).start()
        threading.Thread(
            target=live_worker, args=(self._transcript, self._update_stats),
            daemon=True,
        ).start()
        threading.Thread(
            target=cmd_worker,
            args=(self._ai, self._update_stats, self._status_fn),
            daemon=True,
        ).start()

        def audio_loop():
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1,
                blocksize=FRAME, dtype="float32",
                callback=audio_cb,
            )
            with self.stream:
                while not stop_event.is_set():
                    time.sleep(0.05)

        threading.Thread(target=audio_loop, daemon=True).start()

    def _stop(self):
        stop_event.set(); live_active.clear(); cmd_mode.clear()
        sd.stop()
        if self.stream:
            try: self.stream.stop(); self.stream.close()
            except Exception: pass
        self.cmd_btn.config(state=tk.DISABLED)
        self.live_btn.config(state=tk.DISABLED)
        self._set_status("বন্ধ", "#f85149")
        vdb.shutdown()
        for pool in (executor, stt_pool, llm_pool, _trans_pool, _tts_synth_pool):
            try: pool.shutdown(wait=False)
            except Exception: pass


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 64)
    print("  ADAS VOICE AI  —  LOCAL-ONLY EDITION")
    print(f"  STT  : {'Bengali Whisper' if USE_BENGALI_WHISPER else 'tiny.en (FALLBACK)'}")
    print(f"  LLM  : {OLLAMA_MODEL or 'NOT FOUND'} {'✅' if ollama.ok else '❌'}")
    print(f"  TRANS: NLLB-200-distilled-600M  (local, CPU)")
    print(f"  TTS  : facebook/mms-tts-ben  (local, CPU)")
    print(f"  VDB  : {'ON' if HAS_VDB else 'OFF'}")
    print(f"  Cores: {CPU_CORES}")
    print(f"  Pools: STT={_N_STT_WORKERS} | TRANS={_N_TRANS_WORKERS} "
          f"| IO={_N_IO_WORKERS} | LLM={_N_LLM_WORKERS}")
    print("=" * 64)
    if not USE_BENGALI_WHISPER:
        print(f"\n⚠️  Bengali Whisper not found at: {BENGALI_WHISPER_PATH}")
        print("    Run:  python download_models.py")
    root = tk.Tk()
    App(root)
    root.mainloop()
    executor.shutdown(wait=False)
