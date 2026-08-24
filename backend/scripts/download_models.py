"""
One-time model setup for BAIF Bhasha.

Downloads everything the app needs into a local cache so it can run fully
offline afterward:

  - 3x IndicTrans2 translation checkpoints (direct en<->hi, en<->mr, hi<->mr)
  - faster-whisper ASR model (warms the default HF cache)
  - Indic Parler-TTS dubbing model (warms the default HF cache)

Run from the `backend/` directory:

    python scripts/download_models.py
    python scripts/download_models.py --skip-tts   # smaller/faster, no dubbing bonus

This is also what a packaged executable's first-run "setup" step calls.

IMPORTANT -- four of these five repos on Hugging Face are gated (everything
except faster-whisper): before this script can fetch them, log into a
Hugging Face account, visit each repo page below, and request/accept access
(the three IndicTrans2 ones are usually instant; indic-parler-tts says
"authorized list" and may need manual review), then run `huggingface-cli
login` (or set `HF_TOKEN`, or paste the token into a `.env` file at the
repo root -- see `_load_hf_token` below) so the download requests are
authenticated:

    https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M
    https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
    https://huggingface.co/ai4bharat/indictrans2-indic-indic-dist-320M
    https://huggingface.co/ai4bharat/indic-parler-tts   (only if not using --skip-tts)

This is a one-time, per-account step -- there's no way to script around it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402

# config.py defaults HF_HUB_OFFLINE=1 so the running app never tries to
# write to its (possibly read-only, e.g. under Program Files) model cache --
# but this script's whole job is downloading, so it needs network access.
os.environ["HF_HUB_OFFLINE"] = "0"


def _load_hf_token() -> str | None:
    """
    Find a Hugging Face token and put it where huggingface_hub looks.

    `huggingface-cli login` is still the nicest way to do this on a machine
    you own, but it isn't available everywhere this script runs: a Docker
    build has no interactive shell, and someone handed a zip of this repo
    for a demo shouldn't have to learn a second CLI to get past a gated
    repo. So a token in a plain file works too, checked in this order:

      1. HF_TOKEN / HUGGING_FACE_HUB_TOKEN already in the environment
         (what Docker Compose passes through from .env)
      2. the file named by BAIF_HF_TOKEN_FILE (a BuildKit secret mount,
         during a `--build-arg BAKE_MODELS=1` image build)
      3. hf_token.txt or .env, in the repo root or in backend/

    Files may be either a bare token on a line of their own or KEY=VALUE
    lines; surrounding quotes and Windows CRs are stripped either way.
    Returning None is fine -- huggingface_hub then falls back to whatever
    `huggingface-cli login` cached, and only the gated repos fail.
    """

    for env_var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        token = os.environ.get(env_var, "").strip()
        if token:
            os.environ["HF_TOKEN"] = token
            return token

    here = Path(__file__).resolve().parent.parent  # backend/
    candidates = []
    if os.environ.get("BAIF_HF_TOKEN_FILE"):
        candidates.append(Path(os.environ["BAIF_HF_TOKEN_FILE"]))
    for directory in (here.parent, here):
        candidates += [directory / "hf_token.txt", directory / ".env"]

    for path in candidates:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue

        token = None
        for line in raw.splitlines():
            line = line.strip().strip("\ufeff")
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                if key.strip().upper() in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
                    token = value
                    break
            elif token is None:
                token = line  # bare-token file

        token = (token or "").strip().strip("\"'")
        if token:
            os.environ["HF_TOKEN"] = token
            print(f"[auth] using Hugging Face token from {path}")
            return token

    return None


TRANSLATION_REPOS = {
    "indictrans2-en-indic-dist-200M": "ai4bharat/indictrans2-en-indic-dist-200M",
    "indictrans2-indic-en-dist-200M": "ai4bharat/indictrans2-indic-en-dist-200M",
    "indictrans2-indic-indic-dist-320M": "ai4bharat/indictrans2-indic-indic-dist-320M",
}


def download_translation_models() -> None:
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import GatedRepoError

    for local_name, repo_id in TRANSLATION_REPOS.items():
        target = config.TRANSLATION_MODEL_DIR / local_name
        if (target / "config.json").exists() and (target / "model.safetensors").exists():
            print(f"[translation] {local_name}: already present, skipping")
            continue

        print(f"[translation] {local_name}: downloading {repo_id} ...")
        try:
            # Each repo carries both model.safetensors and a legacy
            # pytorch_model.bin of the same weights -- transformers uses
            # safetensors automatically when present, so skip the .bin copy
            # (it roughly doubles the download/disk footprint for nothing).
            snapshot_download(
                repo_id=repo_id, local_dir=str(target), ignore_patterns=["*.bin"]
            )
        except GatedRepoError:
            print(
                f"\n[translation] {repo_id} is a gated repo and your Hugging Face "
                f"credentials don't have access yet.\n"
                f"  1. Log in at https://huggingface.co/{repo_id} and click "
                f"'Agree and access repository'.\n"
                f"  2. Run `huggingface-cli login` (or set HF_TOKEN) in this shell.\n"
                f"  3. Re-run this script.\n"
            )
            raise
        print(f"[translation] {local_name}: done")


def download_asr_model() -> None:
    from faster_whisper import WhisperModel

    print(f"[asr] warming faster-whisper '{config.ASR_MODEL}' cache ...")
    WhisperModel(config.ASR_MODEL, device=config.ASR_DEVICE, compute_type=config.ASR_COMPUTE_TYPE)
    print("[asr] done")


def download_tts_model() -> None:
    from huggingface_hub.utils import GatedRepoError
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer

    print("[tts] warming Indic Parler-TTS cache (this one is several GB) ...")
    try:
        ParlerTTSForConditionalGeneration.from_pretrained("ai4bharat/indic-parler-tts")
        AutoTokenizer.from_pretrained("ai4bharat/indic-parler-tts")
    except (GatedRepoError, OSError) as exc:
        if "gated repo" not in str(exc).lower():
            raise
        print(
            "\n[tts] ai4bharat/indic-parler-tts is a gated repo too (this one may "
            "need manual approval, not just a click-through).\n"
            "  1. Request access at https://huggingface.co/ai4bharat/indic-parler-tts\n"
            "  2. Once granted, re-run this script.\n"
            "  This is the audio-dubbing bonus only -- everything else (documents, "
            "video subtitles, audio transcript+translation) works without it. "
            "Use --skip-tts to leave it out for now.\n"
        )
        raise
    print("[tts] done")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tts", action="store_true", help="skip the Parler-TTS download")
    parser.add_argument("--skip-asr", action="store_true", help="skip the Whisper download")
    parser.add_argument(
        "--skip-translation", action="store_true", help="skip the IndicTrans2 download"
    )
    args = parser.parse_args()

    if _load_hf_token() is None:
        print(
            "[auth] no HF_TOKEN found in the environment, hf_token.txt or .env -- "
            "falling back to any `huggingface-cli login` credentials.\n"
            "       Gated repos will fail without one; see the module docstring."
        )

    if not args.skip_translation:
        download_translation_models()
    if not args.skip_asr:
        download_asr_model()
    if not args.skip_tts:
        download_tts_model()

    print("\nAll requested models are ready.")


if __name__ == "__main__":
    main()
