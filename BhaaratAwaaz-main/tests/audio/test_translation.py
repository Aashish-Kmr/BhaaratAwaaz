from modules.audio.translation import Translator


TEST_SENTENCES = {
    "en": "When I was young, I used to go to the park every day.",
    "hi": "जब मैं छोटा था, मैं हर रोज़ पार्क जाता था।",
    "mr": "जेव्हा मी लहान होतो, तेव्हा मी दररोज उद्यानात जायचो.",
}


TRANSLATION_PAIRS = [
    ("en", "hi"),
    ("en", "mr"),
    ("hi", "en"),
    ("hi", "mr"),
    ("mr", "en"),
    ("mr", "hi"),
]


def main():

    translator = Translator(
        model_root="models/audio",
        device="cpu",
    )

    for source, target in TRANSLATION_PAIRS:

        print("\n" + "=" * 70)
        print(f"{source.upper()} → {target.upper()}")
        print("=" * 70)

        text = TEST_SENTENCES[source]

        print(f"\nInput:")
        print(text)

        try:
            translation = translator.translate(
                text=text,
                source_language=source,
                target_language=target,
            )

            print("\nTranslation:")
            print(translation)

            print("\nStatus: SUCCESS")

        except Exception as exc:

            print("\nStatus: FAILED")
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()