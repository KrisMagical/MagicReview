"""Rule for detecting unchecked list indexing."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, RuleContext, make_issue


class IndexRiskRule(BaseRule):
    """Detect subscript access without a nearby length or truthiness guard."""

    name = "IndexRiskRule"
    category = "bug"

    def check(self, context: RuleContext) -> list[Issue]:
        if context.tree is None:
            return []
        guarded = self._guarded_sequences(context.tree)
        issues: list[Issue] = []
        for node in ast.walk(context.tree):
            if not isinstance(node, ast.Subscript) or not isinstance(node.value, ast.Name):
                continue
            if isinstance(node.ctx, ast.Store):
                continue
            if self._is_annotation(node):
                continue
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                continue
            if node.value.id.lower() in {"data", "dict", "mapping", "payload", "params"}:
                continue
            if node.value.id in guarded:
                continue
            issues.append(
                make_issue(
                    severity="medium",
                    issue_type=self.name,
                    file_path=context.file_path,
                    line=getattr(node, "lineno", 1),
                    message="Potential IndexError.",
                    suggestion="Check the sequence length before indexing it.",
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

    @staticmethod
    def _guarded_sequences(tree: ast.AST) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                for test_node in ast.walk(node.test):
                    if isinstance(test_node, ast.Call) and isinstance(test_node.func, ast.Name) and test_node.func.id == "len":
                        if test_node.args and isinstance(test_node.args[0], ast.Name):
                            names.add(test_node.args[0].id)
                    elif isinstance(test_node, ast.Name):
                        names.add(test_node.id)
        return names
