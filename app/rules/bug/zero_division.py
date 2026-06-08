"""Rule for detecting potential ZeroDivisionError."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, RuleContext, make_issue


class ZeroDivisionRule(BaseRule):
    """Detect division, floor division, and modulo by unsafe denominators."""

    name = "ZeroDivisionRule"
    category = "bug"

    def check(self, context: RuleContext) -> list[Issue]:
        if context.tree is None:
            return []
        guarded = self._non_zero_guarded_names(context.tree)
        issues: list[Issue] = []
        for node in ast.walk(context.tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                continue
            denominator = node.right
            if isinstance(denominator, ast.Constant) and denominator.value == 0:
                issues.append(
                    make_issue(
                        severity="high",
                        issue_type=self.name,
                        file_path=context.file_path,
                        line=getattr(node, "lineno", 1),
                        message="Division by zero.",
                        suggestion="Replace the zero denominator or guard this operation before executing it.",
                    )
                )
                continue
            if isinstance(denominator, ast.Name) and denominator.id not in guarded:
                issues.append(
                    make_issue(
                        severity="medium",
                        issue_type=self.name,
                        file_path=context.file_path,
                        line=getattr(node, "lineno", 1),
                        message="Potential ZeroDivisionError.",
                        suggestion="Check that the denominator is not zero before dividing.",
                    )
                )
        return issues

    @staticmethod
    def _non_zero_guarded_names(tree: ast.AST) -> set[str]:
        guarded: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            for test in ast.walk(node.test):
                if not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Name):
                    continue
                has_zero = any(isinstance(comp, ast.Constant) and comp.value == 0 for comp in test.comparators)
                if has_zero and any(isinstance(op, ast.NotEq) for op in test.ops):
                    guarded.add(test.left.id)
        return guarded
