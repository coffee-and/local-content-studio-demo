from __future__ import annotations

import logging

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from app.database import Database
from app.models import ContentRequest
from app.services.batch_service import BatchImageService
from app.services.content_service import ContentService
from app.services.image_service import ImageService
from app.services.scheduler_service import SchedulerController
from app.services.storage_service import StorageService
from app.ui.content_page import ContentPage
from app.ui.dashboard_page import DashboardPage
from app.ui.history_page import HistoryPage
from app.ui.image_page import ImagePage
from app.ui.prompt_page import PromptPage
from app.ui.schedule_page import SchedulePage
from app.ui.settings_page import SettingsPage
from app.ui.workers import FunctionWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        db: Database,
        content_service: ContentService,
        image_service: ImageService,
        storage_service: StorageService,
        batch_service: BatchImageService,
    ) -> None:
        super().__init__()
        self.db = db
        self.content_service = content_service
        self.image_service = image_service
        self.storage_service = storage_service
        self.batch_service = batch_service
        self.thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle("Local Content Studio — Portfolio Demo")
        self.resize(1400, 860)
        self.setMinimumSize(1180, 720)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.tabs.setMovable(False)
        self.dashboard_page = DashboardPage(db)
        self.content_page = ContentPage(db)
        self.prompt_page = PromptPage(db)
        self.image_page = ImagePage(db, image_service, storage_service)
        self.schedule_page = SchedulePage(db)
        self.history_page = HistoryPage(db)
        self.settings_page = SettingsPage(db, content_service)

        self.tabs.addTab(self.dashboard_page, "대시보드")
        self.tabs.addTab(self.content_page, "콘텐츠 생성")
        self.tabs.addTab(self.prompt_page, "프롬프트 관리")
        self.tabs.addTab(self.image_page, "이미지 모자이크")
        self.tabs.addTab(self.schedule_page, "스케줄러")
        self.tabs.addTab(self.history_page, "이력")
        self.tabs.addTab(self.settings_page, "설정")
        self.setCentralWidget(self.tabs)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("준비 완료")

        self.content_page.generate_requested.connect(self.run_content_generation)
        self.prompt_page.data_changed.connect(self.refresh_reference_data)
        self.image_page.batch_requested.connect(self.run_batch_processing)
        self.schedule_page.schedule_run_requested.connect(self.run_schedule)
        self.schedule_page.schedules_changed.connect(self.dashboard_page.refresh)
        self.settings_page.settings_changed.connect(self.refresh_after_settings)
        self.tabs.currentChanged.connect(self._tab_changed)

        self.scheduler = SchedulerController(db)
        self.scheduler.schedule_due.connect(self.run_schedule)
        self.scheduler.tick_failed.connect(
            lambda message: self.status.showMessage(f"스케줄 확인 실패: {message}", 7000)
        )
        self.scheduler.start()

    def run_content_generation(self, request: ContentRequest) -> None:
        self.content_page.set_busy(True, "콘텐츠를 생성하고 중복 여부를 확인하는 중입니다...")
        worker = FunctionWorker(self.content_service.generate, request)
        worker.signals.result.connect(self._content_success)
        worker.signals.error.connect(self._content_error)
        worker.signals.finished.connect(lambda: self.content_page.set_busy(False))
        self.thread_pool.start(worker)

    def run_schedule(self, schedule: dict) -> None:
        request = ContentRequest(
            prompt_id=schedule.get("prompt_id"),
            region=str(schedule.get("fixed_region") or ""),
            keyword=str(schedule.get("fixed_keyword") or ""),
            use_rotation=bool(schedule.get("use_rotation")),
            source=f"schedule:{schedule.get('id', 'manual')}",
        )
        self.status.showMessage(f"스케줄 실행 중: {schedule.get('name', '자동 생성')}")
        worker = FunctionWorker(self.content_service.generate, request)
        worker.signals.result.connect(lambda result: self._scheduled_success(schedule, result))
        worker.signals.error.connect(lambda message: self._scheduled_error(schedule, message))
        self.thread_pool.start(worker)

    def run_batch_processing(self, request) -> None:
        self.image_page.set_batch_busy(True)
        worker = FunctionWorker(self.batch_service.process, request)
        worker.signals.result.connect(self.image_page.show_batch_result)
        worker.signals.result.connect(lambda _result: self._refresh_stats_and_history())
        worker.signals.error.connect(self.image_page.show_batch_error)
        worker.signals.finished.connect(lambda: self.image_page.set_batch_busy(False))
        self.thread_pool.start(worker)

    def _content_success(self, result) -> None:
        self.content_page.show_result(result)
        self.status.showMessage(f"콘텐츠 저장 완료: {result.output_dir}", 8000)
        self._refresh_stats_and_history()

    def _content_error(self, message: str) -> None:
        self.content_page.show_error(message)
        self.status.showMessage(f"콘텐츠 생성 실패: {message}", 8000)
        self._refresh_stats_and_history()

    def _scheduled_success(self, schedule: dict, result) -> None:
        self.status.showMessage(f"스케줄 완료: {schedule.get('name')} → {result.output_dir}", 10000)
        self.schedule_page.set_execution_status(
            True, f"'{schedule.get('name')}' 실행과 결과 저장이 완료되었습니다."
        )
        self._refresh_stats_and_history()
        self.schedule_page.refresh()

    def _scheduled_error(self, schedule: dict, message: str) -> None:
        logger.error("Schedule %s failed: %s", schedule.get("id"), message)
        self.status.showMessage(f"스케줄 실패: {schedule.get('name')} / {message}", 10000)
        self.schedule_page.set_execution_status(
            False,
            f"'{schedule.get('name')}' 실행에 실패했습니다. 설정과 로그를 확인해 주세요.",
        )
        self._refresh_stats_and_history()
        self.schedule_page.refresh()

    def refresh_reference_data(self) -> None:
        self.content_page.refresh_inputs()
        self.schedule_page.refresh_inputs()
        self.dashboard_page.refresh()

    def refresh_after_settings(self) -> None:
        self.dashboard_page.refresh()
        self.content_page.refresh_settings()
        self.image_page.load_defaults()
        self.settings_page.load()

    def _refresh_stats_and_history(self) -> None:
        self.dashboard_page.refresh()
        self.history_page.refresh()

    def _tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.scheduler.stop()
        self.thread_pool.waitForDone(1500)
        event.accept()
