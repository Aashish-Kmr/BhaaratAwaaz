from handlers.pdf_handler import pdf_handler


INPUT_FILE = "test_files/sample.pdf"
OUTPUT_FILE = "test_files/sample_mr.pdf"


print("=" * 60)
print("PDF TRANSLATION TEST")
print("=" * 60)

print("Input :", INPUT_FILE)
print("Output:", OUTPUT_FILE)

pdf_handler.translate(
    input_file=INPUT_FILE,
    output_file=OUTPUT_FILE,
    target_language="mr",
    source_language="en",
)

print()
print("PDF translation completed successfully.")
print("Output:", OUTPUT_FILE)