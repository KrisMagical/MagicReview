"""Rule for detecting dynamically formatted SQL execution."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, make_issue


class SQLInjectionRule(BaseRule):
    """Detect string interpolation inside database query calls."""

    name = "SQLInjectionRule"
    category = "security"
    sql_methods = {"execute", "executemany", "query", "raw"}

    def match(self, node: ast.AST, file_path: str, source_code: str) -> list[Issue]:
        if not isinstance(node, ast.Call):
            return []
        if not self._is_sql_call(node) or not node.args:
            return []
        if not self._is_dynamic_sql(node.args[0]):
            return []
        return [
            make_issue(
                severity="high",
                issue_type=self.name,
                file_path=file_path,
                line=getattr(node, "lineno", 1),
                message="SQL injection risk.",
                suggestion="Use parameterized queries instead of string interpolation.",
            )
        ]

    @classmethod
    def _is_sql_call(cls, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in cls.sql_methods
        if isinstance(node.func, ast.Name):
            return node.func.id in cls.sql_methods
        return False

    @classmethod
    def _is_dynamic_sql(cls, node: ast.AST) -> bool:
        if isinstance(node, ast.JoinedStr):
            return cls._looks_like_sql(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            return cls._looks_like_sql(node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            return cls._looks_like_sql(node)
        return False

    @staticmethod
    def _looks_like_sql(node: ast.AST) -> bool:
        try:
            text = ast.unparse(node).lower()
        except Exception:
            return True
        return any(token in text for token in ("select", "insert", "update", "delete", "where", "from"))
