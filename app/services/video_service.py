import asyncio
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any
from fastapi import HTTPException

from app.core.config import UPLOAD_DIR, BASE_DIR


def format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

async def generate_clip_internal(
    source_video: Path,
    start_time: float,
    end_time: float,
    font_name: str,
    font_color: str,
    font_size: int,
    all_segments: list[dict],
    captions_enabled: bool = True
) -> str:
    duration = end_time - start_time
    if duration <= 0:
        return ""

    clip_segments = []
    for seg in all_segments:
        seg_start = seg["start"]
        seg_end = seg["end"]
        if seg_end > start_time and seg_start < end_time:
            rel_start = max(0.0, seg_start - start_time)
            rel_end = min(duration, seg_end - start_time)
            clip_segments.append({
                "start": rel_start,
                "end": rel_end,
                "text": seg["text"],
                "words": seg.get("words", [])
            })

    output_filename = f"clip_{uuid.uuid4()}.mp4"
    output_path = UPLOAD_DIR / output_filename

    if not font_name.strip():
        font_name = "Inter"

    # Write SRT to temp dir using a simple UUID name
    temp_dir = Path(tempfile.gettempdir())
    srt_name = f"sub{uuid.uuid4().hex}.srt"
    srt_path = temp_dir / srt_name

    with open(srt_path, "w", encoding="utf-8") as f:
        block_index = 1
        
        # Flatten all words
        clip_words = []
        for seg in clip_segments:
            clip_words.extend(seg.get("words", []))

        if not clip_words:
            # Fallback to standard block if no words are available
            for seg in clip_segments:
                f.write(f"{block_index}\n")
                f.write(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n")
                f.write(f"{seg['text'].strip()}\n\n")
                block_index += 1
        else:
            # Group into chunks of up to 6 words to increase row width of caption
            CHUNK_SIZE = 6
            word_chunks = [clip_words[i:i + CHUNK_SIZE] for i in range(0, len(clip_words), CHUNK_SIZE)]

            for chunk in word_chunks:
                for i, word in enumerate(chunk):
                    raw_start = word["start"]
                    raw_end = chunk[i+1]["start"] if i + 1 < len(chunk) else word["end"]

                    block_start = min(duration, max(0.0, raw_start - start_time))
                    block_end = min(duration, max(0.0, raw_end - start_time))

                    if block_end <= block_start:
                        continue

                    parts = []
                    for j, w in enumerate(chunk):
                        w_text = w["word"]
                        if j == i:
                            # Highlight the active word with user color using standard SRT font tags
                            parts.append(f'<font color="{font_color}">{w_text}</font>')
                        else:
                            # Inactive words remain default color (white as set by force_style)
                            parts.append(w_text)
                    
                    block_text = "".join(parts).strip()
                    
                    f.write(f"{block_index}\n")
                    f.write(f"{format_srt_time(block_start)} --> {format_srt_time(block_end)}\n")
                    f.write(f"{block_text}\n\n")
                    block_index += 1

    # Format the font directory path for FFmpeg
    fonts_dir_str = str((BASE_DIR / "data" / "fonts").resolve()).replace('\\', '/').replace(':', r'\:')
    sub_filter = (
        f"subtitles='{srt_name}':fontsdir='{fonts_dir_str}':force_style='"
        f"Fontname={font_name},FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,"
        f"BorderStyle=1,Outline=1.2,Shadow=0.5,Blur=0.5,Alignment=2,MarginV={max(font_size, 15)}'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", str(source_video),
        "-t", str(duration),
        "-map", "0:v",
        "-map", "0:a?",
        "-c:a", "aac",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20"
    ]
    
    if captions_enabled and clip_segments:
        cmd.extend(["-vf", sub_filter])

    cmd.append(str(output_path))

    def run_ffmpeg() -> tuple[int, str]:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(temp_dir),
        )
        return result.returncode, result.stderr.decode(errors="replace")

    try:
        returncode, stderr_text = await asyncio.to_thread(run_ffmpeg)
        if returncode != 0:
            print(f"FFmpeg error: {stderr_text}")
            return ""
    except FileNotFoundError:
        print("ffmpeg is not installed or not in PATH.")
        return ""
    finally:
        if srt_path.exists():
            srt_path.unlink()

    return f"/api/uploads/{output_filename}"

async def generate_reel_internal(
    source_video: Path,
    project_segments: list[dict],
    clips: list[dict[str, float]],
    font: str,
    color: str,
    size: int,
    captions_enabled: bool,
) -> dict[str, Any]:
    clip_files: list[Path] = []
    
    for clip in clips:
        start_time = clip.get("start", 0.0)
        end_time = clip.get("end", 0.0)
        if end_time <= start_time:
            continue

        clip_url = await generate_clip_internal(
            source_video=source_video,
            start_time=start_time,
            end_time=end_time,
            font_name=font,
            font_color=color,
            font_size=size,
            all_segments=project_segments,
            captions_enabled=captions_enabled,
        )
        
        if clip_url:
            filename = clip_url.split("/")[-1]
            clip_files.append(UPLOAD_DIR / filename)

    if not clip_files:
        raise HTTPException(status_code=500, detail="Failed to generate any clips for the reel.")

    reel_filename = f"reel_{uuid.uuid4()}.mp4"
    reel_path = UPLOAD_DIR / reel_filename
    concat_list_path = UPLOAD_DIR / f"concat_{uuid.uuid4().hex}.txt"

    with open(concat_list_path, "w", encoding="utf-8") as f:
        for cf in clip_files:
            f.write(f"file '{cf.resolve()}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c",
        "copy",
        str(reel_path),
    ]

    def run_concat() -> None:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            print(f"[ffmpeg concat] stderr: {result.stderr.decode(errors='replace')}")

    await asyncio.to_thread(run_concat)

    if not reel_path.exists() or reel_path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="FFmpeg failed to produce output reel.")

    if concat_list_path.exists():
        concat_list_path.unlink()

    return {
        "reelUrl": f"/api/uploads/{reel_filename}",
        "filename": reel_filename,
    }
