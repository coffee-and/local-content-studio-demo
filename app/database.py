from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_after(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(
        timespec="seconds"
    )


class Database:
    def __init__(self, path: Path, default_output_dir: Path) -> None:
        self.path = Path(path)
        self.default_output_dir = Path(default_output_dir)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
        self.seed_defaults()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            template TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rotation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK(kind IN ('region', 'keyword')),
            value TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(kind, value)
        );

        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            prompt_id INTEGER,
            region TEXT NOT NULL,
            keyword TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            title_hash TEXT NOT NULL,
            body_hash TEXT NOT NULL,
            duplicate_score REAL NOT NULL DEFAULT 0,
            model TEXT NOT NULL,
            used_mock INTEGER NOT NULL DEFAULT 0,
            output_dir TEXT,
            status TEXT NOT NULL,
            error TEXT,
            FOREIGN KEY(prompt_id) REFERENCES prompts(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_generations_created_at
        ON generations(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_generations_title_hash
        ON generations(title_hash);

        CREATE TABLE IF NOT EXISTS image_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source_path TEXT NOT NULL,
            output_path TEXT,
            method TEXT NOT NULL,
            detector TEXT NOT NULL,
            roi_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_image_jobs_created_at
        ON image_jobs(created_at DESC);

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            interval_minutes INTEGER NOT NULL,
            next_run_at TEXT NOT NULL,
            last_run_at TEXT,
            prompt_id INTEGER,
            use_rotation INTEGER NOT NULL DEFAULT 1,
            fixed_region TEXT NOT NULL DEFAULT '',
            fixed_keyword TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(prompt_id) REFERENCES prompts(id) ON DELETE SET NULL
        );
        """
        with self.connection() as conn:
            conn.executescript(schema)

    def seed_defaults(self) -> None:
        defaults = {
            "output_root": str(self.default_output_dir),
            "openai_model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            "mock_mode": "1",
            "duplicate_threshold": "0.88",
        }
        for key, value in defaults.items():
            if self.get_setting(key) is None:
                self.set_setting(key, value)

        if not self.list_prompts():
            self.save_prompt(
                None,
                "네이버 블로그 기본",
                (
                    "당신은 정보성 네이버 블로그 글을 작성하는 콘텐츠 에디터입니다.\n"
                    "지역: {region}\n키워드: {keyword}\n\n"
                    "요구사항:\n"
                    "- 과장된 표현과 확인되지 않은 사실은 피합니다.\n"
                    "- 제목 1개와 읽기 쉬운 본문을 작성합니다.\n"
                    "- 본문은 도입, 핵심 내용, 마무리 순서로 구성합니다.\n"
                    "- 제목과 본문은 이전 결과와 다른 관점으로 작성합니다."
                ),
            )

        if not self.list_rotation_items("region"):
            for value in ["부산 사상구", "부산 부산진구", "부산 해운대구"]:
                self.add_rotation_item("region", value)

        if not self.list_rotation_items("keyword"):
            for value in ["교통사고 대처", "사고사진 정리", "보험 처리 절차"]:
                self.add_rotation_item("keyword", value)

    # Settings
    def get_setting(self, key: str) -> str | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        now = utc_now()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, str(value), now),
            )

    def all_settings(self) -> dict[str, str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    # Prompts
    def list_prompts(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM prompts ORDER BY active DESC, name ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_prompt(self, prompt_id: int | None) -> dict[str, Any] | None:
        with self.connection() as conn:
            if prompt_id is None:
                row = conn.execute(
                    "SELECT * FROM prompts WHERE active = 1 ORDER BY id LIMIT 1"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
                ).fetchone()
        return dict(row) if row else None

    def save_prompt(self, prompt_id: int | None, name: str, template: str) -> int:
        name = name.strip()
        template = template.strip()
        if not name or not template:
            raise ValueError("프롬프트 이름과 내용을 입력해 주세요.")
        now = utc_now()
        with self.connection() as conn:
            if prompt_id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO prompts(name, template, active, created_at, updated_at)
                    VALUES(?, ?, 1, ?, ?)
                    """,
                    (name, template, now, now),
                )
                return int(cursor.lastrowid)
            conn.execute(
                """
                UPDATE prompts
                SET name = ?, template = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, template, now, prompt_id),
            )
            return int(prompt_id)

    def delete_prompt(self, prompt_id: int) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))

    # Rotation items
    def list_rotation_items(self, kind: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM rotation_items
                WHERE kind = ?
                ORDER BY enabled DESC, sort_order ASC, id ASC
                """,
                (kind,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_rotation_item(self, kind: str, value: str) -> int:
        if kind not in {"region", "keyword"}:
            raise ValueError("지원하지 않는 로테이션 종류입니다.")
        value = value.strip()
        if not value:
            raise ValueError("값을 입력해 주세요.")
        with self.connection() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM rotation_items WHERE kind = ?",
                (kind,),
            ).fetchone()[0]
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO rotation_items(
                    kind, value, enabled, sort_order, created_at
                ) VALUES(?, ?, 1, ?, ?)
                """,
                (kind, value, int(max_order) + 1, utc_now()),
            )
            return int(cursor.lastrowid or 0)

    def delete_rotation_item(self, item_id: int) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM rotation_items WHERE id = ?", (item_id,))

    def next_rotation_item(self, kind: str) -> str:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM rotation_items
                WHERE kind = ? AND enabled = 1
                ORDER BY
                    CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END,
                    last_used_at ASC,
                    sort_order ASC,
                    id ASC
                LIMIT 1
                """,
                (kind,),
            ).fetchone()
            if not row:
                raise ValueError(f"활성화된 {kind} 항목이 없습니다.")
            conn.execute(
                "UPDATE rotation_items SET last_used_at = ? WHERE id = ?",
                (utc_now(), row["id"]),
            )
            return str(row["value"])

    # Generations
    def insert_generation(self, payload: dict[str, Any]) -> int:
        columns = [
            "created_at",
            "source",
            "prompt_id",
            "region",
            "keyword",
            "title",
            "body",
            "title_hash",
            "body_hash",
            "duplicate_score",
            "model",
            "used_mock",
            "output_dir",
            "status",
            "error",
        ]
        values = [payload.get(column) for column in columns]
        with self.connection() as conn:
            cursor = conn.execute(
                f"INSERT INTO generations({', '.join(columns)}) VALUES({', '.join('?' for _ in columns)})",
                values,
            )
            return int(cursor.lastrowid)

    def recent_generations(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM generations
                WHERE status = 'success'
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_generations(self, limit: int = 300) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM generations ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # Image jobs
    def insert_image_job(
        self,
        *,
        source_path: str,
        output_path: str | None,
        method: str,
        detector: str,
        roi_count: int,
        status: str,
        error: str | None = None,
    ) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO image_jobs(
                    created_at, source_path, output_path, method, detector,
                    roi_count, status, error
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    source_path,
                    output_path,
                    method,
                    detector,
                    roi_count,
                    status,
                    error,
                ),
            )
            return int(cursor.lastrowid)

    def list_image_jobs(self, limit: int = 300) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM image_jobs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # Schedules
    def create_schedule(
        self,
        *,
        name: str,
        interval_minutes: int,
        prompt_id: int | None,
        use_rotation: bool,
        fixed_region: str,
        fixed_keyword: str,
    ) -> int:
        if interval_minutes < 1:
            raise ValueError("실행 간격은 1분 이상이어야 합니다.")
        now = utc_now()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO schedules(
                    name, enabled, interval_minutes, next_run_at, last_run_at,
                    prompt_id, use_rotation, fixed_region, fixed_keyword,
                    created_at, updated_at
                ) VALUES(?, 1, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip() or "자동 생성",
                    interval_minutes,
                    utc_after(interval_minutes),
                    prompt_id,
                    1 if use_rotation else 0,
                    fixed_region.strip(),
                    fixed_keyword.strip(),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_schedules(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.*, p.name AS prompt_name
                FROM schedules s
                LEFT JOIN prompts p ON p.id = s.prompt_id
                ORDER BY s.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def set_schedule_enabled(self, schedule_id: int, enabled: bool) -> None:
        now = utc_now()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE schedules
                SET enabled = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (1 if enabled else 0, utc_after(1), now, schedule_id),
            )

    def delete_schedule(self, schedule_id: int) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))

    def get_schedule(self, schedule_id: int) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
        return dict(row) if row else None

    def claim_due_schedules(self) -> list[dict[str, Any]]:
        now = utc_now()
        claimed: list[dict[str, Any]] = []
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT * FROM schedules
                WHERE enabled = 1 AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (now,),
            ).fetchall()
            for row in rows:
                interval = int(row["interval_minutes"])
                next_run = (
                    datetime.now(timezone.utc) + timedelta(minutes=interval)
                ).isoformat(timespec="seconds")
                conn.execute(
                    """
                    UPDATE schedules
                    SET last_run_at = ?, next_run_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, next_run, now, row["id"]),
                )
                claimed.append(dict(row))
        return claimed

    # Dashboard
    def stats(self) -> dict[str, int]:
        with self.connection() as conn:
            generation_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM generations WHERE status = 'success'"
                ).fetchone()[0]
            )
            image_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM image_jobs WHERE status = 'success'"
                ).fetchone()[0]
            )
            schedule_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM schedules WHERE enabled = 1"
                ).fetchone()[0]
            )
            failure_count = int(
                conn.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM generations WHERE status = 'failed') +
                        (SELECT COUNT(*) FROM image_jobs WHERE status = 'failed')
                    """
                ).fetchone()[0]
            )
        return {
            "generations": generation_count,
            "images": image_count,
            "schedules": schedule_count,
            "failures": failure_count,
        }

    def export_rows(self, table: str) -> tuple[list[str], Sequence[sqlite3.Row]]:
        if table not in {"generations", "image_jobs", "schedules"}:
            raise ValueError("내보낼 수 없는 테이블입니다.")
        with self.connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC")
            rows = cursor.fetchall()
            headers = [description[0] for description in cursor.description]
        return headers, rows
