
from pathlib import Path
from fastapi import HTTPException

from app.core.config import WHISPER_MODEL
from app.models.schemas import TranscriptSegment

def transcribe_video(video_path: Path) -> list[TranscriptSegment]:
    try:
        import whisper
    except ImportError as error:
        raise HTTPException(
            status_code=500,
            detail="Whisper is not installed. Run pip install -r requirements.txt in backend.",
        ) from error

    try:
        model = whisper.load_model(WHISPER_MODEL)
        result = model.transcribe(str(video_path), fp16=False, word_timestamps=True)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail="Whisper could not run. Make sure ffmpeg is installed and available on PATH.",
        ) from error

    segments = []
    for segment in result.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if text:
            # Extract word-level timestamps if available
            words = []
            for w in segment.get("words", []):
                words.append({
                    "word": str(w.get("word", "")),
                    "start": float(w.get("start", 0.0)),
                    "end": float(w.get("end", 0.0))
                })
            
            segments.append(
                TranscriptSegment(
                    start=float(segment.get("start", 0)),
                    end=float(segment.get("end", 0)),
                    text=text,
                    words=words
                )
            )

    if not segments and result.get("text"):
        segments.append(
            TranscriptSegment(start=0, end=30, text=str(result["text"]).strip())
        )

    return segments
