"""Shared AST helpers for FastAPI analyzers."""

from __future__ import annotations

import ast


ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def keyword_value(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def has_keyword(call: ast.Call, names: set[str]) -> bool:
    return any(keyword.arg in names for keyword in call.keywords)


def route_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            if decorator.func.attr in ROUTE_METHODS:
                return decorator
    return None


def route_method(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr.lower()
    return ""


def annotation_text(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def is_basemodel_class(node: ast.ClassDef) -> bool:
    return any(call_name(base) in {"BaseModel", "pydantic.BaseModel"} for base in node.bases)
