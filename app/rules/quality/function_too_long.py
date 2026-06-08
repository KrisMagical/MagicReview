"""Rule for detecting functions with excessive line span."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, make_issue


class FunctionTooLongRule(BaseRule):
    """Detect functions longer than the configured threshold."""

    name = "FunctionTooLongRule"
    category = "quality"

    def __init__(self, max_lines: int = 80) -> None:
        self.max_lines = max_lines

    def match(self, node: ast.AST, file_path: str, source_code: str) -> list[Issue]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return []

        end_lineno = getattr(node, "end_lineno", node.lineno)
        if end_lineno - node.lineno + 1 <= self.max_lines:
            return []

        return [
            make_issue(
                severity="medium",
                issue_type=self.name,
                file_path=file_path,
                line=node.lineno,
                message="Function is too long.",
                suggestion="Consider splitting this function into smaller functions with single responsibilities.",
            )
        ]
