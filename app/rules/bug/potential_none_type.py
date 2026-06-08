"""Rule for detecting likely NoneType access after dict.get calls."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, RuleContext, make_issue


class NoneRiskRule(BaseRule):
    """Detect variables assigned from .get(...) and used without a None guard."""

    name = "NoneRiskRule"
    category = "bug"

    def check(self, context: RuleContext) -> list[Issue]:
        if context.tree is None:
            return []
        issues: list[Issue] = []
        for body in self._iter_bodies(context.tree):
            issues.extend(self._scan_body(body, context.file_path))
        return issues

    def _scan_body(self, body: list[ast.stmt], file_path: str) -> list[Issue]:
        maybe_none: dict[str, int] = {}
        checked: set[str] = set()
        issues: list[Issue] = []
        reported: set[tuple[str, int]] = set()

        for statement in body:
            checked.update(self._guarded_names(statement))
            for access in ast.walk(statement):
                name = self._unguarded_access_name(access)
                if not name or name not in maybe_none or name in checked:
                    continue
                key = (name, getattr(access, "lineno", maybe_none[name]))
                if key in reported:
                    continue
                reported.add(key)
                issues.append(
                    make_issue(
                        severity="medium",
                        issue_type=self.name,
                        file_path=file_path,
                        line=getattr(access, "lineno", maybe_none[name]),
                        message="Potential NoneType error.",
                        suggestion="Check the value for None before using attributes or indexes from a .get(...) result.",
                    )
                )

            assigned = self._get_assigned_from_get(statement)
            for name in self._assigned_names(statement):
                if name in assigned:
                    maybe_none[name] = getattr(statement, "lineno", 1)
                    checked.discard(name)
                else:
                    maybe_none.pop(name, None)
                    checked.discard(name)

        return issues

    @staticmethod
    def _iter_bodies(tree: ast.AST) -> list[list[ast.stmt]]:
        bodies: list[list[ast.stmt]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
                bodies.append(node.body)
        return bodies

    @staticmethod
    def _get_assigned_from_get(statement: ast.stmt) -> set[str]:
        result: set[str] = set()
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
            if isinstance(statement.value.func, ast.Attribute) and statement.value.func.attr == "get":
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        result.add(target.id)
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            value = statement.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "get":
                result.add(statement.target.id)
        return result

    @staticmethod
    def _assigned_names(statement: ast.stmt) -> set[str]:
        targets: list[ast.AST] = []
        if isinstance(statement, ast.Assign):
            targets.extend(statement.targets)
        elif isinstance(statement, ast.AnnAssign):
            targets.append(statement.target)
        elif isinstance(statement, ast.AugAssign):
            targets.append(statement.target)
        return {node.id for target in targets for node in ast.walk(target) if isinstance(node, ast.Name)}

    @staticmethod
    def _guarded_names(statement: ast.stmt) -> set[str]:
        tests: list[ast.AST] = []
        if isinstance(statement, ast.If):
            tests.append(statement.test)
        elif isinstance(statement, ast.Assert):
            tests.append(statement.test)
        names: set[str] = set()
        for test in tests:
            for node in ast.walk(test):
                if isinstance(node, ast.Compare):
                    if (
                        isinstance(node.left, ast.Name)
                        and any(isinstance(op, (ast.IsNot, ast.NotEq)) for op in node.ops)
                        and any(isinstance(comp, ast.Constant) and comp.value is None for comp in node.comparators)
                    ):
                        names.add(node.left.id)
                elif isinstance(node, ast.Name):
                    names.add(node.id)
        return names

    @staticmethod
    def _unguarded_access_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return node.value.id
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            return node.value.id
        return None


PotentialNoneTypeRule = NoneRiskRule
