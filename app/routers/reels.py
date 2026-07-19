from fastapi import APIRouter, HTTPException

from app.models.schemas import ReelGenerateRequest
from app.services.storage_service import read_projects
from app.services.video_service import generate_reel_internal
from app.core.config import UPLOAD_DIR

router = APIRouter(prefix="/api/projects", tags=["reels"])

@router.post("/{project_id}/reels/generate")
async def generate_reel(project_id: str, payload: ReelGenerateRequest):
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

    return await generate_reel_internal(
        source_video=source_video,
        project_segments=project.get("segments", []),
        clips=payload.clips,
        font=payload.font,
        color=payload.color,
        size=payload.size,
        captions_enabled=payload.captionsEnabled
    )
