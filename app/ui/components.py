from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QLayout,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

PAGE_MARGINS = (24, 20, 24, 20)
PAGE_SPACING = 18
CARD_MARGINS = (16, 20, 16, 16)
CARD_SPACING = 12
ROW_SPACING = 10


def configure_page_layout(layout: QLayout, *, spacing: int = PAGE_SPACING) -> None:
    layout.setContentsMargins(*PAGE_MARGINS)
    layout.setSpacing(spacing)


def configure_card_layout(layout: QLayout, *, spacing: int = CARD_SPACING) -> None:
    layout.setContentsMargins(*CARD_MARGINS)
    layout.setSpacing(spacing)


def page_header(title: str, description: str) -> QWidget:
    container = QWidget()
    container.setObjectName("PageHeader")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)

    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    description_label = QLabel(description)
    description_label.setObjectName("PageDescription")
    description_label.setWordWrap(True)

    layout.addWidget(title_label)
    layout.addWidget(description_label)
    return container


def configure_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(36)
    table.horizontalHeader().setMinimumSectionSize(72)
    table.horizontalHeader().setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)


def set_label_state(label: QLabel, text: str, state: str = "muted") -> None:
    object_names = {
        "muted": "Muted",
        "success": "StatusSuccess",
        "warning": "StatusWarning",
        "error": "StatusError",
        "info": "StatusInfo",
    }
    label.setObjectName(object_names.get(state, "Muted"))
    label.setText(text)
    label.style().unpolish(label)
    label.style().polish(label)
