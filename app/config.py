from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "LocalContentStudio"


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    database_path: Path
    log_dir: Path
    default_output_dir: Path


def build_paths() -> AppPaths:
    """Return writable paths for both source and packaged Windows execution."""
    override = os.getenv("LCS_DATA_DIR")
    if override:
        data_dir = Path(override).expanduser().resolve()
    elif os.name == "nt" and os.getenv("LOCALAPPDATA"):
        data_dir = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    else:
        data_dir = Path.home() / f".{APP_NAME.lower()}"

    documents = Path.home() / "Documents"
    default_output = documents / f"{APP_NAME}Output"

    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    default_output.mkdir(parents=True, exist_ok=True)

    return AppPaths(
        data_dir=data_dir,
        database_path=data_dir / "local_content_studio.db",
        log_dir=log_dir,
        default_output_dir=default_output,
    )
