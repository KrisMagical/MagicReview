"""Project review pipeline for Phase 2 static analysis."""

from __future__ import annotations

from pathlib import Path

from app.analyzers.complexity_analyzer import RadonAdapter
from app.analyzers.dependency_analyzer import DependencyAnalyzer
from app.analyzers.fastapi import FastAPIProjectAnalyzer
from app.analyzers.ruff_adapter import RuffAdapter
from app.models.issue import Issue
from app.project.scanner import ProjectScanner
from app.rules.architecture import GodObjectDetector
from app.rules.engine import RuleEngine


class ProjectReviewer:
    """Run Phase 1 and Phase 2 analyzers over a project."""

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def __init__(
        self,
        *,
        scanner: ProjectScanner | None = None,
        rule_engine: RuleEngine | None = None,
        ruff_adapter: RuffAdapter | None = None,
        radon_adapter: RadonAdapter | None = None,
        dependency_analyzer_cls: type[DependencyAnalyzer] = DependencyAnalyzer,
        god_detector_cls: type[GodObjectDetector] = GodObjectDetector,
        fastapi_analyzer: FastAPIProjectAnalyzer | None = None,
    ) -> None:
        self.scanner = scanner or ProjectScanner()
        self.rule_engine = rule_engine or RuleEngine()
        self.ruff_adapter = ruff_adapter
        self.radon_adapter = radon_adapter
        self.dependency_analyzer_cls = dependency_analyzer_cls
        self.god_detector_cls = god_detector_cls
        self.fastapi_analyzer = fastapi_analyzer or FastAPIProjectAnalyzer(scanner=self.scanner)

    def review(self, root: str | Path) -> list[Issue]:
        project_root = Path(root).resolve()
        issues: list[Issue] = []

        files = self.scanner.scan(project_root)
        for relative_path in files:
            absolute_path = project_root / relative_path
            display_path = relative_path.as_posix()
            try:
                source = absolute_path.read_text(encoding="utf-8")
            except OSError:
                issues.append(
                    Issue(
                        severity="low",
                        type="StaticAnalysisError",
                        file=display_path,
                        line=1,
                        message="Unable to read Python file.",
                        suggestion="Check file permissions and encoding.",
                    )
                )
                continue
            issues.extend(self.rule_engine.review_source(file_path=display_path, source_code=source))

        issues.extend(self._safe_run(lambda: (self.ruff_adapter or RuffAdapter(workspace_root=project_root)).check_project(project_root)))
        issues.extend(self._safe_run(lambda: (self.radon_adapter or RadonAdapter(workspace_root=project_root)).analyze_project(project_root)))

        dependency_analyzer = self.dependency_analyzer_cls(project_root)
        graph = dependency_analyzer.build_graph()
        issues.extend(self._safe_run(lambda: dependency_analyzer.detect_cycles(graph)))
        issues.extend(self._safe_run(lambda: dependency_analyzer.detect_high_coupling(graph)))
        issues.extend(self._safe_run(lambda: self.god_detector_cls(project_root).analyze_project(graph=graph)))
        issues.extend(self._safe_run(lambda: self.fastapi_analyzer.analyze_project(project_root)))

        return self._dedupe_and_sort(issues)

    @staticmethod
    def _safe_run(callback) -> list[Issue]:
        try:
            return list(callback())
        except Exception:
            return [
                Issue(
                    severity="low",
                    type="StaticAnalysisError",
                    file="<project>",
                    line=1,
                    message="A static analyzer failed.",
                    suggestion="Run the analyzer in debug mode or inspect project files for invalid input.",
                )
            ]

    @classmethod
    def _dedupe_and_sort(cls, issues: list[Issue]) -> list[Issue]:
        unique: dict[tuple[str, str, int, str], Issue] = {}
        for issue in issues:
            key = (issue.type, issue.file, issue.line, issue.message)
            existing = unique.get(key)
            if existing is None or cls.severity_order[issue.severity] < cls.severity_order[existing.severity]:
                unique[key] = issue
        return sorted(
            unique.values(),
            key=lambda issue: (cls.severity_order[issue.severity], issue.file, issue.line, issue.type),
        )
