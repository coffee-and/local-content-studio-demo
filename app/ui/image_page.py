from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.models import BatchImageRequest
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
from app.ui.components import (
    configure_card_layout,
    configure_page_layout,
    page_header,
    set_label_state,
)
from app.ui.image_canvas import ImageCanvas

SAMPLE_IMAGES = (
    ("주차장 차량 접촉 사고", "parking_lot_minor_collision.png"),
    ("비 오는 도심 접촉 사고", "rainy_city_minor_collision.png"),
    ("골목 차량·오토바이 사고", "alley_car_scooter_collision.png"),
)


def sample_images_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return bundle_root / "sample_data" / "images"
    return Path(__file__).resolve().parents[2] / "sample_data" / "images"


class ImagePage(QWidget):
    batch_requested = Signal(object)

    def __init__(
        self,
        db: Database,
        image_service: ImageService,
        storage: StorageService,
    ) -> None:
        super().__init__()
        self.db = db
        self.image_service = image_service
        self.storage = storage
        self.source_path: Path | None = None
        self.original: np.ndarray | None = None
        self.processed: np.ndarray | None = None

        root = QVBoxLayout(self)
        configure_page_layout(root)
        root.addWidget(
            page_header(
                "이미지 모자이크",
                "샘플 또는 로컬 이미지를 열어 민감 영역을 지정하고, 원본과 처리 결과를 비교합니다.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        source_group = QGroupBox("1. 작업 이미지")
        source_layout = QGridLayout(source_group)
        configure_card_layout(source_layout)
        source_layout.setHorizontalSpacing(10)
        source_layout.setVerticalSpacing(9)
        self.sample_combo = QComboBox()
        for display_name, filename in SAMPLE_IMAGES:
            self.sample_combo.addItem(display_name, filename)
        self.sample_combo.setToolTip("포트폴리오용 AI 생성 가상 사고 이미지를 선택합니다.")
        sample_button = QPushButton("선택한 샘플 열기")
        sample_button.setProperty("primary", True)
        sample_button.setToolTip("선택한 샘플 이미지를 작업 화면에 불러옵니다.")
        sample_button.clicked.connect(self.open_selected_sample)
        load_button = QPushButton("내 이미지 열기")
        load_button.setToolTip("로컬 폴더에서 처리할 이미지 파일을 선택합니다.")
        load_button.clicked.connect(self.load_image)
        self.current_file_label = QLabel("현재 파일: 선택된 이미지 없음")
        self.current_file_label.setObjectName("Muted")
        self.current_file_label.setWordWrap(True)
        self.output_folder_label = QLabel()
        self.output_folder_label.setObjectName("Muted")
        self.output_folder_label.setWordWrap(True)
        source_layout.addWidget(QLabel("샘플 이미지"), 0, 0)
        source_layout.addWidget(self.sample_combo, 0, 1)
        source_layout.addWidget(sample_button, 0, 2)
        source_layout.addWidget(load_button, 0, 3)
        source_layout.addWidget(self.current_file_label, 1, 0, 1, 4)
        source_layout.addWidget(self.output_folder_label, 2, 0, 1, 4)
        source_layout.setColumnStretch(1, 1)
        content_layout.addWidget(source_group)

        compare = QSplitter(Qt.Orientation.Horizontal)
        compare.setChildrenCollapsible(False)

        original_panel = QWidget()
        original_layout = QVBoxLayout(original_panel)
        original_layout.setContentsMargins(0, 0, 4, 0)
        original_layout.setSpacing(7)
        original_title = QLabel("원본 및 ROI 지정")
        original_title.setObjectName("SectionTitle")
        self.canvas = ImageCanvas()
        self.canvas.setToolTip("얼굴이나 번호판 영역을 마우스로 드래그해 수동 ROI를 추가합니다.")
        self.canvas.rois_changed.connect(self._update_roi_label)
        legend = QLabel("수동 영역: 청록색 · 자동 검출 영역: 주황색")
        legend.setObjectName("Muted")
        original_layout.addWidget(original_title)
        original_layout.addWidget(self.canvas, 1)
        original_layout.addWidget(legend)

        result_panel = QWidget()
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(4, 0, 0, 0)
        result_layout.setSpacing(7)
        result_title = QLabel("처리 결과 미리보기")
        result_title.setObjectName("SectionTitle")
        self.result_canvas = ImageCanvas(
            interactive=False,
            empty_text="ROI를 지정하고 모자이크 미리보기를 적용하면 결과가 표시됩니다.",
        )
        result_note = QLabel("원본 파일은 변경하지 않고 결과 파일을 별도로 저장합니다.")
        result_note.setObjectName("Muted")
        result_layout.addWidget(result_title)
        result_layout.addWidget(self.result_canvas, 1)
        result_layout.addWidget(result_note)

        compare.addWidget(original_panel)
        compare.addWidget(result_panel)
        compare.setSizes([600, 600])
        compare.setMinimumHeight(330)
        content_layout.addWidget(compare, 1)

        options = QGroupBox("2. 처리 방식과 선택 영역")
        options_layout = QGridLayout(options)
        configure_card_layout(options_layout)
        options_layout.setHorizontalSpacing(10)
        options_layout.setVerticalSpacing(10)
        self.method_combo = QComboBox()
        self.method_combo.addItem("픽셀 모자이크", "pixelate")
        self.method_combo.addItem("가우시안 블러", "gaussian")
        self.method_combo.setToolTip("선택 영역에 적용할 이미지 처리 방식을 선택합니다.")
        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(3, 40)
        self.strength_slider.setValue(16)
        self.strength_slider.setToolTip("모자이크 블록 또는 블러의 강도를 조절합니다.")
        self.strength_label = QLabel("강도 16")
        self.strength_slider.valueChanged.connect(
            lambda value: self.strength_label.setText(f"강도 {value}")
        )
        self.roi_label = QLabel("선택 영역 0개")
        self.roi_label.setObjectName("ModeBadge")

        face_button = QPushButton("얼굴 자동 검출")
        face_button.setToolTip(
            "OpenCV 기본 검출기를 이용한 보조 기능입니다. 결과를 반드시 확인해 주세요."
        )
        face_button.clicked.connect(self.detect_faces)
        plate_button = QPushButton("번호판 자동 검출")
        plate_button.setToolTip(
            "범용 번호판 검출 보조 기능입니다. 한국 번호판 정확도를 보장하지 않습니다."
        )
        plate_button.clicked.connect(self.detect_plates)
        undo_button = QPushButton("마지막 영역 취소")
        undo_button.setToolTip("가장 최근에 추가한 선택 영역 한 개를 취소합니다.")
        undo_button.clicked.connect(self._undo)
        clear_button = QPushButton("선택 영역 초기화")
        clear_button.setProperty("danger", True)
        clear_button.setToolTip("현재 이미지에 지정한 모든 ROI를 삭제합니다.")
        clear_button.clicked.connect(self._clear)
        preview_button = QPushButton("모자이크 미리보기")
        preview_button.setProperty("primary", True)
        preview_button.setToolTip("현재 ROI에 선택한 처리 방식을 적용해 비교 화면에 표시합니다.")
        preview_button.clicked.connect(self.apply_preview)
        reset_button = QPushButton("결과 미리보기 초기화")
        reset_button.setToolTip("ROI는 유지하고 처리 결과 화면을 원본 상태로 되돌립니다.")
        reset_button.clicked.connect(self.reset_preview)
        save_button = QPushButton("결과 이미지 저장")
        save_button.setProperty("primary", True)
        save_button.setToolTip("원본 파일을 변경하지 않고 별도의 처리 결과 파일을 생성합니다.")
        save_button.clicked.connect(self.save_result)

        options_layout.addWidget(QLabel("처리 방식"), 0, 0)
        options_layout.addWidget(self.method_combo, 0, 1)
        options_layout.addWidget(self.strength_label, 0, 2)
        options_layout.addWidget(self.strength_slider, 0, 3, 1, 2)
        options_layout.addWidget(self.roi_label, 0, 5)
        options_layout.addWidget(face_button, 1, 0)
        options_layout.addWidget(plate_button, 1, 1)
        options_layout.addWidget(undo_button, 1, 2)
        options_layout.addWidget(clear_button, 1, 3)
        options_layout.addWidget(preview_button, 1, 4)
        options_layout.addWidget(save_button, 1, 5)
        options_layout.addWidget(reset_button, 2, 4, 1, 2)
        options_layout.setColumnStretch(3, 1)
        content_layout.addWidget(options)

        batch = QGroupBox("3. 폴더 일괄 처리")
        batch_layout = QHBoxLayout(batch)
        configure_card_layout(batch_layout)
        self.batch_faces = QCheckBox("얼굴 보조 검출")
        self.batch_faces.setChecked(True)
        self.batch_plates = QCheckBox("번호판 보조 검출")
        batch_button = QPushButton("입력 폴더 선택 후 처리")
        batch_button.setToolTip("지원 이미지가 있는 폴더를 작업 스레드에서 순서대로 처리합니다.")
        batch_button.clicked.connect(self.request_batch)
        self.batch_status = QLabel("대기 중 · 앱 실행 중 백그라운드 처리")
        self.batch_status.setObjectName("Muted")
        self.batch_status.setWordWrap(True)
        batch_layout.addWidget(self.batch_faces)
        batch_layout.addWidget(self.batch_plates)
        batch_layout.addWidget(batch_button)
        batch_layout.addWidget(self.batch_status, 1)
        content_layout.addWidget(batch)

        self.status_label = QLabel(
            "이미지를 불러온 뒤 얼굴이나 번호판 영역을 마우스로 드래그하세요."
        )
        self.status_label.setObjectName("StatusInfo")
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.load_defaults()

    def load_defaults(self) -> None:
        method = self.db.get_setting("image_method") or "pixelate"
        method_index = self.method_combo.findData(method)
        if method_index >= 0:
            self.method_combo.setCurrentIndex(method_index)
        self.strength_slider.setValue(int(self.db.get_setting("image_strength") or "16"))
        self.output_folder_label.setText(
            f"결과물 저장 폴더: {self.db.get_setting('output_root') or '설정 필요'}"
        )

    def open_selected_sample(self) -> None:
        filename = str(self.sample_combo.currentData() or "")
        path = sample_images_dir() / filename
        if not path.is_file():
            QMessageBox.warning(
                self,
                "샘플 이미지 없음",
                f"선택한 샘플 파일을 찾을 수 없습니다.\n{path}",
            )
            return
        self.load_path(path)

    def load_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "이미지 선택",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if filename:
            self.load_path(Path(filename))

    def load_path(self, path: Path) -> None:
        try:
            image = self.image_service.read(path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "이미지 열기 실패",
                f"선택한 이미지를 읽지 못했습니다. 파일 형식을 확인해 주세요.\n{exc}",
            )
            return
        self.source_path = path
        self.original = image
        self.processed = None
        self.canvas.set_image(image)
        self.result_canvas.set_image(image)
        self.current_file_label.setText(f"현재 파일: {path.name}")
        self.current_file_label.setToolTip(str(path))
        set_label_state(
            self.status_label,
            "이미지를 불러왔습니다. 민감 영역을 드래그하거나 보조 검출을 실행해 주세요.",
            "info",
        )

    def detect_faces(self) -> None:
        if not self._require_image():
            return
        rois = self.image_service.detect_faces(self.original)
        self.canvas.add_rois(rois, source="auto")
        set_label_state(
            self.status_label,
            f"얼굴 보조 검출로 {len(rois)}개 영역을 찾았습니다. 결과를 직접 확인해 주세요.",
            "warning" if rois else "muted",
        )

    def detect_plates(self) -> None:
        if not self._require_image():
            return
        rois = self.image_service.detect_plates(self.original)
        self.canvas.add_rois(rois, source="auto")
        set_label_state(
            self.status_label,
            f"번호판 보조 검출로 {len(rois)}개 영역을 찾았습니다. "
            "한국 번호판 정확도는 보장되지 않으므로 직접 확인해 주세요.",
            "warning",
        )

    def apply_preview(self) -> None:
        if not self._require_image():
            return
        if not self.canvas.rois:
            QMessageBox.information(
                self,
                "선택 영역 필요",
                "얼굴이나 번호판 영역을 먼저 드래그하거나 자동 검출을 실행해 주세요.",
            )
            return
        self.processed = self.image_service.apply(
            self.original,
            self.canvas.rois,
            method=str(self.method_combo.currentData()),
            strength=self.strength_slider.value(),
        )
        self.result_canvas.set_image(self.processed)
        set_label_state(
            self.status_label,
            "미리보기를 적용했습니다. 결과를 확인한 뒤 별도 파일로 저장할 수 있습니다.",
            "success",
        )

    def reset_preview(self) -> None:
        if self.original is not None:
            self.processed = None
            self.result_canvas.set_image(self.original)
            set_label_state(self.status_label, "결과 미리보기를 원본 상태로 되돌렸습니다.", "muted")

    def save_result(self) -> None:
        if not self._require_image() or self.source_path is None:
            return
        if not self.canvas.rois:
            QMessageBox.information(
                self, "선택 영역 필요", "저장하기 전에 처리할 영역을 지정해 주세요."
            )
            return
        output_image = (
            self.processed
            if self.processed is not None
            else self.image_service.apply(
                self.original,
                self.canvas.rois,
                method=str(self.method_combo.currentData()),
                strength=self.strength_slider.value(),
            )
        )
        try:
            output = self.storage.save_processed_image(
                source_path=self.source_path,
                image=output_image,
            )
            self.db.insert_image_job(
                source_path=str(self.source_path),
                output_path=str(output),
                method=str(self.method_combo.currentData()),
                detector="manual-or-assisted",
                roi_count=len(self.canvas.rois),
                status="success",
            )
        except Exception as exc:
            self.db.insert_image_job(
                source_path=str(self.source_path),
                output_path=None,
                method=str(self.method_combo.currentData()),
                detector="manual-or-assisted",
                roi_count=len(self.canvas.rois),
                status="failed",
                error=str(exc),
            )
            QMessageBox.warning(
                self,
                "결과 저장 실패",
                f"결과 파일을 저장하지 못했습니다. 저장 폴더와 권한을 확인해 주세요.\n{exc}",
            )
            return
        self.result_canvas.set_image(output_image)
        set_label_state(
            self.status_label, f"결과 이미지를 별도 파일로 저장했습니다.\n{output}", "success"
        )
        QMessageBox.information(self, "결과 저장 완료", str(output))

    def request_batch(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "일괄 처리할 이미지 폴더 선택")
        if not folder:
            return
        request = BatchImageRequest(
            input_dir=Path(folder),
            detect_faces=self.batch_faces.isChecked(),
            detect_plates=self.batch_plates.isChecked(),
            method=str(self.method_combo.currentData()),
            strength=self.strength_slider.value(),
        )
        self.batch_requested.emit(request)

    def set_batch_busy(self, busy: bool) -> None:
        self.batch_status.setText(
            "폴더 이미지를 처리하고 있습니다…" if busy else "대기 중 · 앱 실행 중 백그라운드 처리"
        )

    def show_batch_result(self, result: dict[str, int]) -> None:
        self.batch_status.setText(
            f"전체 {result['total']} · 성공 {result['success']} · "
            f"영역 없음 {result['skipped']} · 실패 {result['failed']}"
        )

    def show_batch_error(self, message: str) -> None:
        self.batch_status.setText(f"일괄 처리에 실패했습니다. 입력 폴더를 확인해 주세요. {message}")

    def _require_image(self) -> bool:
        if self.original is not None:
            return True
        QMessageBox.information(
            self, "이미지 필요", "먼저 샘플 이미지 또는 로컬 이미지를 열어 주세요."
        )
        return False

    def _undo(self) -> None:
        self.canvas.undo_roi()
        self.reset_preview()

    def _clear(self) -> None:
        self.canvas.clear_rois()
        self.reset_preview()

    def _update_roi_label(self, count: int) -> None:
        manual, automatic = self.canvas.roi_summary
        self.roi_label.setText(f"선택 영역 {count}개 · 수동 {manual} / 자동 {automatic}")
