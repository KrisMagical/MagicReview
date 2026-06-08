"""Rule for detecting unmanaged file descriptors."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, RuleContext, make_issue


class FileLeakRule(BaseRule):
    """Detect open() calls that are not owned by a context manager or closed."""

    name = "FileLeakRule"
    category = "bug"

    def check(self, context: RuleContext) -> list[Issue]:
        if context.tree is None:
            return []
        closed_names = self._closed_file_names(context.tree)
        issues: list[Issue] = []
        for node in ast.walk(context.tree):
            if not isinstance(node, ast.Call) or not self._is_open_call(node):
                continue
            if self._is_context_manager_open(node):
                continue
            assigned_name = self._assigned_name(node)
            if assigned_name and assigned_name in closed_names:
                continue
            issues.append(
                make_issue(
                    severity="medium",
                    issue_type=self.name,
                    file_path=context.file_path,
                    line=getattr(node, "lineno", 1),
                    message="File opened without guaranteed close.",
                    suggestion="Prefer using a with statement to ensure the file is closed.",
                )
            )
        return issues

    @staticmethod
    def _is_open_call(node: ast.Call) -> bool:
        return isinstance(node.func, ast.Name) and node.func.id == "open"

    @staticmethod
    def _is_context_manager_open(node: ast.Call) -> bool:
        parent = getattr(node, "_parent", None)
        return isinstance(parent, ast.withitem) and parent.context_expr is node

    @staticmethod
    def _assigned_name(node: ast.Call) -> str | None:
        parent = getattr(node, "_parent", None)
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
            return parent.targets[0].id
        if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
            return parent.target.id
        return None

    @staticmethod
    def _closed_file_names(tree: ast.AST) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "close":
                if isinstance(node.func.value, ast.Name):
                    names.add(node.func.value.id)
        return names
