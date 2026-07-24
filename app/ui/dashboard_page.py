from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
)


class DashboardPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.value_labels: dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        configure_page_layout(root)
        root.addWidget(
            page_header(
                "대시보드",
                "콘텐츠 생성, 이미지 처리와 자동 스케줄의 현재 상태를 한눈에 확인합니다.",
            )
        )

        cards = QGridLayout()
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        card_data = {
            "generations": ("생성된 콘텐츠", "SQLite에 저장된 성공 이력"),
            "images": ("이미지 처리", "모자이크 또는 블러 처리 완료"),
            "schedules": ("활성 스케줄", "프로그램 실행 중 동작"),
            "recent": ("최근 실행 상태", "가장 최근 콘텐츠 또는 이미지 작업"),
        }
        for index, (key, (title, description)) in enumerate(card_data.items()):
            card = QWidget()
            card.setObjectName("Card")
            layout = QVBoxLayout(card)
            configure_card_layout(layout, spacing=7)
            caption = QLabel(title)
            caption.setObjectName("CardCaption")
            value = QLabel("0" if key != "recent" else "대기")
            value.setObjectName("CardValue")
            detail = QLabel(description)
            detail.setObjectName("CardDescription")
            detail.setWordWrap(True)
            layout.addWidget(caption)
            layout.addWidget(value)
            layout.addWidget(detail)
            self.value_labels[key] = value
            cards.addWidget(card, 0, index)
            cards.setColumnStretch(index, 1)
        root.addLayout(cards)

        recent_card = QWidget()
        recent_card.setObjectName("Card")
        recent_layout = QVBoxLayout(recent_card)
        configure_card_layout(recent_layout)
        recent_header = QHBoxLayout()
        recent_header.setSpacing(10)
        recent_title = QLabel("최근 작업")
        recent_title.setObjectName("SectionTitle")
        self.empty_label = QLabel(
            "아직 생성된 작업이 없습니다. 콘텐츠 생성 또는 이미지 모자이크 기능을 실행해 보세요."
        )
        self.empty_label.setObjectName("Muted")
        refresh_button = QPushButton("새로고침")
        refresh_button.setToolTip("대시보드 통계와 최근 작업 목록을 다시 불러옵니다.")
        refresh_button.clicked.connect(self.refresh)
        recent_header.addWidget(recent_title)
        recent_header.addWidget(self.empty_label)
        recent_header.addStretch(1)
        recent_header.addWidget(refresh_button)
        recent_layout.addLayout(recent_header)

        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(
            ["작업 종류", "실행 일시", "상태", "결과 또는 메시지"]
        )
        configure_table(self.recent_table)
        self.recent_table.setMinimumHeight(150)
        recent_layout.addWidget(self.recent_table)
        root.addWidget(recent_card, 1)

        environment_card = QWidget()
        environment_card.setObjectName("Card")
        environment_layout = QVBoxLayout(environment_card)
        configure_card_layout(environment_layout)
        status_title = QLabel("실행 환경")
        status_title.setObjectName("SectionTitle")
        self.mode_label = QLabel()
        self.db_label = QLabel()
        self.output_label = QLabel()
        for label in (self.mode_label, self.db_label, self.output_label):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setWordWrap(True)
            environment_layout.addWidget(label)
        environment_layout.insertWidget(0, status_title)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        open_button = QPushButton("결과 폴더 열기")
        open_button.setProperty("primary", True)
        open_button.setToolTip("현재 설정된 결과물 저장 폴더를 Windows 탐색기로 엽니다.")
        open_button.clicked.connect(self.open_output_folder)
        button_row.addStretch()
        button_row.addWidget(open_button)
        environment_layout.addLayout(button_row)
        root.addWidget(environment_card)
        self.refresh()

    def refresh(self) -> None:
        stats = self.db.stats()
        for key in ("generations", "images", "schedules"):
            self.value_labels[key].setText(f"{stats[key]}건")

        generations = self.db.list_generations(limit=5)
        images = self.db.list_image_jobs(limit=5)
        recent = [
            {
                "kind": "콘텐츠 생성",
                "created_at": row["created_at"],
                "status": row["status"],
                "detail": row.get("output_dir") or row.get("error") or row.get("title"),
            }
            for row in generations
        ]
        recent.extend(
            {
                "kind": "이미지 처리",
                "created_at": row["created_at"],
                "status": row["status"],
                "detail": row.get("output_path") or row.get("error") or row.get("source_path"),
            }
            for row in images
        )
        recent.sort(key=lambda row: str(row["created_at"]), reverse=True)
        recent = recent[:5]

        if recent:
            latest_status = "성공" if recent[0]["status"] == "success" else "실패"
            self.value_labels["recent"].setText(latest_status)
        else:
            self.value_labels["recent"].setText("대기")
        self._populate_recent(recent)

        mock = (self.db.get_setting("mock_mode") or "1") == "1"
        api_status = "설정됨" if os.getenv("OPENAI_API_KEY") else "미설정"
        self.mode_label.setText(
            f"콘텐츠 생성 모드: {'Mock 데모' if mock else 'OpenAI API'} · API 키 {api_status}"
        )
        self.db_label.setText(f"SQLite 데이터베이스: {self.db.path}")
        self.output_label.setText(f"결과물 저장 폴더: {self.db.get_setting('output_root')}")

    def _populate_recent(self, rows: list[dict]) -> None:
        self.recent_table.setRowCount(len(rows))
        self.recent_table.setVisible(bool(rows))
        self.empty_label.setVisible(not rows)
        for row_index, row in enumerate(rows):
            status = "성공" if row["status"] == "success" else "실패"
            values = [row["kind"], row["created_at"], status, row["detail"] or "-"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column == 2:
                    item.setForeground(
                        Qt.GlobalColor.darkGreen if status == "성공" else Qt.GlobalColor.darkRed
                    )
                self.recent_table.setItem(row_index, column, item)
        self.recent_table.setColumnWidth(0, 120)
        self.recent_table.setColumnWidth(1, 180)
        self.recent_table.setColumnWidth(2, 80)

    def open_output_folder(self) -> None:
        path = Path(self.db.get_setting("output_root") or "")
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)
