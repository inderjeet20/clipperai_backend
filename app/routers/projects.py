import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import MomentCandidate
from app.services.storage_service import read_projects, write_projects, save_upload
from app.services.transcription_service import transcribe_video
from app.services.analysis_service import retrieve_relevant_chunks
from app.services.ai_service import llm_score_moments, get_embeddings
from app.services.video_service import generate_clip_internal

router = APIRouter(prefix="/api/projects", tags=["projects"])

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def serialize_moment(moment: MomentCandidate) -> dict[str, Any]:
    return {
        "start": round(moment.start, 2),
        "end": round(moment.end, 2),
        "score": moment.score,
        "reason": moment.reason,
        "text": moment.text,
    }

@router.get("")
def list_projects() -> list[dict[str, Any]]:
    return sorted(read_projects(), key=lambda project: project.get("createdAt", ""), reverse=True)


@router.post("")
async def create_project(
    name: str = Form(...),
    captions_enabled: bool = Form(True),
    caption_font: str = Form("Inter"),
    caption_color: str = Form("#FFFFFF"),
    caption_size: int = Form(20),
    video: UploadFile = File(...),
) -> dict[str, Any]:
    if not name.strip():
        raise HTTPException(status_code=400, detail="Project name is required.")

    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Please upload a video file.")

    saved_path, file_size = await asyncio.to_thread(save_upload, video)
    segments = await asyncio.to_thread(transcribe_video, saved_path)
    retrieved_chunks = retrieve_relevant_chunks(segments)
    moments = await asyncio.to_thread(llm_score_moments, retrieved_chunks)

    # Embed segments for proper RAG
    segment_texts = [segment.text for segment in segments]
    embeddings = await asyncio.to_thread(get_embeddings, segment_texts)

    project_segments = []
    for i, segment in enumerate(segments):
        embed = embeddings[i] if i < len(embeddings) else []
        project_segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "words": segment.words,
            "embedding": embed
        })

    serialized_clips = [serialize_moment(moment) for moment in moments]

    # Automatically generate clips
    if captions_enabled:
        for clip in serialized_clips:
            clip_url = await generate_clip_internal(
                source_video=saved_path,
                start_time=clip["start"],
                end_time=clip["end"],
                font_name=caption_font,
                font_color=caption_color,
                font_size=caption_size,
                all_segments=project_segments
            )
            clip["clipUrl"] = clip_url

    project = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "fileName": Path(video.filename or saved_path.name).name,
        "videoFilename": saved_path.name,
        "fileSize": file_size,
        "captionsEnabled": captions_enabled,
        "captionFont": caption_font,
        "captionColor": caption_color,
        "captionSize": caption_size,
        "createdAt": utc_now(),
        "status": "complete",
        "transcript": " ".join(segment.text for segment in segments),
        "segments": project_segments,
        "clips": serialized_clips,
    }

    projects = read_projects()
    projects.append(project)
    write_projects(projects)

    return project


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict[str, str]:
    projects = read_projects()
    next_projects = [project for project in projects if project.get("id") != project_id]

    if len(next_projects) == len(projects):
        raise HTTPException(status_code=404, detail="Project not found.")

    write_projects(next_projects)
    return {"status": "deleted"}
