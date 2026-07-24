from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.services.content_service import ContentService
from app.ui.components import (
    configure_card_layout,
    configure_page_layout,
    page_header,
    set_label_state,
)


class SettingsPage(QWidget):
    settings_changed = Signal()

    def __init__(self, db: Database, content_service: ContentService) -> None:
        super().__init__()
        self.db = db
        self.content_service = content_service

        root = QVBoxLayout(self)
        configure_page_layout(root)
        root.addWidget(
            page_header(
                "설정",
                "콘텐츠 생성 모드, 결과물 저장 위치와 이미지 처리 기본값을 관리합니다.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        openai_group = QGroupBox("1. OpenAI 설정")
        openai_form = QFormLayout(openai_group)
        configure_card_layout(openai_form)
        openai_form.setHorizontalSpacing(16)
        openai_form.setVerticalSpacing(10)
        self.model_edit = QLineEdit()
        self.model_edit.setToolTip("현재 OpenAI 프로젝트에서 사용할 수 있는 텍스트 모델명입니다.")
        self.mock_check = QCheckBox("API 키 없이 로컬 Mock 콘텐츠 생성")
        self.mock_check.setToolTip("활성화하면 외부 API를 호출하지 않고 예제 콘텐츠를 생성합니다.")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("현재 실행 세션에만 적용할 API 키")
        self.api_key_edit.setToolTip(
            "입력값은 SQLite에 저장하지 않으며 현재 프로세스 메모리에만 적용합니다."
        )
        api_button = QPushButton("세션 API 키 적용")
        api_button.setToolTip("입력한 키를 파일이나 DB에 저장하지 않고 현재 세션에 적용합니다.")
        api_button.clicked.connect(self.apply_api_key)
        api_row = QHBoxLayout()
        api_row.setSpacing(10)
        api_row.addWidget(self.api_key_edit, 1)
        api_row.addWidget(api_button)
        self.api_status = QLabel()
        self.api_status.setWordWrap(True)
        openai_form.addRow("OpenAI 모델", self.model_edit)
        openai_form.addRow("콘텐츠 생성 모드", self.mock_check)
        openai_form.addRow("OpenAI API 키", api_row)
        openai_form.addRow("API 연결 상태", self.api_status)
        content_layout.addWidget(openai_group)

        output_group = QGroupBox("2. 결과물 저장 폴더")
        output_layout = QVBoxLayout(output_group)
        configure_card_layout(output_layout)
        output_note = QLabel(
            "콘텐츠와 처리 이미지는 원본과 분리해 이 폴더 아래에 날짜별로 저장합니다."
        )
        output_note.setObjectName("Muted")
        output_note.setWordWrap(True)
        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        self.output_edit = QLineEdit()
        self.output_edit.setToolTip("콘텐츠와 이미지 처리 결과가 저장될 로컬 폴더입니다.")
        browse_button = QPushButton("폴더 선택")
        browse_button.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(browse_button)
        output_layout.addWidget(output_note)
        output_layout.addLayout(output_row)
        content_layout.addWidget(output_group)

        drive_group = QGroupBox("3. Google Drive Desktop 동기화 폴더")
        drive_layout = QHBoxLayout(drive_group)
        configure_card_layout(drive_layout)
        drive_note = QLabel(
            "Drive API를 호출하지 않습니다. Google Drive Desktop이 동기화하는 로컬 폴더를 "
            "결과물 저장 폴더로 선택하면 저장 결과가 함께 동기화됩니다."
        )
        drive_note.setObjectName("Muted")
        drive_note.setWordWrap(True)
        drive_button = QPushButton("동기화 폴더 선택")
        drive_button.setToolTip(
            "선택한 Google Drive Desktop 로컬 폴더를 결과물 저장 폴더로 사용합니다."
        )
        drive_button.clicked.connect(self.choose_output)
        drive_layout.addWidget(drive_note, 1)
        drive_layout.addWidget(drive_button)
        content_layout.addWidget(drive_group)

        image_group = QGroupBox("4. 이미지 처리 기본값")
        image_form = QFormLayout(image_group)
        configure_card_layout(image_form)
        image_form.setHorizontalSpacing(16)
        image_form.setVerticalSpacing(10)
        self.image_method_combo = QComboBox()
        self.image_method_combo.addItem("픽셀 모자이크", "pixelate")
        self.image_method_combo.addItem("가우시안 블러", "gaussian")
        self.image_strength_spin = QSpinBox()
        self.image_strength_spin.setRange(3, 40)
        self.image_strength_spin.setSuffix(" 단계")
        image_form.addRow("기본 처리 방식", self.image_method_combo)
        image_form.addRow("기본 처리 강도", self.image_strength_spin)
        content_layout.addWidget(image_group)

        behavior_group = QGroupBox("5. 프로그램 동작 설정")
        behavior_form = QFormLayout(behavior_group)
        configure_card_layout(behavior_form)
        behavior_form.setHorizontalSpacing(16)
        behavior_form.setVerticalSpacing(10)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.50, 1.00)
        self.threshold_spin.setSingleStep(0.01)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setToolTip(
            "최근 콘텐츠와 계산한 유사도가 이 값 이상이면 중복으로 처리합니다."
        )
        behavior_form.addRow("중복 유사도 차단 기준", self.threshold_spin)
        content_layout.addWidget(behavior_group)

        self.save_status = QLabel("설정을 변경한 뒤 저장해 주세요.")
        self.save_status.setObjectName("Muted")
        self.save_status.setWordWrap(True)
        save_row = QHBoxLayout()
        save_row.addWidget(self.save_status, 1)
        save_button = QPushButton("전체 설정 저장")
        save_button.setProperty("primary", True)
        save_button.setToolTip("현재 화면의 설정을 SQLite에 저장합니다.")
        save_button.clicked.connect(self.save)
        save_row.addWidget(save_button)
        content_layout.addLayout(save_row)
        content_layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.load()

    def load(self) -> None:
        self.output_edit.setText(self.db.get_setting("output_root") or "")
        self.model_edit.setText(self.db.get_setting("openai_model") or "gpt-5-mini")
        self.mock_check.setChecked((self.db.get_setting("mock_mode") or "1") == "1")
        self.threshold_spin.setValue(float(self.db.get_setting("duplicate_threshold") or "0.88"))
        method = self.db.get_setting("image_method") or "pixelate"
        index = self.image_method_combo.findData(method)
        if index >= 0:
            self.image_method_combo.setCurrentIndex(index)
        self.image_strength_spin.setValue(int(self.db.get_setting("image_strength") or "16"))
        self.api_key_edit.clear()
        self._refresh_api_status()

    def choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "결과물 저장 폴더 선택", self.output_edit.text()
        )
        if folder:
            self.output_edit.setText(folder)

    def apply_api_key(self) -> None:
        key = self.api_key_edit.text().strip()
        if not key:
            QMessageBox.information(
                self, "API 키 입력 필요", "현재 세션에 적용할 API 키를 입력해 주세요."
            )
            return
        self.content_service.set_session_api_key(key)
        self.api_key_edit.clear()
        self._refresh_api_status()
        QMessageBox.information(
            self,
            "세션 API 키 적용",
            "현재 프로그램 실행 세션에만 적용했습니다. 코드나 SQLite에는 저장하지 않습니다.",
        )

    def save(self) -> None:
        if not self.output_edit.text().strip():
            QMessageBox.information(self, "저장 폴더 필요", "결과물을 저장할 폴더를 선택해 주세요.")
            return
        output = Path(self.output_edit.text()).expanduser()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "결과물 폴더 오류",
                f"선택한 폴더를 준비하지 못했습니다. 경로와 권한을 확인해 주세요.\n{exc}",
            )
            return
        self.db.set_setting("output_root", str(output))
        self.db.set_setting("openai_model", self.model_edit.text().strip() or "gpt-5-mini")
        self.db.set_setting("mock_mode", "1" if self.mock_check.isChecked() else "0")
        self.db.set_setting("duplicate_threshold", f"{self.threshold_spin.value():.2f}")
        self.db.set_setting("image_method", str(self.image_method_combo.currentData()))
        self.db.set_setting("image_strength", str(self.image_strength_spin.value()))
        set_label_state(
            self.save_status,
            "설정을 저장했습니다. 새 기본값이 관련 화면에 반영됩니다.",
            "success",
        )
        self.settings_changed.emit()

    def _refresh_api_status(self) -> None:
        set_label_state(
            self.api_status,
            "환경 변수 또는 현재 세션 API 키가 설정되어 있습니다."
            if os.getenv("OPENAI_API_KEY")
            else "API 키가 없습니다. Mock 모드를 사용하면 주요 기능을 시연할 수 있습니다.",
            "success" if os.getenv("OPENAI_API_KEY") else "warning",
        )
