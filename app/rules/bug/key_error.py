"""Rule for detecting unchecked dictionary key access."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, RuleContext, make_issue


class KeyErrorRule(BaseRule):
    """Detect dict[key] access without get, membership check, or KeyError handling."""

    name = "KeyErrorRule"
    category = "bug"

    def check(self, context: RuleContext) -> list[Issue]:
        if context.tree is None:
            return []
        guarded = self._guarded_pairs(context.tree)
        in_keyerror_try = self._subscripts_inside_keyerror_try(context.tree)
        issues: list[Issue] = []
        for node in ast.walk(context.tree):
            if not isinstance(node, ast.Subscript) or not isinstance(node.value, ast.Name):
                continue
            if isinstance(node.ctx, ast.Store) or id(node) in in_keyerror_try:
                continue
            if self._is_annotation(node):
                continue
            key = self._key_repr(node.slice)
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                continue
            if node.value.id.lower() in {"items", "list", "arr", "array", "seq", "sequence"}:
                continue
            if (node.value.id, key) in guarded or (node.value.id, None) in guarded:
                continue
            issues.append(
                make_issue(
                    severity="medium",
                    issue_type=self.name,
                    file_path=context.file_path,
                    line=getattr(node, "lineno", 1),
                    message="Potential KeyError.",
                    suggestion="Use dict.get(...), check key membership, or handle KeyError explicitly.",
                )
            )
        return issues

    @staticmethod
    def _is_annotation(node: ast.AST) -> bool:
        current: ast.AST | None = node
        parent = getattr(current, "_parent", None)
        while parent is not None:
            if isinstance(parent, ast.arg) and parent.annotation is current:
                return True
            if isinstance(parent, ast.AnnAssign) and parent.annotation is current:
                return True
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and parent.returns is current:
                return True
            current = parent
            parent = getattr(current, "_parent", None)
        return False

    @classmethod
    def _guarded_pairs(cls, tree: ast.AST) -> set[tuple[str, str | None]]:
        guarded: set[tuple[str, str | None]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.In):
                    if isinstance(node.comparators[0], ast.Name):
                        guarded.add((node.comparators[0].id, cls._key_repr(node.left)))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and isinstance(node.func.value, ast.Name):
                    guarded.add((node.func.value.id, cls._key_repr(node.args[0]) if node.args else None))
        return guarded

    @staticmethod
    def _subscripts_inside_keyerror_try(tree: ast.AST) -> set[int]:
        result: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            handles_keyerror = any(
                handler.type is None
                or (isinstance(handler.type, ast.Name) and handler.type.id == "KeyError")
                for handler in node.handlers
            )
            if handles_keyerror:
                result.update(id(child) for stmt in node.body for child in ast.walk(stmt) if isinstance(child, ast.Subscript))
        return result

    @staticmethod
    def _key_repr(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Name):
            return node.id
        return None
