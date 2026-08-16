from modules.audio.pipeline import AudioPipeline
from shared.config import Config


def main():

    pipeline = AudioPipeline()

    result = pipeline.process(
        input_audio=Config.INPUT_DIR / "1_english.wav",
        target_language="hi",
    )

    print("\n" + "=" * 70)
    print("BAHAARTAWAAZ AUDIO PIPELINE")
    print("=" * 70)

    print(
        f"\nSource language: "
        f"{result['asr']['language']}"
    )

    print(
        f"Target language: "
        f"{result['translation']['target_language']}"
    )

    # --------------------------------------------------
    # Translated text
    # --------------------------------------------------

    print("\nTranslated text:")
    print("-" * 70)

    translated_text = " ".join(
        segment["translated_text"]
        for segment in result["segments"]
    )

    print(translated_text)

    # --------------------------------------------------
    # TTS output
    # --------------------------------------------------

    print("\nTTS output:")
    print("-" * 70)

    print(result["tts"]["output_file"])

    # --------------------------------------------------
    # JSON output
    # --------------------------------------------------

    print("\nOutput JSON:")
    print(result["output_file"])

    # --------------------------------------------------
    # Segments
    # --------------------------------------------------

    print("\nSegments:")
    print("-" * 70)

    for segment in result["segments"]:

        print(
            f"[{segment['start']:.2f}s -> "
            f"{segment['end']:.2f}s]"
        )

        print(
            f"Source:     "
            f"{segment['source_text']}"
        )

        print(
            f"Translated: "
            f"{segment['translated_text']}"
        )


if __name__ == "__main__":
    main()