"""FastAPI route design checks."""

from __future__ import annotations

import ast

from app.models.issue import Issue
from app.analyzers.fastapi.utils import has_keyword, route_decorator, route_method, call_name


class FastAPIRouteAnalyzer:
    """Analyze FastAPI route handlers for API design risks."""

    response_keywords = {"response_model"}
    non_get_methods = {"post", "put", "patch", "delete"}
    db_call_names = {
        "execute",
        "query",
        "commit",
        "rollback",
        "connect",
        "Session",
        "sessionmaker",
        "requests.get",
        "requests.post",
        "httpx.Client",
        "AsyncClient",
    }

    def analyze_tree(self, tree: ast.AST, file_path: str) -> list[Issue]:
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorator = route_decorator(node)
            if decorator is None:
                continue
            method = route_method(decorator)
            if not has_keyword(decorator, self.response_keywords):
                issues.append(
                    Issue(
                        severity="medium",
                        type="FastAPIMissingResponseModel",
                        file=file_path,
                        line=getattr(decorator, "lineno", node.lineno),
                        message="Route is missing response_model.",
                        suggestion="Add response_model to make API responses explicit.",
                    )
                )
            if method in self.non_get_methods and not has_keyword(decorator, {"status_code"}):
                issues.append(
                    Issue(
                        severity="medium",
                        type="FastAPIMissingStatusCode",
                        file=file_path,
                        line=getattr(decorator, "lineno", node.lineno),
                        message="Non-GET route is missing an explicit status_code.",
                        suggestion="Add explicit status_code for non-GET endpoints.",
                    )
                )
            if self._returns_unstructured_dict(node):
                issues.append(
                    Issue(
                        severity="medium",
                        type="FastAPIUnstructuredResponse",
                        file=file_path,
                        line=node.lineno,
                        message="Route returns a raw dictionary without a consistent response shape.",
                        suggestion='Return a consistent response schema such as {"code": ..., "message": ..., "data": ...}.',
                    )
                )
            if self._is_heavy_route(node):
                issues.append(
                    Issue(
                        severity="medium",
                        type="FastAPIHeavyRouteHandler",
                        file=file_path,
                        line=node.lineno,
                        message="Route handler appears to contain business logic.",
                        suggestion="Move business logic to a service layer.",
                    )
                )
        return issues

    @staticmethod
    def _returns_unstructured_dict(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        expected_keys = {"code", "message", "data"}
        for child in ast.walk(node):
            if not isinstance(child, ast.Return) or not isinstance(child.value, ast.Dict):
                continue
            keys = {
                key.value
                for key in child.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            if not expected_keys.issubset(keys):
                return True
        return False

    @classmethod
    def _is_heavy_route(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        end_lineno = getattr(node, "end_lineno", node.lineno)
        if end_lineno - node.lineno + 1 > 50:
            return True
        if any(cls._is_db_operation(child) for child in ast.walk(node)):
            return True
        if sum(isinstance(child, (ast.For, ast.While, ast.AsyncFor)) for child in ast.walk(node)) >= 2:
            return True
        return cls._max_if_depth(node) >= 3

    @classmethod
    def _is_db_operation(cls, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        name = call_name(node.func)
        return name in cls.db_call_names or any(name.endswith(f".{candidate}") for candidate in cls.db_call_names)

    @classmethod
    def _max_if_depth(cls, node: ast.AST, depth: int = 0) -> int:
        max_depth = depth
        for child in ast.iter_child_nodes(node):
            child_depth = depth + 1 if isinstance(child, ast.If) else depth
            max_depth = max(max_depth, cls._max_if_depth(child, child_depth))
        return max_depth
