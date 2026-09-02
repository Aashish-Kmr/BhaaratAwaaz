"""
Prove this bundle is actually offline-complete.

Two levels:

    python verify_offline.py           # fast: every weight file is present,
                                       # real, and the right size (seconds)
    python verify_offline.py --full    # slow: actually load every model with
                                       # the network cut off (minutes, ~8 GB RAM)

The fast check exists because the classic way this bundle breaks is silent: a
zip tool that stores Hugging Face's symlinks as links (or as tiny text stubs)
leaves a cache that looks complete in a directory listing but whose weight
files are 52 bytes. Checking declared minimum sizes catches that immediately,
where "the file exists" would not.

--full is the real proof. It blocks socket creation outright, so any model that
still wants to phone home fails loudly here -- on the machine that can fix it --
instead of at demo time. Run it once on the build machine against the staged
bundle, and once on the target machine after setup.ps1.

Exit code is 0 only if everything passed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# Point Hugging Face at the bundled cache BEFORE importing anything that
# reads these -- huggingface_hub latches HF_HOME at import time, so setting
# them afterwards would silently look in ~/.cache/huggingface instead.
# ----------------------------------------------------------------------

BUNDLE_ROOT = Path(__file__).resolve().parent
APP_ROOT = BUNDLE_ROOT / "app"
if not APP_ROOT.exists():
    # Also allow running this straight out of the repo (packaging/offline/bundle).
    APP_ROOT = BUNDLE_ROOT.parents[2]

DATA_DIR = Path(os.getenv("BAIF_DATA_DIR", APP_ROOT / "backend" / "data"))
HF_CACHE = DATA_DIR / "hf_cache"

os.environ["HF_HOME"] = str(HF_CACHE)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

TRANSLATION_DIR = DATA_DIR / "models" / "translation"

MB = 1024 * 1024

# repo_id -> (filename, minimum plausible size in bytes)
# The minimums are the point: a symlink flattened to a text stub is ~52 bytes
# and would pass a bare existence check.
HUB_MODELS: dict[str, list[tuple[str, int]]] = {
    "Systran/faster-whisper-medium": [
        ("model.bin", 1400 * MB),
        ("config.json", 1024),
        ("tokenizer.json", 1 * MB),
        ("vocabulary.txt", 100 * 1024),
    ],
    "facebook/nllb-200-distilled-600M": [
        ("pytorch_model.bin", 2000 * MB),
        ("config.json", 512),
        ("tokenizer.json", 1 * MB),
        ("sentencepiece.bpe.model", 1 * MB),
    ],
    "ai4bharat/indic-parler-tts": [
        ("model.safetensors", 3000 * MB),
        ("config.json", 1024),
        ("tokenizer.json", 1 * MB),
    ],
    # Dubbing's description tokenizer. vendor/audio_ba/modules/audio/tts.py:60
    # loads it from `model.config.text_encoder._name_or_path`, which resolves to
    # this repo at runtime -- the string never appears in the source, so this is
    # easy to leave out of a bundle and only discover when dubbing fails. No
    # weights here (those are inside parler-tts's own safetensors), just ~3 MB
    # of tokenizer files.
    "google/flan-t5-large": [
        ("tokenizer.json", 2 * MB),
        ("spiece.model", 700 * 1024),
        ("tokenizer_config.json", 1024),
    ],
}

# Loaded by local path, not by repo id (vendor/docs_baif/config.py points at
# TRANSLATION_MODEL_DIR). The three .py files are what makes
# trust_remote_code=True work with no network.
LOCAL_TRANSLATION_MODELS: dict[str, list[tuple[str, int]]] = {
    "indictrans2-en-indic-dist-200M": [
        ("model.safetensors", 1000 * MB),
        ("config.json", 512),
        ("modeling_indictrans.py", 10 * 1024),
        ("configuration_indictrans.py", 1024),
        ("tokenization_indictrans.py", 1024),
        ("dict.SRC.json", 100 * 1024),
        ("dict.TGT.json", 100 * 1024),
        ("model.SRC", 100 * 1024),
        ("model.TGT", 100 * 1024),
    ],
    "indictrans2-indic-en-dist-200M": [
        ("model.safetensors", 830 * MB),
        ("config.json", 512),
        ("modeling_indictrans.py", 10 * 1024),
    ],
    "indictrans2-indic-indic-dist-320M": [
        ("model.safetensors", 1150 * MB),
        ("config.json", 512),
        ("modeling_indictrans.py", 10 * 1024),
    ],
}

failures: list[str] = []
warnings: list[str] = []
checks = 0

# --bundle: a symlink is acceptable in a live dev checkout (that is how
# huggingface_hub stores things), but never in a staged bundle -- it will not
# survive the copy to the other machine. build-bundle.ps1 passes this.
strict_no_symlinks = False


def ok(message: str) -> None:
    print(f"  [ok]   {message}")


def fail(message: str) -> None:
    failures.append(message)
    print(f"  [FAIL] {message}")


def warn(message: str) -> None:
    warnings.append(message)
    print(f"  [warn] {message}")


def human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def check_file(path: Path, minimum: int, label: str) -> bool:
    global checks
    checks += 1

    note = ""
    if path.is_symlink():
        if strict_no_symlinks:
            fail(f"{label}: still a symlink -> {os.readlink(path)}; it will not survive the copy")
            return False
        if not path.exists():
            fail(f"{label}: broken symlink -> {os.readlink(path)}")
            return False
        note = " via symlink"

    if not path.is_file():
        fail(f"{label}: missing ({path})")
        return False

    # stat() follows the link, which is what we want: the question is whether
    # the real bytes are there, not how they are addressed.
    size = path.stat().st_size
    if size < minimum:
        fail(f"{label}: only {human(size)}, expected at least {human(minimum)} -- truncated or a link stub")
        return False

    ok(f"{label} ({human(size)}{note})")
    return True


# ----------------------------------------------------------------------
# Fast checks
# ----------------------------------------------------------------------


def check_hub_cache() -> None:
    global checks

    from huggingface_hub import try_to_load_from_cache

    print("\nHugging Face cache")
    print(f"  HF_HOME = {HF_CACHE}")

    for repo_id, files in HUB_MODELS.items():
        for filename, minimum in files:
            resolved = try_to_load_from_cache(
                repo_id=repo_id, filename=filename, cache_dir=str(HF_CACHE / "hub")
            )
            label = f"{repo_id}/{filename}"

            # try_to_load_from_cache returns the path, the _CACHED_NO_EXIST
            # sentinel, or None -- and only a str/Path means a real hit.
            if not isinstance(resolved, (str, Path)):
                checks += 1
                fail(f"{label}: not resolvable from the cache (refs/snapshots mismatch?)")
                continue

            check_file(Path(resolved), minimum, label)


def check_local_translation_models() -> None:
    print("\nIndicTrans2 checkpoints (loaded by path)")
    print(f"  dir = {TRANSLATION_DIR}")

    for name, files in LOCAL_TRANSLATION_MODELS.items():
        for filename, minimum in files:
            check_file(TRANSLATION_DIR / name / filename, minimum, f"{name}/{filename}")


def check_transformers_modules() -> None:
    print("\ntransformers dynamic-module cache")
    modules = HF_CACHE / "modules" / "transformers_modules"
    global checks
    checks += 1
    if modules.is_dir() and any(modules.rglob("modeling_indictrans.py")):
        ok(f"{modules} populated")
    else:
        # Not fatal on its own: each checkpoint dir carries its own copy of the
        # remote code, so transformers can regenerate this from disk. Flagged
        # anyway because if it IS missing and the checkpoints are too, the app
        # would need network for something it can never fetch offline.
        fail(f"{modules}: no cached IndicTrans2 remote code (checkpoint-local .py files must cover it)")


def check_frontend() -> None:
    print("\nFrontend build")
    dist = APP_ROOT / "frontend" / "dist"
    global checks
    checks += 1

    bundles = sorted(dist.glob("assets/*.js"))
    if not bundles:
        fail(f"{dist}: no built JS bundle -- the UI would 404")
        return

    text = bundles[0].read_text(encoding="utf-8", errors="replace")
    # src/api/index.js: String(import.meta.env.VITE_USE_MOCK) !== 'false'
    if '="false"' in text and '!=="false"' in text:
        ok(f"{bundles[0].name}: built with VITE_USE_MOCK=false (real backend)")
    else:
        fail(f"{bundles[0].name}: mock flag is not inlined as \"false\" -- this build talks to the FAKE in-memory backend")


def check_ffmpeg() -> None:
    import shutil

    global checks

    print("\nffmpeg")
    checks += 1

    # Look in the bundle first. On the packaging machine ffmpeg is usually on
    # PATH anyway, so checking PATH alone would happily pass a bundle whose
    # bin\ is empty -- and the failure would only show up on the target.
    bundled = [
        BUNDLE_ROOT / "bin" / "ffmpeg.exe",
        APP_ROOT / "backend" / ".venv" / "Scripts" / "ffmpeg.exe",
    ]
    for candidate in bundled:
        if candidate.is_file():
            ok(f"bundled at {candidate}")
            return

    found = shutil.which("ffmpeg")
    if found:
        warn(f"not in the bundle; using this machine's own {found}. The target machine will NOT have it.")
        ok("resolvable on PATH (this machine only)")
    else:
        fail("not found -- video jobs fail at audio extraction (vendor/video_baif/services/extractor.py)")


# ----------------------------------------------------------------------
# --full: load every model with the network cut off
# ----------------------------------------------------------------------


def block_network() -> None:
    """
    Make any outbound connection raise, so a model that still wants to reach
    Hugging Face fails here rather than looking fine on this machine and
    hanging on the target's air-gapped one.
    """

    import socket

    class _Blocked(socket.socket):
        def connect(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise OSError("network blocked by verify_offline.py --full")

        def connect_ex(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise OSError("network blocked by verify_offline.py --full")

    socket.socket = _Blocked  # type: ignore[misc, assignment]
    print("  network: blocked")


def load_all() -> None:
    print("\nLoading models (network blocked)")
    block_network()

    global checks

    checks += 1
    try:
        from faster_whisper import WhisperModel

        WhisperModel("medium", device="cpu", compute_type="int8")
        ok("faster-whisper medium")
    except Exception as exc:  # noqa: BLE001
        fail(f"faster-whisper medium: {type(exc).__name__}: {exc}")

    checks += 1
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
        AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-distilled-600M")
        ok("NLLB-200 distilled 600M")
    except Exception as exc:  # noqa: BLE001
        fail(f"NLLB-200: {type(exc).__name__}: {exc}")

    for name in LOCAL_TRANSLATION_MODELS:
        checks += 1
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            path = str(TRANSLATION_DIR / name)
            AutoTokenizer.from_pretrained(path, trust_remote_code=True)
            AutoModelForSeq2SeqLM.from_pretrained(path, trust_remote_code=True)
            ok(name)
        except Exception as exc:  # noqa: BLE001
            fail(f"{name}: {type(exc).__name__}: {exc}")

    checks += 1
    try:
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        tts = ParlerTTSForConditionalGeneration.from_pretrained("ai4bharat/indic-parler-tts")
        AutoTokenizer.from_pretrained("ai4bharat/indic-parler-tts")

        # The step that actually needs google/flan-t5-large in the cache.
        # Mirrors vendor/audio_ba/modules/audio/tts.py:60 exactly, indirection
        # included, so this fails here if that tokenizer was left out.
        encoder_repo = tts.config.text_encoder._name_or_path
        AutoTokenizer.from_pretrained(encoder_repo)
        ok(f"Indic Parler-TTS (+ description tokenizer from {encoder_repo})")
    except Exception as exc:  # noqa: BLE001
        fail(f"Indic Parler-TTS (dubbing only): {type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--full",
        action="store_true",
        help="also load every model with the network blocked (minutes, ~8 GB RAM)",
    )
    parser.add_argument(
        "--bundle",
        action="store_true",
        help="strict mode for a staged bundle: any surviving symlink is a failure",
    )
    args = parser.parse_args()

    global strict_no_symlinks
    strict_no_symlinks = args.bundle

    print(f"BAIF Bhasha offline verification\n  app  = {APP_ROOT}\n  data = {DATA_DIR}")

    if not DATA_DIR.is_dir():
        print(f"\nNo data directory at {DATA_DIR} -- wrong folder, or the models were never copied.")
        return 1

    check_local_translation_models()
    check_hub_cache()
    check_transformers_modules()
    check_frontend()
    check_ffmpeg()

    if args.full:
        load_all()

    print(f"\n{'-' * 60}")
    if failures:
        print(f"FAILED -- {len(failures)} of {checks} checks:")
        for message in failures:
            print(f"  - {message}")
        return 1

    print(f"PASSED -- {checks} checks.")
    for message in warnings:
        print(f"  warning: {message}")
    if not args.full:
        print("Re-run with --full to actually load every model with the network blocked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
