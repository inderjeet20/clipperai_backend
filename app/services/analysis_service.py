import math
import re
from collections import Counter
from app.models.schemas import TranscriptSegment, MomentCandidate

def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", text.lower())

def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    overlap = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in overlap)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))

    if left_norm == 0 or right_norm == 0:
        return 0

    return numerator / (left_norm * right_norm)

def build_chunks(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    chunks: list[TranscriptSegment] = []
    current: list[TranscriptSegment] = []
    current_start = 0.0

    for segment in segments:
        if not current:
            current_start = segment.start

        current.append(segment)
        duration = segment.end - current_start

        if duration >= 35 or len(current) >= 8:
            chunks.append(
                TranscriptSegment(
                    start=current_start,
                    end=current[-1].end,
                    text=" ".join(item.text for item in current),
                )
            )
            current = []

    if current:
        chunks.append(
            TranscriptSegment(
                start=current_start,
                end=current[-1].end,
                text=" ".join(item.text for item in current),
            )
        )

    return chunks or segments

def retrieve_relevant_chunks(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    query = (
        "viral short video hook emotional story surprising insight question "
        "conflict transformation high retention valuable moment"
    )
    query_vector = Counter(tokenize(query))
    scored_chunks = []

    for chunk in build_chunks(segments):
        vector = Counter(tokenize(chunk.text))
        scored_chunks.append((cosine_similarity(query_vector, vector), chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:8]]

def local_score_moments(chunks: list[TranscriptSegment]) -> list[MomentCandidate]:
    signal_words = {
        "secret", "mistake", "story", "never", "best", "worst", "why", "how", 
        "changed", "failed", "won", "growth", "money", "viral", "important",
    }
    moments = []

    for chunk in chunks:
        words = tokenize(chunk.text)
        signal_hits = sum(1 for word in words if word in signal_words)
        punctuation_bonus = chunk.text.count("?") * 0.08 + chunk.text.count("!") * 0.06
        density = min(len(words) / 90, 1)
        score = min(0.35 + signal_hits * 0.08 + punctuation_bonus + density * 0.32, 0.98)
        moments.append(
            MomentCandidate(
                start=chunk.start,
                end=chunk.end,
                text=chunk.text[:260],
                score=round(score, 2),
                reason="Strong spoken signal and compact short-form pacing.",
            )
        )

    moments.sort(key=lambda item: item.score, reverse=True)
    return moments[:5]
