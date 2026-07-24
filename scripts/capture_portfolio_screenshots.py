from __future__ import annotations

# ruff: noqa: E402
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRect
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.database import Database
from app.models import ContentRequest
from app.services.batch_service import BatchImageService
from app.services.content_service import ContentService
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
from app.ui.image_page import SAMPLE_IMAGES, sample_images_dir
from app.ui.main_window import MainWindow
from app.ui.style import APP_STYLESHEET, apply_application_font

SCREENSHOT_DIR = ROOT / "docs" / "assets" / "screenshots"


def _capture(window: MainWindow, filename: str) -> tuple[int, int]:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication이 준비되지 않았습니다.")
    app.processEvents()
    QTest.qWait(180)
    screen = window.screen() or app.primaryScreen()
    if screen:
        frame = window.frameGeometry()
        pixmap = screen.grabWindow(
            0,
            frame.x(),
            frame.y(),
            frame.width(),
            frame.height(),
        )
    else:
        pixmap = window.grab()
    if pixmap.isNull():
        pixmap = window.grab()
    target = SCREENSHOT_DIR / filename
    if not pixmap.save(str(target), "PNG"):
        raise RuntimeError(f"스크린샷을 저장하지 못했습니다: {target}")
    return pixmap.width(), pixmap.height()


def _seed_demo_data(
    db: Database,
    content_service: ContentService,
    image_service: ImageService,
    storage: StorageService,
) -> list:
    db.set_setting("mock_mode", "1")
    prompt_id = db.list_prompts()[0]["id"]
    conditions = [
        ("부산 사상구", "사고사진 정리"),
        ("부산 북구", "차량 접촉 사고"),
        ("부산 강서구", "현장 이미지 관리"),
    ]
    content_results = [
        content_service.generate(
            ContentRequest(
                prompt_id=prompt_id,
                region=region,
                keyword=keyword,
                use_rotation=False,
                source="portfolio-capture",
            )
        )
        for region, keyword in conditions
    ]

    roi_sets = [
        [(180, 165, 95, 115), (1050, 195, 105, 115), (160, 720, 460, 95)],
        [(825, 205, 95, 115), (450, 735, 220, 85)],
        [(1080, 245, 95, 115), (245, 755, 440, 90)],
    ]
    for (_display_name, filename), rois in zip(SAMPLE_IMAGES, roi_sets, strict=True):
        source = sample_images_dir() / filename
        original = image_service.read(source)
        processed = image_service.apply(
            original,
            rois,
            method="pixelate",
            strength=18,
        )
        output = storage.save_processed_image(source_path=source, image=processed)
        db.insert_image_job(
            source_path=f"sample_data/images/{filename}",
            output_path=f"demo-output/images/{output.name}",
            method="pixelate",
            detector="manual",
            roi_count=len(rois),
            status="success",
        )

    db.create_schedule(
        name="포트폴리오 Mock 콘텐츠",
        interval_minutes=60,
        prompt_id=prompt_id,
        use_rotation=True,
        fixed_region="",
        fixed_keyword="",
    )
    return content_results


def main() -> int:
    os.environ.pop("OPENAI_API_KEY", None)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName("Local Content Studio")
    apply_application_font(app)
    app.setStyleSheet(APP_STYLESHEET)

    sizes: dict[str, tuple[int, int]] = {}
    with TemporaryDirectory(prefix=".capture_runtime-", dir=ROOT) as runtime:
        runtime_root = Path(runtime)
        db = Database(runtime_root / "capture.db", runtime_root / "output")
        storage = StorageService(db)
        image_service = ImageService()
        content_service = ContentService(db, storage)
        batch_service = BatchImageService(db, image_service, storage)
        content_results = _seed_demo_data(db, content_service, image_service, storage)

        window = MainWindow(
            db=db,
            content_service=content_service,
            image_service=image_service,
            storage_service=storage,
            batch_service=batch_service,
        )
        window.resize(1400, 860)
        screen = app.primaryScreen()
        if screen:
            available: QRect = screen.availableGeometry()
            window.move(
                available.x() + max(0, (available.width() - window.width()) // 2),
                available.y() + max(0, (available.height() - window.height()) // 2),
            )
        window.show()
        window.raise_()
        window.activateWindow()
        QTest.qWait(250)

        window.dashboard_page.refresh()
        window.tabs.setCurrentIndex(0)
        sizes["01_dashboard.png"] = _capture(window, "01_dashboard.png")

        window.content_page.show_result(content_results[-1])
        window.content_page.region_combo.setEditText(content_results[-1].region)
        window.content_page.keyword_combo.setEditText(content_results[-1].keyword)
        window.tabs.setCurrentIndex(1)
        sizes["02_content_generation.png"] = _capture(window, "02_content_generation.png")

        parking = sample_images_dir() / SAMPLE_IMAGES[0][1]
        window.image_page.sample_combo.setCurrentIndex(0)
        window.image_page.load_path(parking)
        window.image_page.canvas.set_rois(
            [(180, 165, 95, 115), (1050, 195, 105, 115), (160, 720, 460, 95)],
            source="manual",
        )
        window.tabs.setCurrentIndex(3)
        sizes["03_mosaic_roi_selection.png"] = _capture(window, "03_mosaic_roi_selection.png")

        window.image_page.apply_preview()
        sizes["04_mosaic_result.png"] = _capture(window, "04_mosaic_result.png")

        alley = sample_images_dir() / SAMPLE_IMAGES[2][1]
        window.image_page.sample_combo.setCurrentIndex(2)
        window.image_page.load_path(alley)
        window.image_page.canvas.set_rois(
            [(1080, 245, 95, 115), (245, 755, 440, 90)],
            source="manual",
        )
        gaussian_index = window.image_page.method_combo.findData("gaussian")
        window.image_page.method_combo.setCurrentIndex(gaussian_index)
        window.image_page.apply_preview()
        sizes["05_batch_or_second_sample.png"] = _capture(window, "05_batch_or_second_sample.png")

        window.history_page.refresh()
        window.history_page.tabs.setCurrentIndex(1)
        window.tabs.setCurrentIndex(5)
        sizes["06_history.png"] = _capture(window, "06_history.png")

        window.schedule_page.refresh()
        window.tabs.setCurrentIndex(4)
        sizes["07_scheduler.png"] = _capture(window, "07_scheduler.png")

        window.settings_page.load()
        window.tabs.setCurrentIndex(6)
        sizes["08_settings.png"] = _capture(window, "08_settings.png")

        window.close()
        app.processEvents()

    for filename, (width, height) in sizes.items():
        print(f"{filename}: {width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
