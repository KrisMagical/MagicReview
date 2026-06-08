"""Project import graph analyzer."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.models.issue import Issue
from app.project.scanner import ProjectScanner

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    file_path: Path
    display_path: str


class DependencyAnalyzer:
    """Build a directed graph for internal imports and detect graph risks."""

    def __init__(
        self,
        project_root: str | Path = ".",
        *,
        outgoing_threshold: int = 10,
        incoming_threshold: int = 15,
        total_degree_high_threshold: int = 20,
        emit_unavailable_issue: bool = False,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.outgoing_threshold = outgoing_threshold
        self.incoming_threshold = incoming_threshold
        self.total_degree_high_threshold = total_degree_high_threshold
        self.emit_unavailable_issue = emit_unavailable_issue
        self.modules = self._discover_modules()

    def analyze_project(self) -> list[Issue]:
        if nx is None:
            return self._unavailable_issue()
        graph = self.build_graph()
        return [*self.detect_cycles(graph), *self.detect_high_coupling(graph)]

    def build_graph(self):
        if nx is None:
            return None
        graph = nx.DiGraph()
        for module in self.modules.values():
            graph.add_node(module.name, file=module.display_path, path=module.file_path)

        for module in self.modules.values():
            try:
                source = module.file_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=module.display_path)
            except (OSError, SyntaxError):
                continue
            for imported_module in self._iter_local_imports(tree, module.name):
                if imported_module in self.modules:
                    graph.add_edge(module.name, imported_module)
        return graph

    def detect_cycles(self, graph) -> list[Issue]:
        if nx is None or graph is None:
            return self._unavailable_issue()
        issues: list[Issue] = []
        seen: set[tuple[str, ...]] = set()
        for cycle in nx.simple_cycles(graph):
            if len(cycle) < 2:
                continue
            canonical = self._canonical_cycle(cycle)
            if canonical in seen:
                continue
            seen.add(canonical)
            cycle_path = [*cycle, cycle[0]]
            first = cycle[0]
            issues.append(
                Issue(
                    severity="high",
                    type="CircularDependency",
                    file=str(graph.nodes[first].get("file", first)),
                    line=1,
                    message=f"Circular dependency detected: {' -> '.join(cycle_path)}",
                    suggestion="Break the cycle by extracting shared abstractions or moving dependencies to a lower-level module.",
                )
            )
        return issues

    def detect_high_coupling(self, graph) -> list[Issue]:
        if nx is None or graph is None:
            return self._unavailable_issue()
        issues: list[Issue] = []
        for module_name in graph.nodes:
            outgoing = int(graph.out_degree(module_name))
            incoming = int(graph.in_degree(module_name))
            total = incoming + outgoing
            if outgoing < self.outgoing_threshold and incoming < self.incoming_threshold and total < self.total_degree_high_threshold:
                continue
            severity = "high" if total >= self.total_degree_high_threshold else "medium"
            issues.append(
                Issue(
                    severity=severity,
                    type="HighModuleCoupling",
                    file=str(graph.nodes[module_name].get("file", module_name)),
                    line=1,
                    message="Module has high coupling with many incoming or outgoing dependencies.",
                    suggestion="Consider splitting responsibilities or introducing clearer module boundaries.",
                )
            )
        return issues

    def fan_in_by_file(self, graph=None) -> dict[str, int]:
        active_graph = graph if graph is not None else self.build_graph()
        if active_graph is None:
            return {}
        return {
            str(active_graph.nodes[module].get("file", module)): int(active_graph.in_degree(module))
            for module in active_graph.nodes
        }

    def _discover_modules(self) -> dict[str, ModuleInfo]:
        modules: dict[str, ModuleInfo] = {}
        for relative_path in ProjectScanner().scan(self.project_root):
            absolute_path = self.project_root / relative_path
            module_name = self._module_name_for_relative_path(relative_path)
            if module_name:
                modules[module_name] = ModuleInfo(module_name, absolute_path, relative_path.as_posix())
        return modules

    def _iter_local_imports(self, tree: ast.Module, current_module: str) -> Iterable[str]:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_absolute_import(alias.name)
                    if resolved is not None:
                        yield resolved
            elif isinstance(node, ast.ImportFrom):
                base = self._resolve_from_import(current_module, node.module, node.level)
                candidates = [base] if base else []
                if base:
                    candidates.extend(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
                for candidate in candidates:
                    resolved = self._resolve_absolute_import(candidate)
                    if resolved is not None:
                        yield resolved

    def _resolve_absolute_import(self, module_name: str | None) -> str | None:
        if not module_name:
            return None
        parts = module_name.split(".")
        for length in range(len(parts), 0, -1):
            candidate = ".".join(parts[:length])
            if candidate in self.modules:
                return candidate
        return None

    @staticmethod
    def _resolve_from_import(current_module: str, module: str | None, level: int) -> str | None:
        if level <= 0:
            return module
        package_parts = current_module.split(".")[:-1]
        base_parts = package_parts[: max(0, len(package_parts) - level + 1)]
        if module:
            base_parts.extend(module.split("."))
        return ".".join(part for part in base_parts if part)

    @staticmethod
    def _module_name_for_relative_path(path: Path) -> str:
        parts = list(path.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)

    @staticmethod
    def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
        rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
        reversed_cycle = list(reversed(cycle))
        rotations.extend(tuple(reversed_cycle[index:] + reversed_cycle[:index]) for index in range(len(reversed_cycle)))
        return min(rotations)

    def _unavailable_issue(self) -> list[Issue]:
        if not self.emit_unavailable_issue:
            return []
        return [
            Issue(
                severity="low",
                type="AnalyzerUnavailable",
                file="<project>",
                line=1,
                message="networkx is not available.",
                suggestion="Install networkx to enable import graph analysis.",
            )
        ]
