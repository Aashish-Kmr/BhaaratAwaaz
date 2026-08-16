from pathlib import Path

from modules.audio.asr import ASR


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

AUDIO_FILE = Path(
    "data/temp/2_marathi_normalized.wav"
)

OUTPUT_FILE = Path(
    "data/output/2_marathi.json"
)


# ------------------------------------------------------------
# Test
# ------------------------------------------------------------

def main():

    print("=" * 60)
    print("BhaaratAwaaz - ASR Test")
    print("=" * 60)

    print(f"\nInput audio : {AUDIO_FILE}")
    print(f"Output JSON : {OUTPUT_FILE}")

    # --------------------------------------------------------
    # Initialize ASR
    # --------------------------------------------------------

    print("\nLoading Faster-Whisper...")

    asr = ASR(
        model_size="small",
        device="cpu",
        compute_type="int8",
    )

    print("Model loaded.")

    # --------------------------------------------------------
    # Transcribe + save JSON
    # --------------------------------------------------------

    print("\nTranscribing...\n")

    result = asr.transcribe_to_json(
        audio_path=AUDIO_FILE,
        output_path=OUTPUT_FILE,
    )

    # --------------------------------------------------------
    # Display result
    # --------------------------------------------------------

    print("=" * 60)
    print("ASR RESULT")
    print("=" * 60)

    print(
        f"\nDetected language : "
        f"{result['language']}"
    )

    print(
        f"Language probability : "
        f"{result['language_probability']:.4f}"
    )

    print(
        f"Number of segments : "
        f"{len(result['segments'])}"
    )

    print("\nTranscript:")
    print("-" * 60)

    for segment in result["segments"]:

        print(
            f"[{segment['start']:.2f}s -> "
            f"{segment['end']:.2f}s] "
            f"{segment['text']}"
        )

    print("\n" + "=" * 60)
    print("ASR completed successfully.")
    print(f"JSON saved to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()