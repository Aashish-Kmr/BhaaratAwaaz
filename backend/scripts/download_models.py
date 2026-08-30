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
login` (or set `HF_TOKEN`) in this shell so the download requests are
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


# Both pipelines now use "medium" -- audio via vendor/audio_ba's Config,
# video via Transcriber.MODEL_SIZE. Video was raised from "small" for
# better Indic accuracy, which also means only one Whisper model has to
# ship. If you drop video back to "small", add it back here.
ASR_MODELS = ("medium",)


def download_asr_model() -> None:
    from faster_whisper import WhisperModel

    for size in ASR_MODELS:
        print(f"[asr] warming faster-whisper '{size}' cache ...")
        WhisperModel(size, device="cpu", compute_type="int8")
        print(f"[asr] {size}: done")


def download_video_translation_model() -> None:
    """
    NLLB-200 distilled 600M -- used by the vendored video pipeline
    (vendor/video_baif/services/translator.py). Not gated, so this needs
    no Hugging Face login, but it is a ~2.4 GB download.

    This repo publishes weights only as pytorch_model.bin (no safetensors
    variant), so unlike the IndicTrans2 downloads above there is no
    redundant second format to skip.

    Large single-file downloads over a slow link are the one step here
    that regularly times out mid-transfer, so this retries; huggingface_hub
    resumes from the partial blob rather than restarting.
    """

    from huggingface_hub import snapshot_download

    model_name = "facebook/nllb-200-distilled-600M"
    attempts = 5

    print(f"[video-translation] warming {model_name} cache (~2.4 GB) ...")

    for attempt in range(1, attempts + 1):
        try:
            snapshot_download(repo_id=model_name)
            break
        except Exception as exc:
            if attempt == attempts:
                raise
            print(
                f"[video-translation] attempt {attempt}/{attempts} failed "
                f"({type(exc).__name__}); resuming ..."
            )

    print("[video-translation] done")


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
    parser.add_argument("--skip-asr", action="store_true", help="skip the Whisper downloads")
    parser.add_argument(
        "--skip-translation", action="store_true", help="skip the IndicTrans2 download"
    )
    parser.add_argument(
        "--skip-video-translation",
        action="store_true",
        help="skip the NLLB-200 download used by the video pipeline",
    )
    args = parser.parse_args()

    if not args.skip_translation:
        download_translation_models()
    if not args.skip_video_translation:
        download_video_translation_model()
    if not args.skip_asr:
        download_asr_model()
    if not args.skip_tts:
        download_tts_model()

    print("\nAll requested models are ready.")


if __name__ == "__main__":
    main()
