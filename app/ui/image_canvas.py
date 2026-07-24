from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.services.image_service import ROI


class ImageCanvas(QWidget):
    rois_changed = Signal(int)

    def __init__(
        self,
        *,
        interactive: bool = True,
        empty_text: str = "이미지를 불러온 뒤 민감 영역을 마우스로 드래그하세요.",
    ) -> None:
        super().__init__()
        self.setObjectName("CanvasFrame")
        self.setMinimumSize(320, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._interactive = interactive
        self._empty_text = empty_text
        self._qimage: QImage | None = None
        self._image_width = 0
        self._image_height = 0
        self._rois: list[ROI] = []
        self._roi_sources: list[str] = []
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None
        self._target_rect = QRect()

    @property
    def rois(self) -> list[ROI]:
        return list(self._rois)

    @property
    def roi_summary(self) -> tuple[int, int]:
        automatic = sum(source == "auto" for source in self._roi_sources)
        return len(self._rois) - automatic, automatic

    def set_image(self, image: np.ndarray | None, *, keep_rois: bool = False) -> None:
        if image is None:
            self._qimage = None
            self._image_width = 0
            self._image_height = 0
            if not keep_rois:
                self.clear_rois()
            self.update()
            return

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        self._qimage = QImage(
            rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()
        self._image_width = width
        self._image_height = height
        if not keep_rois:
            self._rois.clear()
            self._roi_sources.clear()
            self.rois_changed.emit(0)
        self.update()

    def set_rois(self, rois: list[ROI], *, source: str = "manual") -> None:
        self._rois = [tuple(map(int, roi)) for roi in rois]
        self._roi_sources = [source] * len(self._rois)
        self.rois_changed.emit(len(self._rois))
        self.update()

    def add_rois(self, rois: list[ROI], *, source: str) -> None:
        normalized = [tuple(map(int, roi)) for roi in rois]
        self._rois.extend(normalized)
        self._roi_sources.extend([source] * len(normalized))
        self.rois_changed.emit(len(self._rois))
        self.update()

    def clear_rois(self) -> None:
        self._rois.clear()
        self._roi_sources.clear()
        self._drag_start = None
        self._drag_current = None
        self.rois_changed.emit(0)
        self.update()

    def undo_roi(self) -> None:
        if self._rois:
            self._rois.pop()
            self._roi_sources.pop()
            self.rois_changed.emit(len(self._rois))
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#17191f"))
        if self._qimage is None or self._qimage.isNull():
            painter.setPen(QColor("#9aa0aa"))
            painter.drawText(
                self.rect().adjusted(28, 28, -28, -28),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self._empty_text,
            )
            return

        self._target_rect = self._calculate_target_rect()
        painter.drawImage(self._target_rect, self._qimage)

        for roi, source in zip(self._rois, self._roi_sources, strict=True):
            color = QColor("#ff9f43") if source == "auto" else QColor("#4dd0e1")
            painter.setPen(QPen(color, 2))
            painter.drawRect(self._image_roi_to_widget(roi))

        if self._drag_start and self._drag_current:
            drag_pen = QPen(QColor("#4dd0e1"), 2, Qt.PenStyle.DashLine)
            painter.setPen(drag_pen)
            painter.drawRect(QRect(self._drag_start, self._drag_current).normalized())

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._interactive
            and event.button() == Qt.MouseButton.LeftButton
            and self._qimage is not None
            and self._target_rect.contains(event.position().toPoint())
        ):
            self._drag_start = event.position().toPoint()
            self._drag_current = self._drag_start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_start:
            point = event.position().toPoint()
            x = max(self._target_rect.left(), min(point.x(), self._target_rect.right()))
            y = max(self._target_rect.top(), min(point.y(), self._target_rect.bottom()))
            self._drag_current = QPoint(x, y)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self._drag_start:
            return
        self._drag_current = event.position().toPoint()
        widget_rect = QRect(self._drag_start, self._drag_current).normalized()
        self._drag_start = None
        self._drag_current = None

        if widget_rect.width() >= 6 and widget_rect.height() >= 6:
            roi = self._widget_rect_to_image(widget_rect)
            if roi and roi[2] >= 3 and roi[3] >= 3:
                self._rois.append(roi)
                self._roi_sources.append("manual")
                self.rois_changed.emit(len(self._rois))
        self.update()

    def _calculate_target_rect(self) -> QRect:
        if self._qimage is None or self._qimage.isNull():
            return QRect()
        available = self.rect().adjusted(12, 12, -12, -12)
        scale = min(
            available.width() / self._image_width,
            available.height() / self._image_height,
        )
        draw_width = max(1, int(self._image_width * scale))
        draw_height = max(1, int(self._image_height * scale))
        left = available.left() + (available.width() - draw_width) // 2
        top = available.top() + (available.height() - draw_height) // 2
        return QRect(left, top, draw_width, draw_height)

    def _image_roi_to_widget(self, roi: ROI) -> QRect:
        x, y, width, height = roi
        sx = self._target_rect.width() / self._image_width
        sy = self._target_rect.height() / self._image_height
        return QRect(
            self._target_rect.left() + int(x * sx),
            self._target_rect.top() + int(y * sy),
            max(1, int(width * sx)),
            max(1, int(height * sy)),
        )

    def _widget_rect_to_image(self, rect: QRect) -> ROI | None:
        intersection = rect.intersected(self._target_rect)
        if intersection.isEmpty():
            return None
        sx = self._image_width / self._target_rect.width()
        sy = self._image_height / self._target_rect.height()
        x = int((intersection.left() - self._target_rect.left()) * sx)
        y = int((intersection.top() - self._target_rect.top()) * sy)
        width = int(intersection.width() * sx)
        height = int(intersection.height() * sy)
        return x, y, width, height
