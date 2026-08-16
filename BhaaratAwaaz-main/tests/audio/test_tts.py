from modules.audio.tts import TTS


def main():

    tts = TTS()

    text = (
        "When I was young, I used to go "
        "to the park every day."
    )

    output = tts.synthesize(
        text=text,
        language="en",
        output_path="data/output/test_tts.wav",
    )

    print("=" * 60)
    print("BAHAARTAWAAZ TTS TEST")
    print("=" * 60)

    print(f"\nInput:")
    print(text)

    print(f"\nOutput:")
    print(output)

    print("\nStatus: SUCCESS")


if __name__ == "__main__":
    main()