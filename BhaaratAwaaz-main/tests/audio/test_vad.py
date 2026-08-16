from modules.audio.asr import ASR


AUDIO_FILE = "data/input/test.wav"


def main():

    asr = ASR(
        model_size="medium",
        device="cpu",
        compute_type="int8",
    )

    result = asr.transcribe(AUDIO_FILE)

    print("\n" + "=" * 70)
    print("VAD + ASR TEST")
    print("=" * 70)

    print(f"\nLanguage: {result['language']}")
    print(f"Probability: {result['language_probability']}")

    print("\nSegments:")
    print("-" * 70)

    for segment in result["segments"]:
        print(
            f"[{segment['start']:.2f}s -> "
            f"{segment['end']:.2f}s] "
            f"{segment['text']}"
        )


if __name__ == "__main__":
    main()