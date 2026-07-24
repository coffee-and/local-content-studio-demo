from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.ui.components import (
    configure_card_layout,
    configure_page_layout,
    page_header,
    set_label_state,
)


class RotationEditor(QGroupBox):
    changed = Signal()

    def __init__(self, db: Database, kind: str, title: str) -> None:
        super().__init__(title)
        self.db = db
        self.kind = kind
        layout = QVBoxLayout(self)
        configure_card_layout(layout)
        self.list_widget = QListWidget()
        self.list_widget.setToolTip(f"콘텐츠 생성에 사용할 {title} 목록입니다.")
        layout.addWidget(self.list_widget)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText(f"새 {title} 입력")
        self.input.returnPressed.connect(self.add_item)
        add_button = QPushButton(f"{title} 추가")
        add_button.clicked.connect(self.add_item)
        delete_button = QPushButton("선택 삭제")
        delete_button.setProperty("danger", True)
        delete_button.clicked.connect(self.delete_selected)
        row.addWidget(self.input, 1)
        row.addWidget(add_button)
        row.addWidget(delete_button)
        layout.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        for item in self.db.list_rotation_items(self.kind):
            widget_item = QListWidgetItem(item["value"])
            widget_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.list_widget.addItem(widget_item)

    def add_item(self) -> None:
        if not self.input.text().strip():
            QMessageBox.information(self, "입력 필요", f"추가할 {self.title()}을 입력해 주세요.")
            return
        try:
            self.db.add_rotation_item(self.kind, self.input.text())
        except Exception as exc:
            QMessageBox.warning(
                self,
                "항목 추가 실패",
                f"{self.title()}을 추가하지 못했습니다. 중복 여부를 확인해 주세요.\n{exc}",
            )
            return
        self.input.clear()
        self.refresh()
        self.changed.emit()

    def delete_selected(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(
                self, "선택 필요", f"삭제할 {self.title()}을 먼저 선택해 주세요."
            )
            return
        self.db.delete_rotation_item(int(item.data(Qt.ItemDataRole.UserRole)))
        self.refresh()
        self.changed.emit()


class PromptPage(QWidget):
    data_changed = Signal()

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.current_prompt_id: int | None = None
        self._loading = False
        self._dirty = False

        root = QVBoxLayout(self)
        configure_page_layout(root)
        root.addWidget(
            page_header(
                "프롬프트 관리",
                "콘텐츠 프롬프트를 편집하고 자동 로테이션에 사용할 지역과 키워드를 관리합니다.",
            )
        )

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        prompt_group = QGroupBox("프롬프트 목록과 편집")
        prompt_layout = QHBoxLayout(prompt_group)
        configure_card_layout(prompt_layout)

        list_panel = QVBoxLayout()
        list_panel.setSpacing(10)
        list_title = QLabel("저장된 프롬프트")
        list_title.setObjectName("CardCaption")
        self.prompt_list = QListWidget()
        self.prompt_list.setMinimumWidth(230)
        self.prompt_list.currentItemChanged.connect(self._load_selected)
        new_button = QPushButton("새 프롬프트")
        new_button.clicked.connect(self.new_prompt)
        import_button = QPushButton("TXT 파일 불러오기")
        import_button.setToolTip("UTF-8 또는 CP949 형식의 TXT 프롬프트를 불러옵니다.")
        import_button.clicked.connect(self.import_txt)
        list_panel.addWidget(list_title)
        list_panel.addWidget(self.prompt_list, 1)
        list_panel.addWidget(new_button)
        list_panel.addWidget(import_button)

        editor_panel = QVBoxLayout()
        editor_panel.setSpacing(8)
        self.selection_label = QLabel("현재 선택: 없음")
        self.selection_label.setObjectName("Muted")
        self.file_label = QLabel("TXT 파일 위치: 직접 작성")
        self.file_label.setObjectName("Muted")
        self.file_label.setWordWrap(True)
        name_label = QLabel("프롬프트 이름")
        name_label.setObjectName("CardCaption")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("목록에서 구분할 이름을 입력하세요.")
        content_label = QLabel("프롬프트 내용")
        content_label.setObjectName("CardCaption")
        self.template_edit = QPlainTextEdit()
        self.template_edit.setPlaceholderText(
            "프롬프트 내용을 입력하세요. {region}, {keyword} 자리표시자를 사용할 수 있습니다."
        )
        self.name_edit.textChanged.connect(self._mark_dirty)
        self.template_edit.textChanged.connect(self._mark_dirty)
        self.dirty_label = QLabel("저장된 상태입니다.")
        self.dirty_label.setObjectName("Muted")
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        save_button = QPushButton("프롬프트 저장")
        save_button.setProperty("primary", True)
        save_button.clicked.connect(self.save_prompt)
        delete_button = QPushButton("현재 프롬프트 삭제")
        delete_button.setProperty("danger", True)
        delete_button.clicked.connect(self.delete_prompt)
        buttons.addWidget(save_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()

        editor_panel.addWidget(self.selection_label)
        editor_panel.addWidget(self.file_label)
        editor_panel.addWidget(name_label)
        editor_panel.addWidget(self.name_edit)
        editor_panel.addWidget(content_label)
        editor_panel.addWidget(self.template_edit, 1)
        editor_panel.addWidget(self.dirty_label)
        editor_panel.addLayout(buttons)

        prompt_layout.addLayout(list_panel, 1)
        prompt_layout.addLayout(editor_panel, 2)

        rotation_container = QWidget()
        rotation_layout = QHBoxLayout(rotation_container)
        rotation_layout.setContentsMargins(0, 0, 0, 0)
        rotation_layout.setSpacing(14)
        self.region_editor = RotationEditor(db, "region", "지역")
        self.keyword_editor = RotationEditor(db, "keyword", "키워드")
        self.region_editor.changed.connect(self.data_changed.emit)
        self.keyword_editor.changed.connect(self.data_changed.emit)
        rotation_layout.addWidget(self.region_editor)
        rotation_layout.addWidget(self.keyword_editor)

        splitter.addWidget(prompt_group)
        splitter.addWidget(rotation_container)
        splitter.setSizes([470, 230])
        root.addWidget(splitter, 1)
        self.refresh()

    def refresh(self) -> None:
        selected_id = self.current_prompt_id
        self.prompt_list.clear()
        selected_item: QListWidgetItem | None = None
        for prompt in self.db.list_prompts():
            item = QListWidgetItem(prompt["name"])
            item.setData(Qt.ItemDataRole.UserRole, prompt["id"])
            self.prompt_list.addItem(item)
            if prompt["id"] == selected_id:
                selected_item = item
        self.region_editor.refresh()
        self.keyword_editor.refresh()
        if selected_item:
            self.prompt_list.setCurrentItem(selected_item)
        elif self.prompt_list.count():
            self.prompt_list.setCurrentRow(0)

    def new_prompt(self) -> None:
        self.current_prompt_id = None
        self.prompt_list.clearSelection()
        self._loading = True
        self.name_edit.clear()
        self.template_edit.clear()
        self._loading = False
        self.selection_label.setText("현재 선택: 새 프롬프트")
        self.file_label.setText("TXT 파일 위치: 직접 작성")
        self._set_dirty(False)
        self.name_edit.setFocus()

    def _load_selected(self, current: QListWidgetItem | None, _previous) -> None:
        if not current:
            return
        prompt_id = int(current.data(Qt.ItemDataRole.UserRole))
        prompt = self.db.get_prompt(prompt_id)
        if not prompt:
            return
        self._loading = True
        self.current_prompt_id = prompt_id
        self.name_edit.setText(prompt["name"])
        self.template_edit.setPlainText(prompt["template"])
        self._loading = False
        self.selection_label.setText(f"현재 선택: {prompt['name']}")
        self.file_label.setText("TXT 파일 위치: 데이터베이스에 저장됨")
        self._set_dirty(False)

    def save_prompt(self) -> None:
        if not self.name_edit.text().strip() or not self.template_edit.toPlainText().strip():
            QMessageBox.information(self, "입력 확인", "프롬프트 이름과 내용을 모두 입력해 주세요.")
            return
        try:
            self.current_prompt_id = self.db.save_prompt(
                self.current_prompt_id,
                self.name_edit.text(),
                self.template_edit.toPlainText(),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "프롬프트 저장 실패",
                f"입력 내용을 저장하지 못했습니다. 이름 중복 여부를 확인해 주세요.\n{exc}",
            )
            return
        self.refresh()
        self._set_dirty(False)
        self.data_changed.emit()

    def delete_prompt(self) -> None:
        if self.current_prompt_id is None:
            QMessageBox.information(self, "선택 필요", "삭제할 프롬프트를 먼저 선택해 주세요.")
            return
        if self.prompt_list.count() <= 1:
            QMessageBox.information(self, "삭제 불가", "프롬프트는 최소 1개가 필요합니다.")
            return
        self.db.delete_prompt(self.current_prompt_id)
        self.current_prompt_id = None
        self.refresh()
        self.data_changed.emit()

    def import_txt(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "프롬프트 TXT 선택", "", "Text files (*.txt);;All files (*)"
        )
        if not filename:
            return
        path = Path(filename)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="cp949")
        except OSError as exc:
            QMessageBox.warning(self, "TXT 불러오기 실패", f"선택한 파일을 읽지 못했습니다.\n{exc}")
            return
        self.current_prompt_id = None
        self._loading = True
        self.name_edit.setText(path.stem)
        self.template_edit.setPlainText(content)
        self._loading = False
        self.selection_label.setText(f"현재 선택: {path.stem} (저장 전)")
        self.file_label.setText(f"TXT 파일 위치: {path}")
        self.file_label.setToolTip(str(path))
        self._set_dirty(True)

    def _mark_dirty(self) -> None:
        if not self._loading:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        set_label_state(
            self.dirty_label,
            "저장되지 않은 변경 사항이 있습니다." if dirty else "현재 내용은 저장된 상태입니다.",
            "warning" if dirty else "muted",
        )
