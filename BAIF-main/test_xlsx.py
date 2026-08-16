from handlers.xlsx_handler import xlsx_handler


INPUT_FILE = "test_files/sample.xlsx"
OUTPUT_FILE = "test_files/sample_mr.xlsx"


print("=" * 60)
print("XLSX TRANSLATION TEST")
print("=" * 60)

print("Input :", INPUT_FILE)
print("Output:", OUTPUT_FILE)

xlsx_handler.translate(
    input_file=INPUT_FILE,
    output_file=OUTPUT_FILE,
    target_language="mr",
)

print()
print("Translation completed successfully.")
print("Output:", OUTPUT_FILE)