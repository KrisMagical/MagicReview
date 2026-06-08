"""Rule for detecting functions with too many parameters."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, make_issue


class TooManyParametersRule(BaseRule):
    """Detect functions whose parameter count exceeds the threshold."""

    name = "TooManyParametersRule"
    category = "quality"
    ignored_names = {"self", "cls"}

    def __init__(self, max_params: int = 5) -> None:
        self.max_params = max_params

    def match(self, node: ast.AST, file_path: str, source_code: str) -> list[Issue]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return []

        params = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        params.extend(arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None)
        params = [param for param in params if param.arg not in self.ignored_names]
        if len(params) <= self.max_params:
            return []

        return [
            make_issue(
                severity="medium",
                issue_type=self.name,
                file_path=file_path,
                line=node.lineno,
                message="Function has too many parameters.",
                suggestion="Consider grouping related parameters into a DTO or configuration object.",
            )
        ]


TooManyArgumentsRule = TooManyParametersRule
