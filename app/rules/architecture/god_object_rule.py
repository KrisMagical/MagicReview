"""God Object, God Class, and large module responsibility detection."""

from __future__ import annotations

import ast
from pathlib import Path

from app.models.issue import Issue
from app.project.scanner import ProjectScanner


class GodObjectDetector:
    """Detect oversized files and classes using static AST metrics."""

    def __init__(
        self,
        project_root: str | Path = ".",
        *,
        god_file_max_lines: int = 800,
        god_file_max_functions: int = 30,
        god_file_max_classes: int = 15,
        god_class_max_methods: int = 20,
        god_class_max_attributes: int = 30,
        god_class_max_lines: int = 500,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.god_file_max_lines = god_file_max_lines
        self.god_file_max_functions = god_file_max_functions
        self.god_file_max_classes = god_file_max_classes
        self.god_class_max_methods = god_class_max_methods
        self.god_class_max_attributes = god_class_max_attributes
        self.god_class_max_lines = god_class_max_lines

    def analyze_project(self, **_kwargs: object) -> list[Issue]:
        issues: list[Issue] = []
        for relative_path in ProjectScanner().scan(self.project_root):
            absolute_path = self.project_root / relative_path
            try:
                source = absolute_path.read_text(encoding="utf-8")
            except OSError:
                continue
            issues.extend(self.analyze_file(relative_path.as_posix(), source))
        return issues

    def analyze_file(self, file_path: str, source_code: str, *, fan_in: int = 0) -> list[Issue]:
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError:
            return []

        issues: list[Issue] = []
        line_count = len(source_code.splitlines())
        module_functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        module_classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        global_statements = [
            node
            for node in tree.body
            if not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]

        if (
            line_count >= self.god_file_max_lines
            or len(module_functions) >= self.god_file_max_functions
            or len(module_classes) >= self.god_file_max_classes
        ):
            issues.append(
                Issue(
                    severity="high",
                    type="GodFile",
                    file=file_path,
                    line=1,
                    message="File appears to have too many responsibilities.",
                    suggestion="Split this file into smaller modules with focused responsibilities.",
                )
            )

        if len(module_functions) >= 10 and len(module_classes) >= 3 and len(global_statements) >= 10:
            issues.append(
                Issue(
                    severity="medium",
                    type="LargeModuleResponsibility",
                    file=file_path,
                    line=1,
                    message="Module mixes many functions, classes, and global statements.",
                    suggestion="Consider splitting this module by responsibility.",
                )
            )

        for class_node in module_classes:
            class_issue = self._class_issue(file_path, class_node)
            if class_issue is not None:
                issues.append(class_issue)
        return issues

    def _class_issue(self, file_path: str, class_node: ast.ClassDef) -> Issue | None:
        methods = [
            node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        attributes = self._class_attribute_count(class_node)
        end_lineno = getattr(class_node, "end_lineno", class_node.lineno)
        line_count = end_lineno - class_node.lineno + 1
        if (
            len(methods) < self.god_class_max_methods
            and attributes < self.god_class_max_attributes
            and line_count < self.god_class_max_lines
        ):
            return None
        severity = "high" if line_count >= self.god_class_max_lines or len(methods) >= self.god_class_max_methods else "medium"
        return Issue(
            severity=severity,
            type="GodClass",
            file=file_path,
            line=class_node.lineno,
            message="Class appears to have too many responsibilities.",
            suggestion="Split this class into smaller classes with focused responsibilities.",
        )

    @staticmethod
    def _class_attribute_count(class_node: ast.ClassDef) -> int:
        attributes: set[str] = set()
        for node in ast.walk(class_node):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                attributes.add(node.target.id)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        attributes.add(target.id)
                    elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                        attributes.add(target.attr)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
                if isinstance(node.ctx, ast.Store):
                    attributes.add(node.attr)
        return len(attributes)


GodObjectRule = GodObjectDetector
