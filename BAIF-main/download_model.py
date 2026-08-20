from pathlib import Path

from huggingface_hub import snapshot_download


# --------------------------------------------------
# Project paths
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"


# --------------------------------------------------
# Required IndicTrans2 models
# --------------------------------------------------

MODELS = {
    "indictrans2-en-indic": {
        "repo_id": "ai4bharat/indictrans2-en-indic-dist-200M",
        "description": "English -> Hindi / Marathi",
    },
    "indictrans2-indic-en": {
        "repo_id": "ai4bharat/indictrans2-indic-en-dist-200M",
        "description": "Hindi / Marathi -> English",
    },
}


def is_model_downloaded(model_path):
    """
    Check whether the model appears to be downloaded.

    config.json is used as a lightweight marker instead
    of checking the size of model files.
    """

    return (
        model_path.exists()
        and (model_path / "config.json").exists()
    )


def download_model(model_name, model_config):
    """
    Download one IndicTrans2 model.
    """

    repo_id = model_config["repo_id"]
    description = model_config["description"]

    model_path = MODEL_DIR / model_name

    print()
    print("=" * 70)
    print(f"Model       : {model_name}")
    print(f"Repository  : {repo_id}")
    print(f"Purpose     : {description}")
    print(f"Destination : {model_path}")
    print("=" * 70)

    # --------------------------------------------------
    # Already downloaded
    # --------------------------------------------------

    if is_model_downloaded(model_path):
        print("Model already exists.")
        print("Skipping download.")
        return True

    # --------------------------------------------------
    # Create destination
    # --------------------------------------------------

    model_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Downloading model...")
    print("This may take some time.")
    print()

    try:

        snapshot_download(
            repo_id=repo_id,
            local_dir=str(model_path),
        )

    except Exception as exc:

        print()
        print("ERROR: Model download failed.")
        print(f"Model: {model_name}")
        print(f"Reason: {exc}")

        return False

    # --------------------------------------------------
    # Verify download
    # --------------------------------------------------

    if not is_model_downloaded(model_path):

        print()
        print("ERROR: Download completed but model")
        print("verification failed.")
        print(f"Expected: {model_path / 'config.json'}")

        return False

    print()
    print("Model downloaded successfully.")
    print(f"Location: {model_path}")

    return True


def main():

    print()
    print("=" * 70)
    print("BAIF Translator - Model Downloader")
    print("=" * 70)

    print()
    print("Required models:")
    print()

    for model_name, config in MODELS.items():

        print(
            f"- {model_name}: "
            f"{config['description']}"
        )

    print()
    print(f"Models directory: {MODEL_DIR}")

    # --------------------------------------------------
    # Create models directory
    # --------------------------------------------------

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------
    # Download models
    # --------------------------------------------------

    failed_models = []

    for model_name, model_config in MODELS.items():

        success = download_model(
            model_name=model_name,
            model_config=model_config,
        )

        if not success:
            failed_models.append(model_name)

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()
    print("=" * 70)

    if failed_models:

        print("MODEL DOWNLOAD FAILED")
        print("=" * 70)

        print()
        print("The following models could not be downloaded:")

        for model_name in failed_models:
            print(f"  - {model_name}")

        print()
        print(
            "Please check your internet connection and "
            "Hugging Face access."
        )

        raise SystemExit(1)

    print("ALL REQUIRED MODELS ARE READY")
    print("=" * 70)

    print()
    print("Available models:")

    for model_name in MODELS:
        print(
            f"  - {MODEL_DIR / model_name}"
        )

    print()
    print("You can now start the BAIF Translator API.")
    print()


if __name__ == "__main__":
    main()