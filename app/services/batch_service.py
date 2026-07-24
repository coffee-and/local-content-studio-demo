from __future__ import annotations

from pathlib import Path

from app.database import Database
from app.models import BatchImageRequest
from app.services.image_service import ImageService
from app.services.storage_service import StorageService


class BatchImageService:
    def __init__(
        self,
        db: Database,
        image_service: ImageService,
        storage: StorageService,
    ) -> None:
        self.db = db
        self.image_service = image_service
        self.storage = storage

    def process(self, request: BatchImageRequest) -> dict[str, int]:
        files = sorted(
            path
            for path in request.input_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in self.image_service.IMAGE_EXTENSIONS
        )
        success = 0
        skipped = 0
        failed = 0

        for source in files:
            try:
                image = self.image_service.read(source)
                rois, detector = self.image_service.auto_rois(
                    image,
                    faces=request.detect_faces,
                    plates=request.detect_plates,
                )
                if not rois:
                    skipped += 1
                    self.db.insert_image_job(
                        source_path=str(source),
                        output_path=None,
                        method=request.method,
                        detector=detector,
                        roi_count=0,
                        status="skipped",
                        error="자동 검출 영역 없음",
                    )
                    continue
                output_image = self.image_service.apply(
                    image,
                    rois,
                    method=request.method,
                    strength=request.strength,
                )
                output = self.storage.save_processed_image(
                    source_path=source,
                    image=output_image,
                    suffix="auto_mosaic",
                )
                self.db.insert_image_job(
                    source_path=str(source),
                    output_path=str(output),
                    method=request.method,
                    detector=detector,
                    roi_count=len(rois),
                    status="success",
                )
                success += 1
            except Exception as exc:
                failed += 1
                self.db.insert_image_job(
                    source_path=str(source),
                    output_path=None,
                    method=request.method,
                    detector="batch",
                    roi_count=0,
                    status="failed",
                    error=str(exc),
                )
        return {"total": len(files), "success": success, "skipped": skipped, "failed": failed}
