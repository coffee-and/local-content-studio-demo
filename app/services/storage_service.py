from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from app.database import Database

_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_component(value: str, fallback: str = "untitled", max_length: int = 60) -> str:
    cleaned = _INVALID_PATH_CHARS.sub("_", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or fallback)[:max_length]


class StorageService:
    def __init__(self, db: Database) -> None:
        self.db = db

    @property
    def output_root(self) -> Path:
        root = self.db.get_setting("output_root")
        if not root:
            raise ValueError("결과 저장 폴더가 설정되지 않았습니다.")
        path = Path(root).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_content(
        self,
        *,
        region: str,
        keyword: str,
        title: str,
        body: str,
        metadata: dict[str, Any],
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        date_folder = datetime.now().strftime("%Y-%m-%d")
        target = (
            self.output_root
            / "contents"
            / date_folder
            / sanitize_component(region, "no-region")
            / sanitize_component(keyword, "no-keyword")
            / timestamp
        )
        target.mkdir(parents=True, exist_ok=False)

        (target / "title.txt").write_text(title.strip(), encoding="utf-8")
        (target / "body.md").write_text(body.strip(), encoding="utf-8")
        (target / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return target

    def save_processed_image(
        self,
        *,
        source_path: Path,
        image,
        suffix: str = "mosaic",
    ) -> Path:
        date_folder = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
        target_dir = self.output_root / "images" / date_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        stem = sanitize_component(source_path.stem, "image")
        extension = source_path.suffix.lower() or ".jpg"
        if extension not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            extension = ".jpg"
        output = target_dir / f"{stem}_{suffix}_{timestamp}{extension}"

        ok, encoded = cv2.imencode(extension, image)
        if not ok:
            raise ValueError("결과 이미지를 인코딩하지 못했습니다.")
        encoded.tofile(str(output))
        return output
