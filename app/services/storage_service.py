import json
import uuid
from pathlib import Path
from typing import Any
from fastapi import UploadFile, HTTPException

from app.core.config import PROJECTS_FILE, ALLOWED_EXTENSIONS, UPLOAD_DIR

def read_projects() -> list[dict[str, Any]]:
    if not PROJECTS_FILE.exists():
        return []

    try:
        return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def write_projects(projects: list[dict[str, Any]]) -> None:
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2), encoding="utf-8")


def save_upload(upload: UploadFile) -> tuple[Path, int]:
    original_name = Path(upload.filename or "video.mp4").name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Please upload a supported video file.",
        )

    destination = UPLOAD_DIR / f"{uuid.uuid4()}{extension}"
    size = 0

    with destination.open("wb") as buffer:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            buffer.write(chunk)

    return destination, size
