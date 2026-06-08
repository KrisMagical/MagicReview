"""FastAPI project detection."""

from __future__ import annotations

import ast
from pathlib import Path

from app.project.scanner import ProjectScanner
from app.analyzers.fastapi.utils import ROUTE_METHODS, call_name


class FastAPIDetector:
    """Detect whether a project or file uses FastAPI."""

    def __init__(self, scanner: ProjectScanner | None = None) -> None:
        self.scanner = scanner or ProjectScanner()

    def is_fastapi_project(self, root: str | Path) -> bool:
        project_root = Path(root).resolve()
        for relative_path in self.scanner.scan(project_root):
            try:
                source = (project_root / relative_path).read_text(encoding="utf-8")
            except OSError:
                continue
            if self.is_fastapi_source(source):
                return True
        return False

    def is_fastapi_source(self, source: str) -> bool:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "fastapi" or alias.name.startswith("fastapi.") for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "fastapi" or (node.module or "").startswith("fastapi."):
                    return True
            elif isinstance(node, ast.Call):
                name = call_name(node.func)
                if name in {"FastAPI", "fastapi.FastAPI", "APIRouter", "fastapi.APIRouter"}:
                    return True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr in ROUTE_METHODS:
                            return True
        return False
