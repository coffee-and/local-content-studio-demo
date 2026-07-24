from pathlib import Path

import cv2
import numpy as np

from app.services.image_service import ImageService


def test_pixelate_changes_only_roi() -> None:
    service = ImageService()
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    for x in range(100):
        image[:, x] = (x, x, x)

    result = service.apply(image, [(20, 20, 40, 40)], method="pixelate", strength=10)

    assert np.array_equal(result[:10, :10], image[:10, :10])
    assert not np.array_equal(result[20:60, 20:60], image[20:60, 20:60])


def test_unicode_image_path_roundtrip(tmp_path: Path) -> None:
    service = ImageService()
    image = np.full((20, 20, 3), 127, dtype=np.uint8)
    path = tmp_path / "한글 이미지.png"
    cv2.imencode(".png", image)[1].tofile(str(path))
    loaded = service.read(path)
    assert loaded.shape == image.shape
