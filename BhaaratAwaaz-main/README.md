# BhaaratAwaaz

Offline multilingual audio translation and speech synthesis pipeline for **Marathi (mr), Hindi (hi), and English (en)**.

BhaaratAwaaz accepts an input audio file, performs speech recognition, translates the recognized text into the requested target language, and synthesizes the translated text back into audio.

## 1. System Overview

The current audio pipeline is:

```text
Input Audio
    |
    v
+----------------------+
| Audio Preprocessing  |
| PyAV                 |
| - validation         |
| - duration check     |
| - mono               |
| - 16 kHz             |
| - PCM 16-bit WAV     |
+----------+-----------+
           |
           v
+----------------------+
| ASR                  |
| faster-whisper       |
| medium               |
| CPU + INT8           |
+----------+-----------+
           |
           v
+----------------------+
| Translation          |
| IndicTrans2          |
| 200M                 |
+----------+-----------+
           |
           v
+----------------------+
| TTS                  |
| Indic Parler-TTS     |
| ai4bharat/           |
| indic-parler-tts     |
+----------+-----------+
           |
           v
    Output WAV Audio
```

The pipeline also generates a JSON file containing processing metadata and translated segments.

---

# 2. Supported Languages

| Language | Code |
|---|---|
| English | `en` |
| Hindi | `hi` |
| Marathi | `mr` |

The source language is optional.

If `source_language` is not provided, Faster-Whisper performs language detection.

The target language is required.

---

# 3. Current Models

## ASR

The project currently uses:

```text
faster-whisper
Model: medium
Device: CPU
Compute type: INT8
```

The ASR model is configured through `shared/config.py`.

The current implementation uses Faster-Whisper's integrated Silero VAD:

```python
vad_filter=True
```

with:

```python
vad_parameters={
    "min_silence_duration_ms": 500,
}
```

No separate `vad.py` processing step is currently required by the main pipeline.

## Translation

The project uses an IndicTrans2 model for translation.

The current local model directory is configured through:

```python
Config.TRANSLATION_MODEL_DIR
```

The pipeline supports translations between the configured `en`, `hi`, and `mr` languages.

## TTS

The project uses:

```text
ai4bharat/indic-parler-tts
```

through:

```python
ParlerTTSForConditionalGeneration
```

The current implementation generates WAV audio.

TTS currently runs on CPU when CUDA is unavailable.

**Current performance note:** TTS is the slowest stage on the development CPU environment. Short input files can take several minutes to synthesize. This is a known current limitation and is separate from ASR/translation correctness.

---

# 4. Audio Constraints

The preprocessing module currently supports:

```text
.wav
.mp3
.m4a
.aac
.flac
.ogg
.opus
.webm
.mp4
```

The pipeline itself accepts:

```text
.wav
.mp3
.m4a
.flac
.ogg
.aac
```

Maximum input duration:

```text
30 minutes
```

Audio is normalized to:

```text
Sample rate : 16,000 Hz
Channels    : 1 (mono)
Format      : WAV
Encoding    : PCM signed 16-bit
```

PyAV is used for decoding and normalization, so a separate system `ffmpeg.exe` is not required by the preprocessing implementation.

---

# 5. Requirements

Recommended development environment:

```text
Windows 11
Python 3.x
16 GB RAM minimum
512 GB storage
```

The models require significant disk space.

The current TTS model alone downloads several GB of model data.

For a complete setup, allow additional disk space for:

- Python packages
- Faster-Whisper model files
- IndicTrans2 model files
- Indic Parler-TTS model files
- Hugging Face cache
- generated audio
- temporary normalized audio

---

# 6. Repository Setup

Clone the repository and enter the project directory:

```powershell
git clone <YOUR_REPOSITORY_URL>
cd BhaaratAwaaz
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, use the appropriate Python/PowerShell execution-policy configuration for your environment.

Verify Python:

```powershell
python --version
```

---

# 7. Install Dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install project dependencies:

```powershell
pip install -r requirements.txt
```

The requirements include the packages used by:

- Faster-Whisper
- IndicTrans2
- Indic Parler-TTS
- PyTorch
- PyAV
- FastAPI
- Uvicorn
- audio processing
- testing

---

# 8. Model Setup

The application uses Hugging Face models.

On the first execution, required models may be downloaded and cached locally.

## Faster-Whisper

The current ASR configuration uses:

```text
medium
```

The first ASR execution downloads the corresponding Faster-Whisper model if it is not already available locally.

## IndicTrans2

The configured IndicTrans2 model must be available at the path specified by:

```python
Config.TRANSLATION_MODEL_DIR
```

If the selected Hugging Face model is restricted, authentication/access approval may be required before downloading it.

## Indic Parler-TTS

The TTS implementation loads:

```text
ai4bharat/indic-parler-tts
```

The first TTS execution downloads the required model files and tokenizer files.

After the models have been downloaded, the application can use the local Hugging Face cache without downloading the model again for every request.

---

# 9. Configuration

The main configuration is located in:

```text
shared/config.py
```

Relevant configuration includes:

```text
ASR_MODEL
ASR_DEVICE
ASR_COMPUTE_TYPE
TRANSLATION_MODEL_DIR
TRANSLATION_DEVICE
TTS_DEVICE
SAMPLE_RATE
CHANNELS
AUDIO_FORMAT
```

Example ASR configuration:

```text
ASR_MODEL=medium
ASR_DEVICE=cpu
ASR_COMPUTE_TYPE=int8
```

For TTS, the current implementation can select:

```text
cuda
```

when CUDA is available, otherwise:

```text
cpu
```

The configuration value should be consistent with how `TTS` is initialized.

---

# 10. Directory Structure

Current project structure:

```text
BhaaratAwaaz/
│
├── api/
│   └── audio.py
│
├── modules/
│   └── audio/
│       ├── __init__.py
│       ├── preprocessing.py
│       ├── vad.py
│       ├── asr.py
│       ├── translation.py
│       ├── tts.py
│       └── pipeline.py
│
├── shared/
│   ├── __init__.py
│   ├── config.py
│   └── logging.py
│
├── tests/
│   └── audio/
│       ├── test_preprocessing.py
│       ├── test_vad.py
│       ├── test_asr.py
│       ├── test_translation.py
│       ├── test_tts.py
│       └── test_pipeline.py
│
├── models/
│   └── audio/
│       └── indictrans2-indic-en-dist-200M
│
├── data/
│   ├── input/
│   ├── output/
│   └── temp/
│
├── main.py
├── requirements.txt
└── README.md
```

### Module responsibilities

### `preprocessing.py`

Responsible for:

- input validation
- metadata extraction
- duration validation
- audio decoding
- resampling
- mono conversion
- WAV/PCM normalization

### `vad.py`

Contains the standalone VAD-related testing/implementation work.

The current production ASR path uses Faster-Whisper's integrated VAD configuration directly in `asr.py`.

### `asr.py`

Responsible for:

- loading Faster-Whisper
- speech-to-text
- optional source-language selection
- automatic language detection
- timestamped segments

### `translation.py`

Responsible for:

- loading IndicTrans2
- translating ASR segments
- maintaining source/target language information

### `tts.py`

Responsible for:

- loading Indic Parler-TTS
- selecting the configured speaker
- synthesizing translated text
- writing WAV output

### `pipeline.py`

Orchestrates:

```text
Preprocessing
    ↓
ASR
    ↓
Translation
    ↓
TTS
    ↓
JSON metadata
```

### `api/audio.py`

Provides the FastAPI endpoint for uploaded audio.

### `main.py`

Creates the FastAPI application and registers the audio router.

---

# 11. Test Individual Modules

Tests can be executed from the project root.

## Preprocessing

```powershell
python -m tests.audio.test_preprocessing
```

## VAD

```powershell
python -m tests.audio.test_vad
```

## ASR

```powershell
python -m tests.audio.test_asr
```

## Translation

```powershell
python -m tests.audio.test_translation
```

## TTS

```powershell
python -m tests.audio.test_tts
```

## Complete Pipeline

```powershell
python -m tests.audio.test_pipeline
```

The complete pipeline test performs:

```text
input.wav
   ↓
preprocessing
   ↓
ASR
   ↓
translation
   ↓
TTS
   ↓
test_en.wav
   +
test_translation.json
```

---

# 12. Running the FastAPI Application

From the project root:

```powershell
uvicorn main:app --reload
```

The application runs at:

```text
http://127.0.0.1:8000
```

Root endpoint:

```text
GET /
```

Expected response:

```json
{
  "service": "BhaaratAwaaz",
  "status": "running"
}
```

Health endpoint:

```text
GET /health
```

Expected response:

```json
{
  "status": "healthy"
}
```

---

# 13. Swagger API Documentation

FastAPI automatically provides Swagger UI.

Open:

```text
http://127.0.0.1:8000/docs
```

The audio translation endpoint appears under:

```text
Audio
```

Endpoint:

```text
POST /audio/translate
```

---

# 14. Audio Translation Endpoint

## Endpoint

```text
POST /audio/translate
```

## Multipart form fields

### `audio_file`

Required.

The uploaded input audio file.

### `target_language`

Required.

One of:

```text
en
hi
mr
```

### `source_language`

Optional.

One of:

```text
en
hi
mr
```

If omitted, ASR detects the source language.

---

# 15. Using Swagger

Open:

```text
http://127.0.0.1:8000/docs
```

Expand:

```text
POST /audio/translate
```

Click:

```text
Try it out
```

Select:

```text
audio_file
```

Choose an audio file.

For example:

```text
test.wav
```

Set:

```text
target_language = en
```

Optionally set:

```text
source_language = mr
```

Click:

```text
Execute
```

The server processes:

```text
Audio
 ↓
Preprocessing
 ↓
ASR
 ↓
Translation
 ↓
TTS
```

The response is a WAV audio file containing the translated speech.

---

# 16. Using cURL

Example:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/audio/translate" `
  -F "audio_file=@data/input/test.wav" `
  -F "target_language=en" `
  -F "source_language=mr" `
  --output translated.wav
```

If source-language detection is desired:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/audio/translate" `
  -F "audio_file=@data/input/test.wav" `
  -F "target_language=en" `
  --output translated.wav
```

The resulting:

```text
translated.wav
```

contains the synthesized target-language audio.

---

# 17. API Processing Flow

For a request such as:

```text
source_language = mr
target_language = en
```

the server performs:

```text
test.wav
   |
   v
Validate input
   |
   v
Normalize audio
   |
   v
Faster-Whisper
   |
   v
Marathi transcript
   |
   v
IndicTrans2
   |
   v
English translated segments
   |
   v
Indic Parler-TTS
   |
   v
English WAV audio
```

Example segment:

```json
{
  "start": 10.43,
  "end": 13.43,
  "source_text": "क्रिस लिन ने बिग बैश लिग मधिल",
  "translated_text": "Chris Lynn in the Big Bash League"
}
```

The translated segments are combined into text before TTS synthesis.

---

# 18. Pipeline JSON Output

The pipeline also writes a JSON file under:

```text
data/output/
```

Example structure:

```json
{
  "audio_file": "...",
  "normalized_audio": {
    "file": "...",
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav"
  },
  "asr": {
    "model": "medium",
    "device": "cpu",
    "compute_type": "int8",
    "language": "mr",
    "language_probability": 0.71
  },
  "translation": {
    "source_language": "mr",
    "target_language": "en"
  },
  "tts": {
    "language": "en",
    "output_file": "..."
  },
  "output_audio": "...",
  "segments": []
}
```

---

# 19. Model Loading and API Requests

The API creates the `AudioPipeline` at application startup:

```python
pipeline = AudioPipeline()
```

The pipeline initializes:

```text
ASR
Translation
TTS
```

once for the running application process.

Therefore, the models are not intentionally reloaded for every API request.

A request reuses the already initialized model objects.

However, running with:

```powershell
uvicorn main:app --reload
```

uses Uvicorn's development reloader. Code changes can cause the application process to restart, which means models can be loaded again.

For normal execution without the development reloader:

```powershell
uvicorn main:app
```

---

# 20. Current Performance Characteristics

The current development configuration is CPU-based:

```text
ASR:
medium + CPU + INT8

Translation:
IndicTrans2 200M

TTS:
Indic Parler-TTS + CPU when CUDA is unavailable
```

ASR and translation have already been tested successfully.

TTS currently has substantially higher latency on CPU.

For this reason, the end-to-end API response time can be significantly longer than the input audio duration.

This is currently a performance limitation rather than a pipeline failure.

Potential future optimization areas include:

- GPU/CUDA inference
- TTS model optimization
- TTS chunking
- lower-latency TTS model selection
- batching
- asynchronous/background processing
- caching
- streaming output

These are not required for the current functional implementation.

---

# 21. Hugging Face Warnings

On Windows, Hugging Face may display a warning similar to:

```text
huggingface_hub cache-system uses symlinks by default...
```

This indicates that the Windows environment does not currently support the symlink-based Hugging Face cache optimization.

The model can still be downloaded and used.

The warning does not indicate a model failure.

Windows Developer Mode or running the relevant process with appropriate administrator privileges can enable symlink support.

Another message that may appear during TTS initialization is:

```text
Flash attention 2 is not installed
```

This indicates that Flash Attention 2 is unavailable in the current environment.

The current TTS implementation can still run without it.

The following warning can also appear:

```text
The attention mask is not set and cannot be inferred...
```

This is emitted by the Transformers/TTS stack during generation. The current TTS test successfully generated audio despite the warning.

These messages should be distinguished from actual exceptions or failed requests.

---

# 22. Offline Operation

The intended deployment model is:

```text
Initial setup
     |
     +-- install Python dependencies
     |
     +-- obtain/download required models
     |
     v
Models available locally
     |
     v
Application can process audio locally
```

The application itself does not require a cloud speech-recognition, translation, or TTS API.

Model availability is the important requirement for offline execution.

If a required model has not previously been downloaded or is not available locally, the first model initialization may require network access.

---

# 23. Recommended First-Time Setup Sequence

After creating the environment:

```powershell
python -m tests.audio.test_preprocessing
python -m tests.audio.test_asr
python -m tests.audio.test_translation
python -m tests.audio.test_tts
python -m tests.audio.test_pipeline
```

Once all individual components work, start the API:

```powershell
uvicorn main:app
```

Then open:

```text
http://127.0.0.1:8000/docs
```

and test:

```text
POST /audio/translate
```

---

# 24. Current Functional Scope

The current implementation provides:

- audio file validation
- maximum 30-minute input validation
- audio normalization
- Faster-Whisper ASR
- automatic source-language detection
- optional explicit source language
- IndicTrans2 translation
- Marathi/Hindi/English support
- Indic Parler-TTS synthesis
- WAV output
- pipeline JSON metadata
- FastAPI REST endpoint
- Swagger documentation
- local/offline model execution after model setup

---

# 25. Current Known Limitations

### TTS latency

TTS is currently slow on CPU and is the primary end-to-end performance bottleneck.

### Model size

The ASR, translation, and TTS models require substantial disk space and RAM.

### Translation quality

Translation quality depends on:

- ASR transcription quality
- source-language detection
- IndicTrans2 model quality
- audio quality

Errors in ASR can propagate into translation and TTS.

### API processing model

The current endpoint performs the complete pipeline during the request.

For longer audio files, the HTTP request therefore remains active until:

```text
ASR + Translation + TTS
```

has completed.

A production deployment may eventually move long-running processing to a background job architecture.

---

# 26. Development Checklist

Before handing the project to another developer:

```text
[ ] Clone repository
[ ] Create virtual environment
[ ] Install requirements.txt
[ ] Configure shared/config.py
[ ] Make required models available
[ ] Run preprocessing test
[ ] Run ASR test
[ ] Run translation test
[ ] Run TTS test
[ ] Run complete pipeline test
[ ] Start FastAPI
[ ] Open /docs
[ ] Test /audio/translate
```

---

# 27. Quick Start

For an already prepared environment:

```powershell
.\.venv\Scripts\Activate.ps1

python -m tests.audio.test_pipeline

uvicorn main:app
```

Then open:

```text
http://127.0.0.1:8000/docs
```

Use:

```text
POST /audio/translate
```

with:

```text
audio_file       = <input audio>
source_language  = mr
target_language  = en
```

The endpoint returns the generated translated WAV audio.
