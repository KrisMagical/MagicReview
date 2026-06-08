"""File parsing helpers."""

from __future__ import annotations

from pathlib import Path


def read_python_file(file_path: str | Path) -> tuple[str, str]:
    """Return normalized file path and UTF-8 source for a Python file."""

    path = Path(file_path)
    return str(path), path.read_text(encoding="utf-8")
