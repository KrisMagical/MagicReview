"""Project Python file scanner."""

from __future__ import annotations

from pathlib import Path


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
}


class ProjectScanner:
    """Discover Python files under a project root."""

    def __init__(self, exclude_dirs: set[str] | None = None) -> None:
        self.exclude_dirs = set(exclude_dirs or DEFAULT_EXCLUDE_DIRS)

    def scan(self, root: Path) -> list[Path]:
        """Return stable project-relative Python file paths."""

        project_root = root.resolve()
        if project_root.is_file():
            return [Path(project_root.name)] if project_root.suffix == ".py" else []

        files: list[Path] = []
        for path in project_root.rglob("*.py"):
            try:
                relative = path.resolve().relative_to(project_root)
            except ValueError:
                continue
            if any(part in self.exclude_dirs for part in relative.parts):
                continue
            files.append(relative)
        return sorted(files, key=lambda item: item.as_posix())
