"""FastAPI project analyzer facade."""

from __future__ import annotations

import ast
from pathlib import Path

from app.analyzers.fastapi.dependency_analyzer import FastAPIDependencyAnalyzer
from app.analyzers.fastapi.detector import FastAPIDetector
from app.analyzers.fastapi.pydantic_analyzer import PydanticModelAnalyzer
from app.analyzers.fastapi.route_analyzer import FastAPIRouteAnalyzer
from app.models.issue import Issue
from app.project.scanner import ProjectScanner


class FastAPIProjectAnalyzer:
    """Run FastAPI-specific analyzers only for FastAPI projects."""

    def __init__(
        self,
        *,
        scanner: ProjectScanner | None = None,
        detector: FastAPIDetector | None = None,
        route_analyzer: FastAPIRouteAnalyzer | None = None,
        pydantic_analyzer: PydanticModelAnalyzer | None = None,
        dependency_analyzer: FastAPIDependencyAnalyzer | None = None,
    ) -> None:
        self.scanner = scanner or ProjectScanner()
        self.detector = detector or FastAPIDetector(self.scanner)
        self.route_analyzer = route_analyzer or FastAPIRouteAnalyzer()
        self.pydantic_analyzer = pydantic_analyzer or PydanticModelAnalyzer()
        self.dependency_analyzer = dependency_analyzer or FastAPIDependencyAnalyzer()

    def analyze_project(self, root: str | Path) -> list[Issue]:
        project_root = Path(root).resolve()
        if not self.detector.is_fastapi_project(project_root):
            return []

        issues: list[Issue] = []
        for relative_path in self.scanner.scan(project_root):
            absolute_path = project_root / relative_path
            try:
                source = absolute_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative_path.as_posix())
            except (OSError, SyntaxError):
                continue
            file_path = relative_path.as_posix()
            issues.extend(self.route_analyzer.analyze_tree(tree, file_path))
            issues.extend(self.pydantic_analyzer.analyze_tree(tree, file_path))
            issues.extend(self.dependency_analyzer.analyze_tree(tree, file_path))
        return issues
