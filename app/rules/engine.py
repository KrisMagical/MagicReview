"""Rule registration, execution, deduplication, and stable ordering."""

from __future__ import annotations

import ast
from collections.abc import Iterable

from app.models.issue import Issue
from app.rules.base import Rule, RuleContext
from app.rules.bug import (
    FileLeakRule,
    IndexRiskRule,
    KeyErrorRule,
    NoneRiskRule,
    PathTraversalRule,
    SQLInjectionRule,
    ZeroDivisionRule,
)
from app.rules.quality import FunctionTooLongRule, MagicNumberRule, TooManyParametersRule, TypeHintRule


def default_phase1_rules() -> list[Rule]:
    """Return the complete Phase 1 static rule set."""

    return [
        FunctionTooLongRule(),
        TooManyParametersRule(),
        TypeHintRule(),
        MagicNumberRule(),
        NoneRiskRule(),
        IndexRiskRule(),
        KeyErrorRule(),
        ZeroDivisionRule(),
        FileLeakRule(),
        SQLInjectionRule(),
        PathTraversalRule(),
    ]


class RuleEngine:
    """Execute registered rules and return stable de-duplicated issues."""

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def __init__(self, rules: Iterable[Rule] | None = None) -> None:
        self.rules: list[Rule] = []
        for rule in rules if rules is not None else default_phase1_rules():
            self.register(rule)

    def register(self, rule: Rule) -> None:
        self.rules.append(rule)

    def run(self, context: RuleContext) -> list[Issue]:
        issues: list[Issue] = []
        for rule in self.rules:
            issues.extend(rule.check(context))
        if context.changed_lines:
            issues = [issue for issue in issues if issue.line in context.changed_lines]
        return self._dedupe_and_sort(issues)

    def review_source(
        self,
        *,
        file_path: str,
        source_code: str,
        changed_lines: set[int] | None = None,
    ) -> list[Issue]:
        tree = self._parse(file_path, source_code)
        if tree is None:
            return []
        self._attach_parent_links(tree)
        context = RuleContext(
            file_path=file_path,
            source_code=source_code,
            tree=tree,
            changed_lines=changed_lines,
            lines=source_code.splitlines(),
        )
        return self.run(context)

    @staticmethod
    def _parse(file_path: str, source_code: str) -> ast.AST | None:
        try:
            return ast.parse(source_code, filename=file_path)
        except SyntaxError:
            return None

    @staticmethod
    def _attach_parent_links(tree: ast.AST) -> None:
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                setattr(child, "_parent", parent)

    @classmethod
    def _dedupe_and_sort(cls, issues: Iterable[Issue]) -> list[Issue]:
        unique: dict[tuple[str, int, str, str], Issue] = {}
        for issue in issues:
            key = (issue.file, issue.line, issue.type, issue.message)
            existing = unique.get(key)
            if existing is None or cls.severity_order[issue.severity] < cls.severity_order[existing.severity]:
                unique[key] = issue
        return sorted(
            unique.values(),
            key=lambda issue: (cls.severity_order[issue.severity], issue.file, issue.line, issue.type, issue.message),
        )
