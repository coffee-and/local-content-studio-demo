from pathlib import Path

import numpy as np

from app.database import Database
from app.services.storage_service import StorageService, sanitize_component


def test_sanitize_component() -> None:
    assert sanitize_component('a:b/c*?') == "a_b_c__"


def test_save_processed_image(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db", tmp_path / "output")
    db.set_setting("output_root", str(tmp_path / "output"))
    storage = StorageService(db)
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    output = storage.save_processed_image(
        source_path=tmp_path / "source.png",
        image=image,
    )
    assert output.exists()
