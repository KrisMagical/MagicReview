"""Radon adapter for cyclomatic complexity and maintainability analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.issue import Issue
from app.project.scanner import ProjectScanner

try:
    from radon.metrics import mi_visit
    from radon.visitors import ComplexityVisitor
except ImportError:  # pragma: no cover - exercised with monkeypatch in tests
    mi_visit = None
    ComplexityVisitor = None


class RadonAdapter:
    """Analyze Python code with Radon and normalize results as Issues."""

    def __init__(
        self,
        *,
        workspace_root: str | Path | None = None,
        max_complexity_medium: int = 15,
        max_complexity_high: int = 25,
        min_maintainability_medium: float = 65.0,
        min_maintainability_high: float = 40.0,
        emit_unavailable_issue: bool = False,
    ) -> None:
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.max_complexity_medium = max_complexity_medium
        self.max_complexity_high = max_complexity_high
        self.min_maintainability_medium = min_maintainability_medium
        self.min_maintainability_high = min_maintainability_high
        self.emit_unavailable_issue = emit_unavailable_issue

    def analyze_file(self, file_path: str, file_content: str) -> list[Issue]:
        if ComplexityVisitor is None or mi_visit is None:
            return self._unavailable_issue()

        try:
            visitor = ComplexityVisitor.from_code(file_content)
        except SyntaxError as exc:
            return [
                Issue(
                    severity="medium",
                    type="ParseError",
                    file=file_path,
                    line=exc.lineno or 1,
                    message=f"Unable to parse Python file: {exc.msg}",
                    suggestion="Fix the syntax error so static analyzers can inspect this file.",
                )
            ]
        except Exception:
            return [
                Issue(
                    severity="low",
                    type="StaticAnalysisError",
                    file=file_path,
                    line=1,
                    message="Radon could not analyze this file.",
                    suggestion="Check whether the file contains valid Python source.",
                )
            ]

        issues: list[Issue] = []
        for block in self._iter_blocks(visitor):
            issue = self._complexity_issue(block, file_path)
            if issue is not None:
                issues.append(issue)

        mi_issue = self._maintainability_issue(file_path, file_content)
        if mi_issue is not None:
            issues.append(mi_issue)
        return issues

    def analyze_project(self, project_dir: str | Path = ".") -> list[Issue]:
        root = self._resolve_path(project_dir)
        issues: list[Issue] = []
        for relative_path in ProjectScanner().scan(root):
            absolute_path = root / relative_path
            try:
                source = absolute_path.read_text(encoding="utf-8")
            except OSError:
                issues.append(
                    Issue(
                        severity="low",
                        type="StaticAnalysisError",
                        file=relative_path.as_posix(),
                        line=1,
                        message="Unable to read Python file.",
                        suggestion="Check file permissions and encoding.",
                    )
                )
                continue
            issues.extend(self.analyze_file(relative_path.as_posix(), source))
        return issues

    def analyze_diff_files(self, diff_results: list[dict[str, Any]]) -> list[Issue]:
        issues: list[Issue] = []
        for diff_result in diff_results:
            file_path = diff_result.get("file") or diff_result.get("file_path") or diff_result.get("path")
            source = diff_result.get("source_code") or diff_result.get("content") or diff_result.get("file_content")
            if isinstance(file_path, str) and isinstance(source, str):
                issues.extend(self.analyze_file(file_path, source))
        return issues

    def get_function_line_map(self, file_content: str) -> dict[str, int]:
        if ComplexityVisitor is None:
            return {}
        try:
            visitor = ComplexityVisitor.from_code(file_content)
        except Exception:
            return {}
        return {
            str(getattr(block, "fullname", getattr(block, "name", ""))): int(getattr(block, "lineno", 1))
            for block in self._iter_blocks(visitor)
        }

    def _complexity_issue(self, block: object, file_path: str) -> Issue | None:
        complexity = int(getattr(block, "complexity", 0))
        if complexity < self.max_complexity_medium:
            return None
        severity = "high" if complexity >= self.max_complexity_high else "medium"
        return Issue(
            severity=severity,
            type="CyclomaticComplexity",
            file=file_path,
            line=int(getattr(block, "lineno", 1)),
            message="Function has high cyclomatic complexity.",
            suggestion="Consider splitting complex branches into smaller functions.",
        )

    def _maintainability_issue(self, file_path: str, source: str) -> Issue | None:
        if mi_visit is None:
            return None
        try:
            score = float(mi_visit(source, multi=True))
        except SyntaxError:
            return None
        except Exception:
            return None
        if score >= self.min_maintainability_medium:
            return None
        severity = "high" if score < self.min_maintainability_high else "medium"
        return Issue(
            severity=severity,
            type="MaintainabilityIndex",
            file=file_path,
            line=1,
            message="File has low maintainability index.",
            suggestion="Consider refactoring this file to improve maintainability.",
        )

    @staticmethod
    def _iter_blocks(visitor: object) -> list[object]:
        blocks: list[object] = []
        for function in getattr(visitor, "functions", []):
            RadonAdapter._collect_blocks(function, blocks)
        for class_block in getattr(visitor, "classes", []):
            for method in getattr(class_block, "methods", []):
                RadonAdapter._collect_blocks(method, blocks)
        return blocks

    @staticmethod
    def _collect_blocks(block: object, blocks: list[object]) -> None:
        blocks.append(block)
        for closure in getattr(block, "closures", []):
            RadonAdapter._collect_blocks(closure, blocks)

    def _unavailable_issue(self) -> list[Issue]:
        if not self.emit_unavailable_issue:
            return []
        return [
            Issue(
                severity="low",
                type="AnalyzerUnavailable",
                file="<project>",
                line=1,
                message="Radon is not available.",
                suggestion="Install radon to enable complexity and maintainability checks.",
            )
        ]

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else (self.workspace_root / candidate).resolve()


ComplexityAnalyzer = RadonAdapter
