from app.services.translator import Translator


def main():

    translator = Translator()

    result = translator.translate_batch(
        [
            "शेतकऱ्यांनी पिकांची योग्य काळजी घेतली पाहिजे.",
            "पशूंच्या आरोग्याची नियमित तपासणी करणे आवश्यक आहे.",
        ],
        source_language="marathi",
        target_language="hindi",
    )

    for index, text in enumerate(
        result,
        start=1,
    ):
        print(f"{index}. {text}")


if __name__ == "__main__":
    main()