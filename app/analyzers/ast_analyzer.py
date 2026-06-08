"""AST analyzer adapter for Phase 1 rule execution."""

from __future__ import annotations

import ast
from collections.abc import Iterable

from app.models.issue import Issue, make_issue
from app.rules.base import Rule
from app.rules.engine import RuleEngine
from app.rules.quality import MagicNumberRule


class ASTAnalyzer:
    """Parse Python source code and dispatch it through the rule engine."""

    def __init__(self, rules: Iterable[Rule] | None = None) -> None:
        self.engine = RuleEngine(rules=rules)

    def analyze_file(self, file_path: str, source_code: str) -> list[Issue]:
        try:
            ast.parse(source_code, filename=file_path)
        except SyntaxError as exc:
            return [
                make_issue(
                    severity="critical",
                    issue_type="SyntaxError",
                    file_path=file_path,
                    line=exc.lineno,
                    message=f"Syntax error: {exc.msg}",
                    suggestion="Fix the Python syntax error before running static review.",
                )
            ]
        return self.engine.review_source(file_path=file_path, source_code=source_code)


class MagicNumberAnalyzer:
    """Compatibility wrapper for the previous single-rule analyzer."""

    def __init__(self) -> None:
        self._analyzer = ASTAnalyzer(rules=[MagicNumberRule()])

    def analyze_file(self, file_path: str, file_content: str) -> list[Issue]:
        return self._analyzer.analyze_file(file_path, file_content)
