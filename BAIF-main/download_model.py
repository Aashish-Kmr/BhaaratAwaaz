from pathlib import Path

from huggingface_hub import snapshot_download


BASE_DIR = Path(__file__).resolve().parent

MODEL_DIR = (
    BASE_DIR
    / "models"
    / "indictrans2-indic-en"
)

MODEL_ID = "ai4bharat/indictrans2-indic-en-dist-200M"


print("Downloading IndicTrans2 Indic -> English model...")
print("Model:", MODEL_ID)
print("Destination:", MODEL_DIR)


snapshot_download(
    repo_id=MODEL_ID,
    local_dir=str(MODEL_DIR),
)

print()
print("Model downloaded successfully.")
print("Location:", MODEL_DIR)