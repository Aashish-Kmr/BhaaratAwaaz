from translator import translator


tests = [
    ("en", "mr", "India is a beautiful country."),
    ("en", "hi", "India is a beautiful country."),

    ("mr", "en", "भारत हा एक सुंदर देश आहे."),
    ("hi", "en", "भारत एक सुंदर देश आहे।"),

    ("hi", "mr", "भारत एक सुंदर देश आहे।"),
    ("mr", "hi", "भारत हा एक सुंदर देश आहे."),
]


for source, target, text in tests:

    print()
    print("=" * 60)
    print(f"{source.upper()} -> {target.upper()}")
    print("=" * 60)

    result = translator.translate(
        text,
        source,
        target,
    )

    print()
    print("INPUT:")
    print(text)

    print()
    print("OUTPUT:")
    print(result)