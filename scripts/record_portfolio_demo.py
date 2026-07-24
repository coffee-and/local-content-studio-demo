from __future__ import annotations

# ruff: noqa: E402
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import imageio_ffmpeg
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea

from app.database import Database
from app.models import ContentRequest
from app.services.batch_service import BatchImageService
from app.services.content_service import ContentService
from app.services.image_service import ROI, ImageService
from app.services.storage_service import StorageService
from app.ui.image_page import SAMPLE_IMAGES, sample_images_dir
from app.ui.main_window import MainWindow
from app.ui.style import APP_STYLESHEET, apply_application_font

FPS = 24
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_PATH = ROOT / "docs" / "assets" / "demo" / "local-content-studio-demo.mp4"
THUMBNAIL_PATH = ROOT / "docs" / "assets" / "demo" / "video-thumbnail.png"
TMP_ROOT = ROOT / ".tmp"


class Recorder:
    def __init__(self, app: QApplication, window: MainWindow) -> None:
        self.app = app
        self.window = window
        self.frame_index = 0
        self.thumbnail_frame_index = 0
        self._writer = imageio_ffmpeg.write_frames(
            str(VIDEO_PATH),
            (VIDEO_WIDTH, VIDEO_HEIGHT),
            pix_fmt_in="rgb24",
            pix_fmt_out="yuv420p",
            fps=FPS,
            quality=None,
            codec="libx264",
            macro_block_size=16,
            ffmpeg_log_level="warning",
            output_params=[
                "-preset",
                "medium",
                "-crf",
                "27",
                "-movflags",
                "+faststart",
            ],
        )
        self._writer.send(None)

    @property
    def elapsed(self) -> float:
        return self.frame_index / FPS

    def close(self) -> None:
        self._writer.close()

    def capture(self) -> np.ndarray:
        self.app.processEvents()
        screen = self.window.screen() or self.app.primaryScreen()
        if screen:
            frame = self.window.frameGeometry()
            pixmap = screen.grabWindow(
                0,
                frame.x(),
                frame.y(),
                frame.width(),
                frame.height(),
            )
        else:
            pixmap = self.window.grab()
        if pixmap.isNull():
            raise RuntimeError("앱 창 프레임을 캡처하지 못했습니다.")

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        buffer = np.frombuffer(
            image.bits(),
            dtype=np.uint8,
            count=bytes_per_line * height,
        )
        rgb = buffer.reshape(height, bytes_per_line)[:, : width * 3]
        rgb = rgb.reshape(height, width, 3).copy()

        scale = min(VIDEO_WIDTH / width, VIDEO_HEIGHT / height)
        draw_width = max(1, round(width * scale))
        draw_height = max(1, round(height * scale))
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        resized = cv2.resize(rgb, (draw_width, draw_height), interpolation=interpolation)
        output = np.full((VIDEO_HEIGHT, VIDEO_WIDTH, 3), 242, dtype=np.uint8)
        left = (VIDEO_WIDTH - draw_width) // 2
        top = (VIDEO_HEIGHT - draw_height) // 2
        output[top : top + draw_height, left : left + draw_width] = resized
        return output

    def write_frame(self, frame: np.ndarray) -> None:
        self._writer.send(np.ascontiguousarray(frame).tobytes())
        self.frame_index += 1

    def hold(self, seconds: float) -> None:
        frame = self.capture()
        for _ in range(max(1, round(seconds * FPS))):
            self.write_frame(frame)

    def transition(self, seconds: float = 0.5) -> None:
        frames = max(2, round(seconds * FPS))
        start = self.capture()
        self.app.processEvents()
        end = self.capture()
        for index in range(frames):
            alpha = index / (frames - 1)
            blended = cv2.addWeighted(start, 1.0 - alpha, end, alpha, 0)
            self.write_frame(blended)

    def click_tab(self, index: int) -> None:
        tab_bar = self.window.tabs.tabBar()
        position = tab_bar.tabRect(index).center()
        QTest.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=position)
        self.app.processEvents()

    def click_button(self, text: str, parent=None) -> QPushButton:
        root = parent or self.window
        for button in root.findChildren(QPushButton):
            if button.text() == text:
                button.setFocus()
                self.app.processEvents()
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                return button
        raise RuntimeError(f"버튼을 찾지 못했습니다: {text}")

    def animate_text(
        self,
        setter: Callable[[str], None],
        value: str,
        *,
        seconds: float,
    ) -> None:
        steps = max(1, len(value))
        frames_per_step = max(1, round(seconds * FPS / steps))
        for index in range(1, len(value) + 1):
            setter(value[:index])
            self.app.processEvents()
            frame = self.capture()
            for _ in range(frames_per_step):
                self.write_frame(frame)

    def animate_roi(self, roi: ROI, *, seconds: float = 1.8) -> None:
        canvas = self.window.image_page.canvas
        canvas.repaint()
        self.app.processEvents()
        widget_rect = canvas._image_roi_to_widget(roi)
        start = widget_rect.topLeft() + QPoint(2, 2)
        end = widget_rect.bottomRight() - QPoint(2, 2)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
        steps = 18
        frames_per_step = max(1, round(seconds * FPS / steps))
        for step in range(1, steps + 1):
            x = start.x() + round((end.x() - start.x()) * step / steps)
            y = start.y() + round((end.y() - start.y()) * step / steps)
            QTest.mouseMove(canvas, QPoint(x, y))
            self.app.processEvents()
            frame = self.capture()
            for _ in range(frames_per_step):
                self.write_frame(frame)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
        self.app.processEvents()


def _seed_demo_data(
    db: Database,
    content_service: ContentService,
    image_service: ImageService,
    storage: StorageService,
) -> None:
    db.set_setting("mock_mode", "1")
    prompt_id = db.list_prompts()[0]["id"]
    for region, keyword in [
        ("부산 북구", "차량 접촉 사고"),
        ("부산 강서구", "현장 이미지 관리"),
        ("부산 해운대구", "사고 이미지 정리"),
    ]:
        content_service.generate(
            ContentRequest(
                prompt_id=prompt_id,
                region=region,
                keyword=keyword,
                use_rotation=False,
                source="portfolio-video-seed",
            )
        )

    seed_jobs = [
        (
            SAMPLE_IMAGES[1][1],
            [(825, 205, 95, 115), (450, 735, 220, 85)],
            "pixelate",
        ),
        (
            SAMPLE_IMAGES[2][1],
            [(1080, 245, 95, 115), (245, 755, 440, 90)],
            "gaussian",
        ),
    ]
    for filename, rois, method in seed_jobs:
        source = sample_images_dir() / filename
        original = image_service.read(source)
        processed = image_service.apply(
            original,
            rois,
            method=method,
            strength=18,
        )
        output = storage.save_processed_image(source_path=source, image=processed)
        db.insert_image_job(
            source_path=f"sample_data/images/{filename}",
            output_path=f".tmp/portfolio-demo/output/images/{output.name}",
            method=method,
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


def _wait_for_content(window: MainWindow, app: QApplication, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if window.content_page.title_edit.text().strip():
            return
        QTest.qWait(30)
    raise TimeoutError("Mock 콘텐츠 생성 결과가 제한 시간 안에 표시되지 않았습니다.")


def _verify_video() -> dict[str, float | int]:
    if not VIDEO_PATH.is_file() or VIDEO_PATH.stat().st_size <= 0:
        raise RuntimeError("MP4 파일이 생성되지 않았습니다.")
    capture = cv2.VideoCapture(str(VIDEO_PATH))
    if not capture.isOpened():
        raise RuntimeError("OpenCV가 생성된 MP4를 열지 못했습니다.")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    ok, first_frame = capture.read()
    capture.release()
    if not ok or first_frame is None:
        raise RuntimeError("생성된 MP4의 첫 프레임을 읽지 못했습니다.")
    duration = frame_count / fps
    if frame_count <= 0 or width < 1280 or height < 720:
        raise RuntimeError("영상 프레임 수 또는 해상도가 조건을 충족하지 않습니다.")
    if not 90 <= duration <= 180:
        raise RuntimeError(f"영상 길이가 조건을 벗어났습니다: {duration:.2f}초")
    if not 20 <= fps <= 60:
        raise RuntimeError(f"영상 프레임률이 비정상적입니다: {fps:.2f}")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(VIDEO_PATH), "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if "Video: h264" not in probe.stderr:
        raise RuntimeError("생성된 MP4의 H.264 스트림을 확인하지 못했습니다.")
    if probe.returncode != 0:
        raise RuntimeError("ffmpeg 전체 영상 디코딩 검증에 실패했습니다.")
    return {
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "size": VIDEO_PATH.stat().st_size,
    }


def _extract_thumbnail(frame_index: int) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(VIDEO_PATH))
    if not capture.isOpened():
        raise RuntimeError("썸네일 추출을 위해 MP4를 열지 못했습니다.")
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise RuntimeError("영상에서 썸네일 프레임을 읽지 못했습니다.")
    if not cv2.imwrite(str(THUMBNAIL_PATH), frame):
        raise RuntimeError("영상 썸네일을 저장하지 못했습니다.")
    return frame.shape[1], frame.shape[0]


def main() -> int:
    os.environ.pop("OPENAI_API_KEY", None)
    VIDEO_PATH.parent.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    VIDEO_PATH.unlink(missing_ok=True)
    THUMBNAIL_PATH.unlink(missing_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("Local Content Studio")
    apply_application_font(app)
    app.setStyleSheet(APP_STYLESHEET)

    recorder: Recorder | None = None
    thumbnail_frame_index = 0
    original_information = QMessageBox.information
    try:
        with TemporaryDirectory(prefix="portfolio-demo-", dir=TMP_ROOT) as runtime:
            runtime_root = Path(runtime)
            db = Database(runtime_root / "portfolio-demo.db", runtime_root / "output")
            storage = StorageService(db)
            image_service = ImageService()
            content_service = ContentService(db, storage)
            batch_service = BatchImageService(db, image_service, storage)
            _seed_demo_data(db, content_service, image_service, storage)

            original_generate = content_service.generate

            def paced_generate(request: ContentRequest):
                time.sleep(1.2)
                return original_generate(request)

            content_service.generate = paced_generate  # type: ignore[method-assign]
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

            QMessageBox.information = lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok
            recorder = Recorder(app, window)

            # 0:00~0:08 — 대시보드
            window.dashboard_page.refresh()
            recorder.hold(8)

            # 0:08~0:33 — 실제 Mock 콘텐츠 생성
            recorder.click_tab(1)
            recorder.hold(2)
            page = window.content_page
            page.region_combo.setEditText("")
            page.keyword_combo.setEditText("")
            recorder.animate_text(page.region_combo.setEditText, "부산 사상구", seconds=2.5)
            recorder.animate_text(page.keyword_combo.setEditText, "사고사진 정리", seconds=2.5)
            recorder.hold(2)
            recorder.click_button("콘텐츠 생성 및 저장", page)
            recorder.hold(3)
            _wait_for_content(window, app)
            recorder.hold(12)

            # 0:33~1:08 — 첫 샘플에서 실제 ROI 드래그, 픽셀 모자이크, 저장
            recorder.click_tab(3)
            recorder.hold(2)
            image_page = window.image_page
            image_page.sample_combo.setCurrentIndex(0)
            recorder.click_button("선택한 샘플 열기", image_page)
            recorder.hold(4)
            recorder.animate_roi((180, 165, 95, 115))
            recorder.animate_roi((160, 720, 460, 95))
            recorder.hold(4)
            pixel_index = image_page.method_combo.findData("pixelate")
            image_page.method_combo.setCurrentIndex(pixel_index)
            recorder.click_button("모자이크 미리보기", image_page)
            recorder.thumbnail_frame_index = recorder.frame_index + round(3 * FPS)
            recorder.hold(12)
            recorder.click_button("결과 이미지 저장", image_page)
            recorder.hold(5)

            # 1:08~1:31 — 두 번째 샘플에서 가우시안 블러와 저장
            image_page.sample_combo.setCurrentIndex(1)
            recorder.click_button("선택한 샘플 열기", image_page)
            recorder.hold(4)
            recorder.animate_roi((825, 205, 95, 115))
            recorder.animate_roi((450, 735, 220, 85))
            gaussian_index = image_page.method_combo.findData("gaussian")
            image_page.method_combo.setCurrentIndex(gaussian_index)
            recorder.hold(2)
            recorder.click_button("모자이크 미리보기", image_page)
            recorder.hold(8)
            recorder.click_button("결과 이미지 저장", image_page)
            recorder.hold(4)

            # 1:31~1:48 — 콘텐츠 및 이미지 SQLite 이력
            recorder.click_tab(5)
            window.history_page.refresh()
            window.history_page.tabs.setCurrentIndex(0)
            recorder.hold(7)
            window.history_page.tabs.setCurrentIndex(1)
            recorder.hold(10)

            # 1:48~2:00 — 활성 스케줄
            recorder.click_tab(4)
            window.schedule_page.refresh()
            if window.schedule_page.table.rowCount():
                window.schedule_page.table.selectRow(0)
            recorder.hold(12)

            # 2:00~2:12 — Mock 및 로컬 저장 설정
            recorder.click_tab(6)
            window.settings_page.load()
            recorder.hold(8)
            recorder.click_button("전체 설정 저장", window.settings_page)
            if "설정을 저장했습니다." not in window.settings_page.save_status.text():
                raise RuntimeError("설정 저장 상태를 확인하지 못했습니다.")
            scroll = window.settings_page.findChild(QScrollArea)
            if scroll is not None:
                scroll.ensureWidgetVisible(window.settings_page.save_status)
                app.processEvents()
            recorder.hold(4)

            # 2:12~2:20 — 갱신된 대시보드로 마무리
            recorder.click_tab(0)
            window.dashboard_page.refresh()
            recorder.hold(8)

            thumbnail_frame_index = recorder.thumbnail_frame_index
            recorder.close()
            recorder = None
            window.close()
            app.processEvents()

        metadata = _verify_video()
        thumbnail_size = _extract_thumbnail(thumbnail_frame_index)
        print(
            "video="
            f"{VIDEO_PATH} duration={metadata['duration']:.2f}s "
            f"size={metadata['size']} bytes "
            f"resolution={metadata['width']}x{metadata['height']} "
            f"fps={metadata['fps']:.2f} frames={metadata['frame_count']}"
        )
        print(
            f"thumbnail={THUMBNAIL_PATH} "
            f"resolution={thumbnail_size[0]}x{thumbnail_size[1]} "
            f"frame={thumbnail_frame_index}"
        )
        return 0
    finally:
        QMessageBox.information = original_information
        if recorder is not None:
            recorder.close()


if __name__ == "__main__":
    raise SystemExit(main())
