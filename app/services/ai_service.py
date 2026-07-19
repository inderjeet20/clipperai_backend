import json
import re
import math
from typing import Any

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.models.schemas import TranscriptSegment, MomentCandidate
from app.services.analysis_service import local_score_moments

def parse_llm_json(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        payload = payload.get("moments", [])

    if not isinstance(payload, list):
        return []

    return payload

def llm_score_moments(chunks: list[TranscriptSegment]) -> list[MomentCandidate]:
    if not GEMINI_API_KEY:
        return local_score_moments(chunks)

    try:
        from google import genai
    except ImportError:
        return local_score_moments(chunks)

    context = "\n\n".join(
        f"[{index}] {chunk.start:.2f}-{chunk.end:.2f}: {chunk.text}"
        for index, chunk in enumerate(chunks)
    )
    prompt = f"""
You score transcript chunks for short-form viral clips.
Return only JSON with this shape:
[
  {{"start": 0.0, "end": 12.3, "score": 0.91, "reason": "why it will retain viewers"}}
]

Pick up to 5 moments. Favor hooks, conflict, surprise, emotion, useful insight, and clear story turns.

Transcript chunks:
{context}
"""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        payload = parse_llm_json(response.text or "")
    except Exception:
        return local_score_moments(chunks)

    moments = []
    for item in payload[:5]:
        try:
            start = float(item["start"])
            end = float(item["end"])
            matching_text = next(
                (
                    chunk.text
                    for chunk in chunks
                    if abs(chunk.start - start) < 1.5 or chunk.start <= start <= chunk.end
                ),
                "",
            )
            moments.append(
                MomentCandidate(
                    start=start,
                    end=end,
                    text=matching_text[:260],
                    score=round(float(item.get("score", 0.75)), 2),
                    reason=str(item.get("reason", "High-retention candidate.")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return moments or local_score_moments(chunks)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not GEMINI_API_KEY or not texts:
        return [[] for _ in texts]
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.embed_content(
            model="gemini-embedding-2",
            contents=texts,
        )
        return [embed.values for embed in response.embeddings]
    except Exception as e:
        print(f"Embedding error: {e}")
        return [[] for _ in texts]

def embedding_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if not vec1 or not vec2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)
