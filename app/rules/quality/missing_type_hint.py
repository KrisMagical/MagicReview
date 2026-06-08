"""Rule for detecting missing function type annotations."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, make_issue


class TypeHintRule(BaseRule):
    """Detect missing argument or return annotations on functions."""

    name = "TypeHintRule"
    category = "quality"
    ignored_names = {"self", "cls"}

    def match(self, node: ast.AST, file_path: str, source_code: str) -> list[Issue]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return []

        issues: list[Issue] = []
        for argument in self._iter_arguments(node.args):
            if argument.arg in self.ignored_names or argument.annotation is not None:
                continue
            issues.append(
                make_issue(
                    severity="low",
                    issue_type=self.name,
                    file_path=file_path,
                    line=getattr(argument, "lineno", node.lineno),
                    message=f"Parameter '{argument.arg}' is missing a type annotation.",
                    suggestion="Add explicit Python type annotations for function parameters.",
                )
            )

        if node.returns is None:
            issues.append(
                make_issue(
                    severity="low",
                    issue_type=self.name,
                    file_path=file_path,
                    line=node.lineno,
                    message="Function is missing a return type annotation.",
                    suggestion="Add an explicit return type annotation, such as -> None.",
                )
            )

        return issues

    @staticmethod
    def _iter_arguments(arguments: ast.arguments) -> list[ast.arg]:
        return [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
            *([arguments.vararg] if arguments.vararg else []),
            *([arguments.kwarg] if arguments.kwarg else []),
        ]


MissingTypeHintRule = TypeHintRule
