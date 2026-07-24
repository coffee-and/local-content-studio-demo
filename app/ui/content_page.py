from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.models import ContentRequest, ContentResult
from app.ui.components import (
    configure_card_layout,
    configure_page_layout,
    page_header,
    set_label_state,
)


class ContentPage(QWidget):
    generate_requested = Signal(object)

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        configure_page_layout(root)
        root.addWidget(
            page_header(
                "콘텐츠 생성",
                "지역과 키워드를 조합해 제목과 본문을 생성하고 결과를 로컬에 저장합니다.",
            )
        )

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(14)

        conditions = QGroupBox("1. 생성 조건")
        conditions_layout = QFormLayout(conditions)
        configure_card_layout(conditions_layout)
        conditions_layout.setHorizontalSpacing(16)
        conditions_layout.setVerticalSpacing(12)
        conditions_layout.setLabelAlignment(conditions_layout.labelAlignment())
        self.prompt_combo = QComboBox()
        self.prompt_combo.setToolTip("콘텐츠 생성에 사용할 프롬프트를 선택합니다.")
        self.region_combo = QComboBox()
        self.region_combo.setEditable(True)
        self.region_combo.setToolTip("콘텐츠에 반영할 지역을 선택하거나 입력합니다.")
        self.keyword_combo = QComboBox()
        self.keyword_combo.setEditable(True)
        self.keyword_combo.setToolTip("콘텐츠에 반영할 키워드를 선택하거나 입력합니다.")
        self.rotation_check = QCheckBox("지역과 키워드를 순서대로 자동 선택")
        self.rotation_check.setToolTip(
            "활성화하면 저장된 지역과 키워드를 생성할 때마다 순서대로 선택합니다."
        )
        self.rotation_check.toggled.connect(self._toggle_rotation)
        conditions_layout.addRow("사용할 프롬프트", self.prompt_combo)
        conditions_layout.addRow("지역", self.region_combo)
        conditions_layout.addRow("키워드", self.keyword_combo)
        conditions_layout.addRow("자동 로테이션", self.rotation_check)
        left_layout.addWidget(conditions)

        settings = QGroupBox("2. 생성 설정")
        settings_layout = QVBoxLayout(settings)
        configure_card_layout(settings_layout, spacing=8)
        self.mode_label = QLabel()
        self.mode_label.setObjectName("ModeBadge")
        self.mode_label.setWordWrap(True)
        self.model_label = QLabel()
        self.model_label.setObjectName("Muted")
        self.threshold_label = QLabel()
        self.threshold_label.setObjectName("Muted")
        settings_layout.addWidget(self.mode_label)
        settings_layout.addWidget(self.model_label)
        settings_layout.addWidget(self.threshold_label)
        left_layout.addWidget(settings)

        execute = QGroupBox("3. 실행")
        execute_layout = QVBoxLayout(execute)
        configure_card_layout(execute_layout)
        self.generate_button = QPushButton("콘텐츠 생성 및 저장")
        self.generate_button.setProperty("primary", True)
        self.generate_button.setToolTip(
            "선택한 조건으로 콘텐츠를 생성하고 결과와 이력을 저장합니다."
        )
        self.generate_button.clicked.connect(self._request_generation)
        self.status_label = QLabel("생성할 조건을 확인한 뒤 실행해 주세요.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("Muted")
        execute_layout.addWidget(self.generate_button)
        execute_layout.addWidget(self.status_label)
        left_layout.addWidget(execute)
        left_layout.addStretch()

        result = QGroupBox("4. 생성 결과")
        result_layout = QVBoxLayout(result)
        configure_card_layout(result_layout)
        title_label = QLabel("생성된 제목")
        title_label.setObjectName("CardCaption")
        self.title_edit = QLineEdit()
        self.title_edit.setReadOnly(True)
        self.title_edit.setPlaceholderText("콘텐츠를 생성하면 제목이 표시됩니다.")
        body_label = QLabel("생성된 본문")
        body_label.setObjectName("CardCaption")
        self.body_edit = QPlainTextEdit()
        self.body_edit.setReadOnly(True)
        self.body_edit.setPlaceholderText("콘텐츠를 생성하면 본문이 표시됩니다.")
        self.result_meta = QLabel("아직 저장된 결과가 없습니다.")
        self.result_meta.setWordWrap(True)
        self.result_meta.setTextInteractionFlags(self.result_meta.textInteractionFlags())
        self.result_meta.setObjectName("Muted")
        result_layout.addWidget(title_label)
        result_layout.addWidget(self.title_edit)
        result_layout.addWidget(body_label)
        result_layout.addWidget(self.body_edit, 1)
        result_layout.addWidget(self.result_meta)

        splitter.addWidget(left_panel)
        splitter.addWidget(result)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([480, 760])
        root.addWidget(splitter, 1)
        self.refresh_inputs()

    def refresh_inputs(self) -> None:
        current_prompt = self.prompt_combo.currentData()
        self.prompt_combo.clear()
        for prompt in self.db.list_prompts():
            self.prompt_combo.addItem(prompt["name"], prompt["id"])
        if current_prompt is not None:
            index = self.prompt_combo.findData(current_prompt)
            if index >= 0:
                self.prompt_combo.setCurrentIndex(index)

        self._fill_combo(self.region_combo, "region")
        self._fill_combo(self.keyword_combo, "keyword")
        self.refresh_settings()

    def refresh_settings(self) -> None:
        mock_mode = (self.db.get_setting("mock_mode") or "1") == "1"
        self.mode_label.setText(
            "Mock 모드 — API 키 없이 예제 콘텐츠를 생성합니다."
            if mock_mode
            else "OpenAI API 모드 — API 키 값은 화면에 표시하지 않습니다."
        )
        self.model_label.setText(
            f"사용 모델: {self.db.get_setting('openai_model') or 'gpt-5-mini'}"
        )
        threshold = float(self.db.get_setting("duplicate_threshold") or "0.88")
        self.threshold_label.setText(f"중복 유사도 차단 기준: {threshold:.2f}")

    def _fill_combo(self, combo: QComboBox, kind: str) -> None:
        current = combo.currentText()
        combo.clear()
        for item in self.db.list_rotation_items(kind):
            combo.addItem(item["value"])
        if current:
            combo.setEditText(current)

    def _toggle_rotation(self, checked: bool) -> None:
        self.region_combo.setEnabled(not checked)
        self.keyword_combo.setEnabled(not checked)

    def _request_generation(self) -> None:
        if self.prompt_combo.currentData() is None:
            QMessageBox.information(self, "프롬프트 필요", "사용할 프롬프트를 먼저 선택해 주세요.")
            return
        if not self.rotation_check.isChecked() and (
            not self.region_combo.currentText().strip()
            or not self.keyword_combo.currentText().strip()
        ):
            QMessageBox.information(
                self,
                "생성 조건 확인",
                "지역과 키워드를 입력하거나 자동 로테이션을 선택해 주세요.",
            )
            return
        request = ContentRequest(
            prompt_id=self.prompt_combo.currentData(),
            region=self.region_combo.currentText(),
            keyword=self.keyword_combo.currentText(),
            use_rotation=self.rotation_check.isChecked(),
            source="manual",
        )
        self.generate_requested.emit(request)

    def set_busy(self, busy: bool, text: str = "") -> None:
        self.generate_button.setEnabled(not busy)
        self.generate_button.setText(
            "콘텐츠를 생성하고 있습니다…" if busy else "콘텐츠 생성 및 저장"
        )
        if busy:
            set_label_state(
                self.status_label,
                text or "콘텐츠를 생성하고 결과를 저장하고 있습니다…",
                "info",
            )
        elif self.status_label.text().startswith("콘텐츠를 생성"):
            set_label_state(self.status_label, "생성 작업이 끝났습니다.", "muted")

    def show_result(self, result: ContentResult) -> None:
        self.title_edit.setText(result.title)
        self.body_edit.setPlainText(result.body)
        mode = "Mock" if result.used_mock else "OpenAI API"
        self.result_meta.setText(
            f"지역: {result.region} · 키워드: {result.keyword} · 모델: {result.model} · "
            f"모드: {mode} · 최대 유사도: {result.duplicate_score:.2f}\n"
            f"결과물 저장 위치: {result.output_dir}"
        )
        self.result_meta.setToolTip(str(result.output_dir))
        set_label_state(self.status_label, "생성이 완료되어 결과와 이력을 저장했습니다.", "success")

    def show_error(self, message: str) -> None:
        set_label_state(
            self.status_label,
            f"콘텐츠 생성에 실패했습니다. 입력과 설정을 확인해 주세요.\n{message}",
            "error",
        )
