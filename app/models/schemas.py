from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class MomentCandidate:
    start: float
    end: float
    text: str
    score: float
    reason: str

class ChatRequest(BaseModel):
    message: str

class ClipGenerateRequest(BaseModel):
    start: float
    end: float
    font: str = "Inter"
    color: str = "#FFFFFF"
    size: int = 20
    captionsEnabled: bool = True

class ReelGenerateRequest(BaseModel):
    clips: list[dict[str, float]]
    font: str = "Inter"
    color: str = "#FFFFFF"
    size: int = 20
    captionsEnabled: bool = True
