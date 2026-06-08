"""Project architecture context builder for LLM review."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.analyzers.dependency_analyzer import DependencyAnalyzer
from app.analyzers.fastapi import FastAPIDetector
from app.analyzers.fastapi.utils import route_decorator, route_method
from app.models.issue import Issue
from app.project.scanner import ProjectScanner


@dataclass
class ArchitectureContext:
    project_root: str
    modules: list[str] = field(default_factory=list)
    files_summary: list[dict[str, Any]] = field(default_factory=list)
    classes_summary: list[dict[str, Any]] = field(default_factory=list)
    functions_summary: list[dict[str, Any]] = field(default_factory=list)
    routes_summary: list[dict[str, Any]] = field(default_factory=list)
    dependency_summary: dict[str, Any] = field(default_factory=dict)
    static_issues_summary: list[dict[str, Any]] = field(default_factory=list)
    complexity_summary: list[dict[str, Any]] = field(default_factory=list)
    god_object_summary: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False

    def to_prompt_text(self, max_chars: int = 60000) -> str:
        payload = {
            "project_root": self.project_root,
            "modules": self.modules,
            "files_summary": self.files_summary,
            "classes_summary": self.classes_summary,
            "functions_summary": self.functions_summary,
            "routes_summary": self.routes_summary,
            "dependency_summary": self.dependency_summary,
            "static_issues_summary": self.static_issues_summary,
            "complexity_summary": self.complexity_summary,
            "god_object_summary": self.god_object_summary,
            "truncated": self.truncated,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if len(text) <= max_chars:
            return text
        self.truncated = True
        payload["truncated"] = True
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return text[: max_chars - 200] + "\n...TRUNCATED...\n"


class ArchitectureContextBuilder:
    """Build a bounded, static-only project summary for LLM architecture review."""

    def __init__(self, *, scanner: ProjectScanner | None = None, max_context_chars: int = 60000, max_files: int = 2000) -> None:
        self.scanner = scanner or ProjectScanner()
        self.max_context_chars = max_context_chars
        self.max_files = max_files

    def build(self, project_root: str | Path, static_issues: list[Issue] | None = None) -> ArchitectureContext:
        root = Path(project_root).resolve()
        files = self.scanner.scan(root)[: self.max_files]
        context = ArchitectureContext(project_root=str(root))
        detector = FastAPIDetector(self.scanner)

        for relative_path in files:
            absolute_path = root / relative_path
            try:
                source = absolute_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative_path.as_posix())
            except (OSError, SyntaxError):
                continue

            module_name = ".".join(relative_path.with_suffix("").parts)
            context.modules.append(module_name)
            context.files_summary.append(
                {
                    "file": relative_path.as_posix(),
                    "lines": len(source.splitlines()),
                    "is_fastapi": detector.is_fastapi_source(source),
                    "signals": self._file_signals(relative_path.as_posix()),
                }
            )
            self._collect_symbols(tree, relative_path.as_posix(), context)

        context.dependency_summary = self._dependency_summary(root)
        context.static_issues_summary = self._summarize_issues(static_issues or [])
        context.complexity_summary = [
            issue for issue in context.static_issues_summary if issue["type"] in {"CyclomaticComplexity", "MaintainabilityIndex"}
        ]
        context.god_object_summary = [
            issue for issue in context.static_issues_summary if issue["type"] in {"GodFile", "GodClass", "LargeModuleResponsibility"}
        ]
        if len(context.to_prompt_text(self.max_context_chars)) >= self.max_context_chars:
            context.truncated = True
        return context

    def _collect_symbols(self, tree: ast.AST, file_path: str, context: ArchitectureContext) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
                context.classes_summary.append({"file": file_path, "line": node.lineno, "name": node.name, "methods": methods[:20]})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                context.functions_summary.append(
                    {
                        "file": file_path,
                        "line": node.lineno,
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "lines": getattr(node, "end_lineno", node.lineno) - node.lineno + 1,
                    }
                )
                decorator = route_decorator(node)
                if decorator is not None:
                    context.routes_summary.append(
                        {
                            "file": file_path,
                            "line": node.lineno,
                            "function": node.name,
                            "method": route_method(decorator),
                            "has_response_model": any(keyword.arg == "response_model" for keyword in decorator.keywords),
                        }
                    )

    @staticmethod
    def _file_signals(file_path: str) -> list[str]:
        lowered = file_path.lower()
        return [signal for signal in ("api", "router", "controller", "service", "repository", "model") if signal in lowered]

    @staticmethod
    def _dependency_summary(root: Path) -> dict[str, Any]:
        try:
            analyzer = DependencyAnalyzer(root)
            graph = analyzer.build_graph()
            if graph is None:
                return {}
            return {
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "high_fan_out": [
                    {"module": module, "out_degree": int(graph.out_degree(module))}
                    for module in graph.nodes
                    if int(graph.out_degree(module)) >= 5
                ][:20],
            }
        except Exception:
            return {}

    @staticmethod
    def _summarize_issues(issues: list[Issue]) -> list[dict[str, Any]]:
        return [
            {
                "severity": issue.severity,
                "type": issue.type,
                "file": issue.file,
                "line": issue.line,
                "message": issue.message[:240],
            }
            for issue in issues[:200]
        ]
