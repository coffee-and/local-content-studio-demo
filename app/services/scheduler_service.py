from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from app.database import Database


class SchedulerController(QObject):
    schedule_due = Signal(object)
    tick_failed = Signal(str)

    def __init__(self, db: Database, interval_ms: int = 5_000) -> None:
        super().__init__()
        self.db = db
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._tick)

    def start(self) -> None:
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()

    def check_now(self) -> None:
        self._tick()

    def _tick(self) -> None:
        try:
            for schedule in self.db.claim_due_schedules():
                self.schedule_due.emit(schedule)
        except Exception as exc:  # UI boundary
            self.tick_failed.emit(str(exc))
