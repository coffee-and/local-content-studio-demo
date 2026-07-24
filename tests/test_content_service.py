from pathlib import Path

import pytest

from app.database import Database
from app.models import ContentRequest
from app.services.content_service import ContentService
from app.services.storage_service import StorageService


def test_mock_generation_saves_files(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db", tmp_path / "output")
    db.set_setting("output_root", str(tmp_path / "output"))
    db.set_setting("mock_mode", "1")
    service = ContentService(db, StorageService(db))
    prompt_id = db.list_prompts()[0]["id"]

    result = service.generate(
        ContentRequest(
            prompt_id=prompt_id,
            region="부산 사상구",
            keyword="사고사진 정리",
        )
    )

    assert result.used_mock is True
    assert (result.output_dir / "title.txt").exists()
    assert (result.output_dir / "body.md").exists()
    assert (result.output_dir / "metadata.json").exists()
    assert db.stats()["generations"] == 1


def test_duplicate_generation_is_blocked(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db", tmp_path / "output")
    db.set_setting("output_root", str(tmp_path / "output"))
    db.set_setting("mock_mode", "1")
    service = ContentService(db, StorageService(db))
    prompt_id = db.list_prompts()[0]["id"]
    request = ContentRequest(
        prompt_id=prompt_id,
        region="부산 사상구",
        keyword="사고사진 정리",
    )

    service.generate(request)
    with pytest.raises(RuntimeError):
        service.generate(request)
