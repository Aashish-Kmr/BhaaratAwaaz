# BAIF Translator

BAIF Translator is a Python/FastAPI based document translation application.

## Supported Formats

The application currently supports:

- DOCX
- PDF
- PPTX
- XLSX
- CSV

## Supported Languages

The translator supports:

- English
- Hindi
- Marathi

The source language can be detected automatically by the language detection component.

## Project Structure

```text
BAIF/
├── api/
│   └── routes.py
├── fonts/
│   └── NotoSansDevanagari-Regular.ttf
├── handlers/
│   ├── csv_handler.py
│   ├── docx_handler.py
│   ├── pdf_handler.py
│   ├── pptx_handler.py
│   └── xlsx_handler.py
├── services/
│   └── translation_service.py
├── utils/
│   └── language.py
├── app.py
├── config.py
├── download_model.py
├── requirements.txt
└── translator.py

Installation

Create a Python virtual environment:

python -m venv venv

Activate it on Windows:

venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt
Model Setup

The translation model is not stored in Git.

Download the required model using:

python download_model.py

The downloaded model is stored locally under the models/ directory.

Run the Application

Start FastAPI with:

uvicorn app:app --reload

The API will then be available through the configured local host/port.

Translation API

The application provides a translation endpoint that accepts an uploaded document and target language.

Supported document types:

DOCX
PDF
PPTX
XLSX
CSV
PDF Translation

PDF translation uses the Devanagari Unicode font:

fonts/NotoSansDevanagari-Regular.ttf

The PDF handler supports translated text placement and Hindi/Marathi Unicode rendering.

Test Files

Sample files used during development/testing are available under:

test_files/
Git

The following local/generated resources are intentionally excluded from Git:

Python virtual environment
Downloaded translation models
Uploaded files
Generated translated files
Python cache files
Local environment/secrets