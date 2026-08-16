from translator import translator
from handlers.pptx_handler import pptx_handler


input_file = "test_files/sample.pptx"
output_file = "translated/sample_mr.pptx"

print("Starting PPTX translation...")

pptx_handler.translate(
    input_file=input_file,
    output_file=output_file,
    target_language="mr",
)

print("PPTX translation completed.")
print("Output:", output_file)