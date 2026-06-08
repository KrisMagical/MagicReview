"""Rule for detecting numeric literals that should be named constants."""

from __future__ import annotations

import ast
from numbers import Number

from app.rules.base import BaseRule, Issue, make_issue


class MagicNumberRule(BaseRule):
    """Detect suspicious numeric literals in executable expressions."""

    name = "MagicNumberRule"
    category = "quality"
    allowed_values = {-1, 0, 1, 2}

    def match(self, node: ast.AST, file_path: str, source_code: str) -> list[Issue]:
        if not isinstance(node, ast.Constant) or not self._is_number(node.value):
            return []

        numeric_value = self._numeric_value(node)
        if numeric_value in self.allowed_values:
            return []
        if self._is_named_constant_definition(node):
            return []
        if self._is_line_number_keyword(node) or self._is_simple_index(node):
            return []
        if not self._is_expression_context(node):
            return []

        return [
            make_issue(
                severity="low",
                issue_type=self.name,
                file_path=file_path,
                line=getattr(node, "lineno", 1),
                message="Magic number detected.",
                suggestion="Extract the number into a named constant that explains its meaning.",
            )
        ]

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, Number) and not isinstance(value, bool)

    @classmethod
    def _numeric_value(cls, node: ast.Constant) -> Number:
        parent = getattr(node, "_parent", None)
        if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.USub) and cls._is_number(node.value):
            return -node.value
        return node.value

    @staticmethod
    def _is_named_constant_definition(node: ast.AST) -> bool:
        parent = getattr(node, "_parent", None)
        if isinstance(parent, ast.UnaryOp):
            parent = getattr(parent, "_parent", None)
        if isinstance(parent, ast.Assign):
            return any(isinstance(target, ast.Name) and target.id.isupper() for target in parent.targets)
        if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
            return parent.target.id.isupper()
        return False

    @staticmethod
    def _is_line_number_keyword(node: ast.AST) -> bool:
        parent = getattr(node, "_parent", None)
        return isinstance(parent, ast.keyword) and parent.arg in {"line", "lineno", "line_no", "line_number"}

    @staticmethod
    def _is_simple_index(node: ast.AST) -> bool:
        parent = getattr(node, "_parent", None)
        return isinstance(parent, ast.Subscript) and parent.slice is node

    @staticmethod
    def _is_expression_context(node: ast.AST) -> bool:
        parent = getattr(node, "_parent", None)
        if isinstance(parent, ast.UnaryOp):
            parent = getattr(parent, "_parent", None)
        return isinstance(
            parent,
            (
                ast.BinOp,
                ast.Compare,
                ast.If,
                ast.IfExp,
                ast.Return,
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
                ast.Call,
            ),
        )
