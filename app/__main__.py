from __future__ import annotations

import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from app.config import build_paths
from app.database import Database
from app.logging_setup import configure_logging
from app.services.batch_service import BatchImageService
from app.services.content_service import ContentService
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
from app.ui.main_window import MainWindow
from app.ui.style import APP_STYLESHEET, apply_application_font


def main() -> int:
    load_dotenv()
    paths = build_paths()
    configure_logging(paths.log_dir)

    db = Database(paths.database_path, paths.default_output_dir)
    storage = StorageService(db)
    image_service = ImageService()
    content_service = ContentService(db, storage)
    batch_service = BatchImageService(db, image_service, storage)

    app = QApplication(sys.argv)
    app.setApplicationName("Local Content Studio")
    apply_application_font(app)
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow(
        db=db,
        content_service=content_service,
        image_service=image_service,
        storage_service=storage,
        batch_service=batch_service,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
