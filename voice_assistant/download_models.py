#!/usr/bin/env python3
"""
download_models.py  —  ADAS Voice AI  (one-time setup)
═══════════════════════════════════════════════════════════════════
Run this script ONCE with an internet connection.
After it completes, the voice assistant runs 100 % offline.

Downloads to ~/.cache/huggingface/hub/  (default HuggingFace cache).

Models downloaded:
  1. facebook/nllb-200-distilled-600M    ~1.2 GB  (translation)
  2. facebook/mms-tts-ben                ~400 MB  (Bengali TTS)
  3. sentence-transformers/all-MiniLM-L6-v2  ~90 MB  (VDB embeddings)
  4. arijitx/whisper-small-bn  (STT)  — converted to CTranslate2 int8
     Requires:  pip install ctranslate2
     Output:    ./arijitx-whisper-small-bn-ct2/

Usage:
  python download_models.py
  python download_models.py --skip-whisper   # if you already have the model
  python download_models.py --cache-dir /path/to/dir  # custom cache

After this script, set TRANSFORMERS_OFFLINE=1 to prevent any
accidental network requests:
  Windows:  $env:TRANSFORMERS_OFFLINE = "1"
  Linux:    export TRANSFORMERS_OFFLINE=1
═══════════════════════════════════════════════════════════════════
"""

import argparse
import os
import sys
import time


def _header(msg: str):
    print(f"\n{'═' * 60}")
    print(f"  {msg}")
    print('═' * 60)


def _ok(msg: str):   print(f"  ✅  {msg}")
def _warn(msg: str): print(f"  ⚠️   {msg}")
def _err(msg: str):  print(f"  ❌  {msg}", file=sys.stderr)


def _check_import(pkg: str, pip_name: str = "") -> bool:
    try:
        __import__(pkg)
        return True
    except ImportError:
        pip_name = pip_name or pkg
        _err(f"'{pkg}' not installed.  Fix: pip install {pip_name}")
        return False


# ─── 1. NLLB-200 translation model ────────────────────────────────
def download_nllb(cache_dir: str):
    _header("1 / 4   NLLB-200-distilled-600M  (translation)")
    if not _check_import("transformers"):
        return
    if not _check_import("torch"):
        return
    if not _check_import("sentencepiece"):
        _err("Fix: pip install sentencepiece sacremoses")
        return

    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    model_name = "facebook/nllb-200-distilled-600M"
    kwargs = {"cache_dir": cache_dir} if cache_dir else {}

    print("  Downloading tokenizer …")
    t0 = time.time()
    AutoTokenizer.from_pretrained(model_name, **kwargs)
    _ok(f"Tokenizer  ({time.time()-t0:.1f}s)")

    print("  Downloading model weights (~1.2 GB) …")
    t0 = time.time()
    AutoModelForSeq2SeqLM.from_pretrained(model_name, **kwargs)
    _ok(f"Model  ({time.time()-t0:.1f}s)")

    print("  Running smoke test (bn→en) …")
    import torch
    tok = AutoTokenizer.from_pretrained(model_name, **kwargs)
    mdl = AutoModelForSeq2SeqLM.from_pretrained(model_name, **kwargs)
    mdl.eval()
    tok.src_lang = "ben_Beng"
    inp = tok("হ্যালো", return_tensors="pt")
    fbi = tok.convert_tokens_to_ids("eng_Latn")
    with torch.no_grad():
        out = mdl.generate(**inp, forced_bos_token_id=fbi, max_new_tokens=20)
    result = tok.batch_decode(out, skip_special_tokens=True)[0]
    _ok(f"Smoke test → '{result}'")


# ─── 2. MMS-TTS Bengali ───────────────────────────────────────────
def download_mms(cache_dir: str):
    _header("2 / 4   facebook/mms-tts-ben  (TTS)")
    if not _check_import("transformers"):
        return
    if not _check_import("torch"):
        return

    from transformers import VitsModel, AutoTokenizer
    import torch

    model_name = "facebook/mms-tts-ben"
    kwargs = {"cache_dir": cache_dir} if cache_dir else {}

    print("  Downloading tokenizer …")
    t0 = time.time()
    AutoTokenizer.from_pretrained(model_name, **kwargs)
    _ok(f"Tokenizer  ({time.time()-t0:.1f}s)")

    print("  Downloading model weights (~400 MB) …")
    t0 = time.time()
    VitsModel.from_pretrained(model_name, **kwargs)
    _ok(f"Model  ({time.time()-t0:.1f}s)")

    print("  Running smoke test …")
    tok = AutoTokenizer.from_pretrained(model_name, **kwargs)
    mdl = VitsModel.from_pretrained(model_name, **kwargs)
    mdl.eval()
    inp = tok("হ্যালো", return_tensors="pt")
    with torch.no_grad():
        out = mdl(**inp)
    wav = out.waveform[0].squeeze().numpy()
    _ok(f"Synthesised {len(wav)} samples @ {mdl.config.sampling_rate} Hz")


# ─── 3. Sentence-Transformers (VDB embeddings) ────────────────────
def download_minilm(cache_dir: str):
    _header("3 / 4   all-MiniLM-L6-v2  (VDB embeddings)")
    if not _check_import("sentence_transformers", "sentence-transformers"):
        return

    from sentence_transformers import SentenceTransformer
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    kwargs = {"cache_folder": cache_dir} if cache_dir else {}

    print("  Downloading (~90 MB) …")
    t0 = time.time()
    enc = SentenceTransformer(model_name, device="cpu", **kwargs)
    emb = enc.encode(["hello"], normalize_embeddings=True)
    _ok(f"Encoder ready, dim={emb.shape[1]}  ({time.time()-t0:.1f}s)")


# ─── 4. Bengali Whisper STT ───────────────────────────────────────
def download_whisper(output_dir: str):
    _header("4 / 4   arijitx/whisper-small-bn  (STT)")

    if os.path.exists(output_dir) and os.listdir(output_dir):
        _ok(f"Already exists at '{output_dir}' — skipping")
        return

    if not _check_import("ctranslate2"):
        _warn("ctranslate2 not installed.  Run: pip install ctranslate2")
        _warn("Then re-run this script, or convert manually:")
        print()
        print("    ct2-transformers-converter \\")
        print("        --model arijitx/whisper-small-bn \\")
        print(f"        --output_dir {output_dir} \\")
        print("        --quantization int8")
        return

    import subprocess

    alt_cmd = [
        "ct2-transformers-converter",
        "--model",        "arijitx/whisper-small-bn",
        "--output_dir",   output_dir,
        "--quantization", "int8",
        "--force",
    ]
    cmd = [
        sys.executable, "-m", "ctranslate2.tools.convert_transformers",
        "--model",        "arijitx/whisper-small-bn",
        "--output_dir",   output_dir,
        "--quantization", "int8",
        "--force",
    ]

    print(f"  Converting to CTranslate2 int8 → '{output_dir}' …")
    t0 = time.time()
    for c in (alt_cmd, cmd):
        try:
            subprocess.run(c, check=True, timeout=600)
            _ok(f"Whisper model ready at '{output_dir}'  ({time.time()-t0:.1f}s)")
            return
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError as e:
            _err(f"Conversion failed: {e}")
            return

    _warn("Could not auto-convert.  Install ctranslate2 and run:")
    print(f"    ct2-transformers-converter --model arijitx/whisper-small-bn "
          f"--output_dir {output_dir} --quantization int8")


# ─── main ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Download all ADAS Voice AI models for offline use"
    )
    parser.add_argument("--skip-whisper", action="store_true",
                        help="Skip Bengali Whisper download/conversion")
    parser.add_argument("--cache-dir", default="",
                        help="Custom HuggingFace cache directory")
    parser.add_argument("--whisper-dir", default="./arijitx-whisper-small-bn-ct2",
                        help="Output directory for converted Whisper model")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  ADAS Voice AI  —  Model Downloader")
    print("  Run this ONCE.  All models cached locally after this.")
    print("═" * 60)

    if args.cache_dir:
        os.makedirs(args.cache_dir, exist_ok=True)
        print(f"\n  Cache dir: {args.cache_dir}")

    t_start = time.time()

    download_nllb(args.cache_dir)
    download_mms(args.cache_dir)
    download_minilm(args.cache_dir)

    if not args.skip_whisper:
        download_whisper(args.whisper_dir)
    else:
        _warn("Skipping Whisper download (--skip-whisper)")

    elapsed = time.time() - t_start
    print()
    print("═" * 60)
    print(f"  ✅  All done in {elapsed/60:.1f} minutes.")
    print()
    print("  To run offline, set:")
    print("    Windows:  $env:TRANSFORMERS_OFFLINE = '1'")
    print("    Linux:    export TRANSFORMERS_OFFLINE=1")
    print()
    print("  Then start the assistant:")
    print("    ollama serve            # in a separate terminal")
    print("    python main.py")
    print("═" * 60)


if __name__ == "__main__":
    main()
