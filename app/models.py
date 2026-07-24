from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ContentRequest:
    prompt_id: int | None = None
    region: str = ""
    keyword: str = ""
    use_rotation: bool = False
    source: str = "manual"


@dataclass(slots=True)
class ContentResult:
    generation_id: int
    title: str
    body: str
    region: str
    keyword: str
    model: str
    output_dir: Path
    duplicate_score: float
    used_mock: bool


@dataclass(slots=True)
class BatchImageRequest:
    input_dir: Path
    detect_faces: bool
    detect_plates: bool
    method: str
    strength: int
