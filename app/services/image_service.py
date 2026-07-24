from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

ROI = tuple[int, int, int, int]


class ImageService:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    def __init__(self) -> None:
        cascade_dir = Path(cv2.data.haarcascades)
        self.face_cascade = cv2.CascadeClassifier(
            str(cascade_dir / "haarcascade_frontalface_default.xml")
        )
        plate_path = cascade_dir / "haarcascade_russian_plate_number.xml"
        self.plate_cascade = (
            cv2.CascadeClassifier(str(plate_path)) if plate_path.exists() else None
        )

    @staticmethod
    def read(path: Path) -> np.ndarray:
        data = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"이미지를 읽을 수 없습니다: {path}")
        return image

    def detect_faces(self, image: np.ndarray) -> list[ROI]:
        if self.face_cascade.empty():
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detections = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
        )
        return [tuple(map(int, detection)) for detection in detections]

    def detect_plates(self, image: np.ndarray) -> list[ROI]:
        if self.plate_cascade is None or self.plate_cascade.empty():
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detections = self.plate_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(40, 12),
        )
        return [tuple(map(int, detection)) for detection in detections]

    @staticmethod
    def clamp_roi(roi: ROI, width: int, height: int) -> ROI | None:
        x, y, w, h = map(int, roi)
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(0, min(w, width - x))
        h = max(0, min(h, height - y))
        if w < 2 or h < 2:
            return None
        return x, y, w, h

    def apply(
        self,
        image: np.ndarray,
        rois: Iterable[ROI],
        *,
        method: str,
        strength: int,
    ) -> np.ndarray:
        output = image.copy()
        height, width = output.shape[:2]
        for roi in rois:
            bounded = self.clamp_roi(roi, width, height)
            if bounded is None:
                continue
            x, y, w, h = bounded
            crop = output[y : y + h, x : x + w]
            if method == "gaussian":
                kernel = max(3, int(strength) * 2 + 1)
                if kernel % 2 == 0:
                    kernel += 1
                processed = cv2.GaussianBlur(crop, (kernel, kernel), 0)
            else:
                divisor = max(2, int(strength))
                small_w = max(1, w // divisor)
                small_h = max(1, h // divisor)
                reduced = cv2.resize(crop, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
                processed = cv2.resize(reduced, (w, h), interpolation=cv2.INTER_NEAREST)
            output[y : y + h, x : x + w] = processed
        return output

    def auto_rois(
        self,
        image: np.ndarray,
        *,
        faces: bool,
        plates: bool,
    ) -> tuple[list[ROI], str]:
        rois: list[ROI] = []
        detectors: list[str] = []
        if faces:
            rois.extend(self.detect_faces(image))
            detectors.append("face-haar")
        if plates:
            rois.extend(self.detect_plates(image))
            detectors.append("plate-haar-demo")
        return rois, "+".join(detectors) or "manual"
