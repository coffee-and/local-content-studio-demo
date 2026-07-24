from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.ui.components import configure_page_layout, configure_table, page_header


class HistoryPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        configure_page_layout(root)
        root.addWidget(
            page_header(
                "이력",
                "콘텐츠 생성과 이미지 처리 결과를 구분해 확인하고 현재 목록을 CSV로 내보냅니다.",
            )
        )

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("Muted")
        refresh_button = QPushButton("이력 새로고침")
        refresh_button.setToolTip("SQLite에서 최신 콘텐츠와 이미지 처리 이력을 다시 읽습니다.")
        refresh_button.clicked.connect(self.refresh)
        export_button = QPushButton("현재 탭 CSV 내보내기")
        export_button.setProperty("primary", True)
        export_button.setToolTip("현재 선택한 이력 탭 전체를 UTF-8 CSV 파일로 저장합니다.")
        export_button.clicked.connect(self.export_current)
        actions.addWidget(self.summary_label, 1)
        actions.addWidget(refresh_button)
        actions.addWidget(export_button)
        root.addLayout(actions)

        self.tabs = QTabWidget()
        self.generation_table = QTableWidget()
        self.image_table = QTableWidget()
        configure_table(self.generation_table)
        configure_table(self.image_table)
        self.tabs.addTab(self.generation_table, "콘텐츠 생성 이력")
        self.tabs.addTab(self.image_table, "이미지 처리 이력")
        root.addWidget(self.tabs, 1)
        self.refresh()

    def refresh(self) -> None:
        generations = self.db.list_generations()
        generation_columns = [
            ("id", "ID"),
            ("created_at", "실행 일시"),
            ("status", "상태"),
            ("source", "실행 방식"),
            ("region", "지역"),
            ("keyword", "키워드"),
            ("title", "제목"),
            ("model", "모델"),
            ("duplicate_score", "유사도"),
            ("output_dir", "결과물 저장 위치"),
            ("error", "오류 메시지"),
        ]
        self._populate(self.generation_table, generations, generation_columns)

        images = self.db.list_image_jobs()
        image_columns = [
            ("id", "ID"),
            ("created_at", "처리 일시"),
            ("status", "상태"),
            ("source_path", "원본 이미지"),
            ("output_path", "결과 이미지"),
            ("method", "처리 방식"),
            ("detector", "ROI 방식"),
            ("roi_count", "ROI 개수"),
            ("error", "오류 메시지"),
        ]
        self._populate(self.image_table, images, image_columns)
        self.summary_label.setText(f"콘텐츠 {len(generations)}건 · 이미지 처리 {len(images)}건")

    @staticmethod
    def _populate(
        table: QTableWidget,
        rows: list[dict],
        columns: list[tuple[str, str]],
    ) -> None:
        table.clear()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels([label for _key, label in columns])
        if not rows:
            table.setRowCount(1)
            table.setSpan(0, 0, 1, len(columns))
            empty = QTableWidgetItem(
                "아직 저장된 이력이 없습니다. 해당 기능을 실행하면 이곳에 기록됩니다."
            )
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setForeground(Qt.GlobalColor.darkGray)
            table.setItem(0, 0, empty)
            return

        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, (column, _label) in enumerate(columns):
                value = row.get(column)
                text = str(value or "")
                if column == "status":
                    text = "성공" if value == "success" else "실패"
                elif column == "method":
                    text = "픽셀 모자이크" if value == "pixelate" else "가우시안 블러"
                item = QTableWidgetItem(text)
                item.setToolTip(str(value or ""))
                if column == "status":
                    item.setForeground(
                        Qt.GlobalColor.darkGreen if value == "success" else Qt.GlobalColor.darkRed
                    )
                table.setItem(row_index, column_index, item)

        widths = {
            "id": 56,
            "created_at": 190,
            "status": 72,
            "source": 110,
            "region": 110,
            "keyword": 130,
            "title": 250,
            "model": 110,
            "duplicate_score": 75,
            "output_dir": 300,
            "source_path": 260,
            "output_path": 280,
            "method": 110,
            "detector": 130,
            "roi_count": 80,
            "error": 220,
        }
        for index, (key, _label) in enumerate(columns):
            if key in widths:
                table.setColumnWidth(index, widths[key])

    def export_current(self) -> None:
        table_name = "generations" if self.tabs.currentIndex() == 0 else "image_jobs"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "CSV 저장",
            str(Path.home() / f"{table_name}.csv"),
            "CSV (*.csv)",
        )
        if not filename:
            return
        headers, rows = self.db.export_rows(table_name)
        with open(filename, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row[header] for header in headers])
