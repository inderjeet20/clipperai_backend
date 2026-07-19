
from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest
from app.services.storage_service import read_projects
from app.services.ai_service import get_embeddings, embedding_cosine_similarity
from app.services.analysis_service import tokenize
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

router = APIRouter(prefix="/api/projects", tags=["chat"])

@router.post("/{project_id}/chat")
def chat_with_project(project_id: str, payload: ChatRequest):
    projects = read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    query = payload.message
    segments = project.get("segments", [])

    # Proper RAG Architecture using Embeddings
    query_embed_list = get_embeddings([query])
    query_embed = query_embed_list[0] if query_embed_list else []

    scored_segments = []
    
    for seg in segments:
        text = seg.get("text", "")
        seg_embed = seg.get("embedding", [])
        
        if query_embed and seg_embed:
            score = embedding_cosine_similarity(query_embed, seg_embed)
        else:
            # Fallback to naive keyword overlap if embeddings failed
            query_tokens = set(tokenize(query))
            seg_tokens = set(tokenize(text))
            score = float(len(query_tokens & seg_tokens))
            if query.lower() in text.lower():
                score += 3.0

        scored_segments.append((score, seg))

    scored_segments.sort(key=lambda x: x[0], reverse=True)
    top_segments = [seg for score, seg in scored_segments[:5] if score > 0]

    if not top_segments:
        top_segments = segments[:5]

    context_str = "\n".join(
        f"[{seg['start']:.2f} - {seg['end']:.2f}]: {seg['text']}"
        for seg in top_segments
    )

    if GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""
You are an expert AI Video Assistant. A user is asking a question about a video.
Below is the relevant transcript context from the video with timestamps.

Context from video:
{context_str}

User Question: {query}

Instructions:
1. Answer the question accurately and concisely based ONLY on the provided context.
2. Cite the timestamps (e.g., "[0:12 - 0:18]") when referencing parts of the video so the user knows exactly where it was mentioned.
3. If the answer is not in the context, synthesize a general, polite response explaining what is mentioned in the transcript and say that specific detail was not explicitly found.
"""
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            answer = response.text or ""
            return {
                "answer": answer.strip(),
                "sources": [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"]
                    }
                    for seg in top_segments
                ]
            }
        except Exception:
            pass

    # Fallback Local Generator
    if not top_segments:
        answer = "I couldn't find any clear transcript data for this video."
    else:
        answer_parts = []
        answer_parts.append("Based on the video transcript, here is what I found:\n")
        for seg in top_segments:
            start_m = int(seg['start'] // 60)
            start_s = int(seg['start'] % 60)
            end_m = int(seg['end'] // 60)
            end_s = int(seg['end'] % 60)
            timestamp_str = f"[{start_m}:{start_s:02d} - {end_m}:{end_s:02d}]"
            answer_parts.append(f"• At {timestamp_str}, the speaker says: \"{seg['text']}\"")

        answer_parts.append("\nFeel free to click any of these segments/timestamps in the sources below to jump directly to that part of the video!")
        answer = "\n".join(answer_parts)

    return {
        "answer": answer,
        "sources": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"]
            }
            for seg in top_segments
        ]
    }
