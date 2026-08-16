from handlers.csv_handler import csv_handler


INPUT_FILE = "test_files/sample.csv"
OUTPUT_FILE = "test_files/sample_mr.csv"


print("=" * 60)
print("CSV TRANSLATION TEST")
print("=" * 60)

print("Input :", INPUT_FILE)
print("Output:", OUTPUT_FILE)

csv_handler.translate(
    input_file=INPUT_FILE,
    output_file=OUTPUT_FILE,
    target_language="mr",
    source_language="en",
)

print()
print("CSV translation completed successfully.")
print("Output:", OUTPUT_FILE)