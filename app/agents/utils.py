"""Utility helpers shared by multi-agent implementations."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from app.models.issue import Issue


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def read_python_source(project_root: Path, relative_path: Path) -> str | None:
    try:
        return (project_root / relative_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def parse_python(file_path: str, source: str) -> ast.AST | None:
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return None
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_parent", parent)
    return tree


def dedupe_and_sort(issues: Iterable[Issue]) -> list[Issue]:
    unique: dict[tuple[str, str, int, str], Issue] = {}
    for issue in issues:
        key = (issue.type, issue.file, issue.line, issue.message)
        existing = unique.get(key)
        if existing is None or SEVERITY_ORDER[issue.severity] < SEVERITY_ORDER[existing.severity]:
            unique[key] = issue
    return sorted(unique.values(), key=lambda issue: (SEVERITY_ORDER[issue.severity], issue.file, issue.line, issue.type))


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""
