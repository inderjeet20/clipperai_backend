# Clipper AI Backend

FastAPI backend for video upload, Whisper transcription, simple retrieval, and Gemini timestamp scoring.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Whisper needs `ffmpeg` installed and available on PATH.

Gemini scoring:

```bash
$env:GEMINI_API_KEY="your_api_key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

Without `GEMINI_API_KEY`, the backend still returns real timestamps using a local scoring fallback.
