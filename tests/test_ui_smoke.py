from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.database import Database
from app.services.batch_service import BatchImageService
from app.services.content_service import ContentService
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
from app.ui.image_page import SAMPLE_IMAGES, sample_images_dir
from app.ui.main_window import MainWindow


def test_main_window_and_sample_image_smoke(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "ui-smoke.db", tmp_path / "output")
    storage = StorageService(db)
    image_service = ImageService()
    content_service = ContentService(db, storage)
    batch_service = BatchImageService(db, image_service, storage)

    window = MainWindow(
        db=db,
        content_service=content_service,
        image_service=image_service,
        storage_service=storage,
        batch_service=batch_service,
    )
    try:
        assert window.tabs.count() == 7
        assert [
            window.tabs.tabText(index) for index in range(window.tabs.count())
        ] == [
            "대시보드",
            "콘텐츠 생성",
            "프롬프트 관리",
            "이미지 모자이크",
            "스케줄러",
            "이력",
            "설정",
        ]
        assert window.minimumWidth() == 1180
        assert window.minimumHeight() == 720
        assert window.image_page.sample_combo.count() == len(SAMPLE_IMAGES) == 3
        assert all(
            (sample_images_dir() / filename).is_file()
            for _display_name, filename in SAMPLE_IMAGES
        )
        assert any(
            button.text() == "콘텐츠 생성 및 저장"
            for button in window.findChildren(QPushButton)
        )

        sample = sample_images_dir() / SAMPLE_IMAGES[0][1]
        window.image_page.load_path(sample)
        window.image_page.canvas.set_rois(
            [(160, 720, 450, 100)],
            source="manual",
        )
        window.image_page.apply_preview()
        assert window.image_page.original is not None
        assert window.image_page.processed is not None
        assert window.image_page.canvas.roi_summary == (1, 0)
    finally:
        window.close()
        app.processEvents()
