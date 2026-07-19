from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.models.schemas import ClipGenerateRequest
from app.services.storage_service import read_projects
from app.services.video_service import generate_clip_internal
from app.core.config import UPLOAD_DIR

router = APIRouter(prefix="/api/projects", tags=["clips"])

@router.post("/{project_id}/clips/generate")
async def generate_clip(project_id: str, payload: ClipGenerateRequest):
    projects = read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    video_filename = project.get("videoFilename")
    if not video_filename:
        raise HTTPException(status_code=400, detail="Original video not available.")
        
    source_video = UPLOAD_DIR / video_filename
    if not source_video.exists():
        raise HTTPException(status_code=404, detail="Original video file missing.")

    clip_url = await generate_clip_internal(
        source_video=source_video,
        start_time=payload.start,
        end_time=payload.end,
        font_name=payload.font,
        font_color=payload.color,
        font_size=payload.size,
        all_segments=project.get("segments", []),
        captions_enabled=payload.captionsEnabled
    )

    if not clip_url:
        raise HTTPException(status_code=500, detail="Failed to generate clip using ffmpeg.")

    return {
        "clipUrl": clip_url,
        "filename": Path(clip_url).name
    }
