from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.ui.components import (
    configure_card_layout,
    configure_page_layout,
    configure_table,
    page_header,
    set_label_state,
)


class SchedulePage(QWidget):
    schedule_run_requested = Signal(object)
    schedules_changed = Signal()

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        configure_page_layout(root)
        root.addWidget(
            page_header(
                "스케줄러",
                "반복 콘텐츠 생성 조건을 저장하고 활성 상태, 마지막 실행과 다음 실행 시각을 확인합니다.",
            )
        )

        form_group = QGroupBox("1. 새 스케줄 등록")
        form_layout = QGridLayout(form_group)
        configure_card_layout(form_layout)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)
        self.name_edit = QLineEdit("자동 콘텐츠 생성")
        self.name_edit.setToolTip("스케줄 목록에서 구분할 이름을 입력합니다.")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 10080)
        self.interval_spin.setValue(60)
        self.interval_spin.setSuffix(" 분")
        self.prompt_combo = QComboBox()
        self.rotation_check = QCheckBox("지역과 키워드 자동 로테이션")
        self.rotation_check.setChecked(True)
        self.rotation_check.toggled.connect(self._toggle_fixed)
        self.region_edit = QLineEdit()
        self.region_edit.setPlaceholderText("예: 부산 사상구")
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("예: 사고사진 정리")
        self.region_edit.setEnabled(False)
        self.keyword_edit.setEnabled(False)
        add_button = QPushButton("스케줄 등록")
        add_button.setProperty("primary", True)
        add_button.setToolTip("입력한 조건을 활성 스케줄로 SQLite에 저장합니다.")
        add_button.clicked.connect(self.add_schedule)

        form_layout.addWidget(QLabel("스케줄 이름"), 0, 0)
        form_layout.addWidget(self.name_edit, 0, 1)
        form_layout.addWidget(QLabel("실행 간격"), 0, 2)
        form_layout.addWidget(self.interval_spin, 0, 3)
        form_layout.addWidget(QLabel("사용할 프롬프트"), 1, 0)
        form_layout.addWidget(self.prompt_combo, 1, 1)
        form_layout.addWidget(self.rotation_check, 1, 2, 1, 2)
        form_layout.addWidget(QLabel("고정 지역"), 2, 0)
        form_layout.addWidget(self.region_edit, 2, 1)
        form_layout.addWidget(QLabel("고정 키워드"), 2, 2)
        form_layout.addWidget(self.keyword_edit, 2, 3)
        form_layout.addWidget(add_button, 3, 3)
        form_layout.setColumnStretch(1, 1)
        form_layout.setColumnStretch(3, 1)
        root.addWidget(form_group)

        list_group = QGroupBox("2. 등록된 스케줄")
        list_layout = QVBoxLayout(list_group)
        configure_card_layout(list_layout)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        run_button = QPushButton("선택 스케줄 즉시 실행")
        run_button.setProperty("primary", True)
        run_button.setToolTip("선택한 스케줄을 예약 시각과 관계없이 한 번 실행합니다.")
        run_button.clicked.connect(self.run_selected)
        toggle_button = QPushButton("선택 스케줄 활성/중지")
        toggle_button.setToolTip("예약 실행 여부만 전환하며 즉시 실행하지 않습니다.")
        toggle_button.clicked.connect(self.toggle_selected)
        delete_button = QPushButton("선택 스케줄 삭제")
        delete_button.setProperty("danger", True)
        delete_button.clicked.connect(self.delete_selected)
        refresh_button = QPushButton("목록 새로고침")
        refresh_button.clicked.connect(self.refresh)
        actions.addWidget(run_button)
        actions.addWidget(toggle_button)
        actions.addWidget(delete_button)
        actions.addStretch()
        actions.addWidget(refresh_button)
        list_layout.addLayout(actions)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "스케줄 이름",
                "상태",
                "실행 간격",
                "프롬프트",
                "지역 및 키워드",
                "마지막 실행(UTC)",
                "다음 실행(UTC)",
            ]
        )
        configure_table(self.table)
        self.table.setColumnHidden(0, True)
        list_layout.addWidget(self.table, 1)
        self.status_label = QLabel(
            "스케줄을 선택하면 즉시 실행하거나 활성 상태를 바꿀 수 있습니다."
        )
        self.status_label.setObjectName("Muted")
        list_layout.addWidget(self.status_label)
        root.addWidget(list_group, 1)

        self.refresh_inputs()
        self.refresh()

    def refresh_inputs(self) -> None:
        current = self.prompt_combo.currentData()
        self.prompt_combo.clear()
        for prompt in self.db.list_prompts():
            self.prompt_combo.addItem(prompt["name"], prompt["id"])
        if current is not None:
            index = self.prompt_combo.findData(current)
            if index >= 0:
                self.prompt_combo.setCurrentIndex(index)

    def refresh(self) -> None:
        rows = self.db.list_schedules()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            condition = (
                "자동 로테이션"
                if row["use_rotation"]
                else f"{row['fixed_region']} · {row['fixed_keyword']}"
            )
            values = [
                row["id"],
                row["name"],
                "활성" if row["enabled"] else "중지",
                f"{row['interval_minutes']}분",
                row.get("prompt_name") or "기본",
                condition,
                row.get("last_run_at") or "-",
                row["next_run_at"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row["id"])
                if column == 2:
                    item.setForeground(
                        Qt.GlobalColor.darkGreen if row["enabled"] else Qt.GlobalColor.darkGray
                    )
                self.table.setItem(row_index, column, item)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 72)
        self.table.setColumnWidth(3, 92)
        self.table.setColumnWidth(4, 170)
        self.table.setColumnWidth(5, 210)
        self.table.setColumnWidth(6, 190)
        self.table.setColumnWidth(7, 190)
        if not rows:
            set_label_state(
                self.status_label,
                "등록된 스케줄이 없습니다. 위 조건을 입력해 첫 스케줄을 등록해 보세요.",
                "muted",
            )

    def add_schedule(self) -> None:
        if self.prompt_combo.currentData() is None:
            QMessageBox.information(
                self, "프롬프트 필요", "스케줄에 사용할 프롬프트를 선택해 주세요."
            )
            return
        if not self.rotation_check.isChecked() and (
            not self.region_edit.text().strip() or not self.keyword_edit.text().strip()
        ):
            QMessageBox.information(
                self,
                "고정 조건 필요",
                "자동 로테이션을 사용하지 않으려면 고정 지역과 키워드를 입력해 주세요.",
            )
            return
        try:
            self.db.create_schedule(
                name=self.name_edit.text(),
                interval_minutes=self.interval_spin.value(),
                prompt_id=self.prompt_combo.currentData(),
                use_rotation=self.rotation_check.isChecked(),
                fixed_region=self.region_edit.text(),
                fixed_keyword=self.keyword_edit.text(),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "스케줄 등록 실패",
                f"스케줄을 저장하지 못했습니다. 입력값을 확인해 주세요.\n{exc}",
            )
            return
        self.refresh()
        set_label_state(self.status_label, "새 스케줄을 활성 상태로 등록했습니다.", "success")
        self.schedules_changed.emit()

    def selected_schedule_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_or_notify(self) -> int | None:
        schedule_id = self.selected_schedule_id()
        if schedule_id is None:
            QMessageBox.information(
                self, "스케줄 선택", "목록에서 작업할 스케줄을 먼저 선택해 주세요."
            )
        return schedule_id

    def run_selected(self) -> None:
        schedule_id = self._selected_or_notify()
        if schedule_id is None:
            return
        schedule = self.db.get_schedule(schedule_id)
        if schedule:
            set_label_state(
                self.status_label,
                f"'{schedule['name']}' 스케줄을 실행하고 있습니다…",
                "info",
            )
            self.schedule_run_requested.emit(schedule)

    def toggle_selected(self) -> None:
        schedule_id = self._selected_or_notify()
        if schedule_id is None:
            return
        schedule = self.db.get_schedule(schedule_id)
        if not schedule:
            return
        enabled = not bool(schedule["enabled"])
        self.db.set_schedule_enabled(schedule_id, enabled)
        self.refresh()
        set_label_state(
            self.status_label,
            f"스케줄 상태를 {'활성' if enabled else '중지'}로 변경했습니다.",
            "success",
        )
        self.schedules_changed.emit()

    def delete_selected(self) -> None:
        schedule_id = self._selected_or_notify()
        if schedule_id is None:
            return
        self.db.delete_schedule(schedule_id)
        self.refresh()
        set_label_state(self.status_label, "선택한 스케줄을 삭제했습니다.", "success")
        self.schedules_changed.emit()

    def set_execution_status(self, success: bool, message: str) -> None:
        set_label_state(
            self.status_label,
            message,
            "success" if success else "error",
        )

    def _toggle_fixed(self, checked: bool) -> None:
        self.region_edit.setEnabled(not checked)
        self.keyword_edit.setEnabled(not checked)
