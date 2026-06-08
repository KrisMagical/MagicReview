"""FastAPI dependency injection checks."""

from __future__ import annotations

import ast

from app.models.issue import Issue
from app.analyzers.fastapi.utils import call_name, route_decorator


class FastAPIDependencyAnalyzer:
    """Analyze FastAPI dependency usage and resource lifecycle risks."""

    resource_factories = {
        "Session",
        "SessionLocal",
        "create_engine",
        "connect",
        "Client",
        "AsyncClient",
        "Redis",
        "MongoClient",
        "Service",
        "UserService",
        "Database",
    }
    resource_methods = {"connect", "cursor", "execute", "commit"}

    def analyze_tree(self, tree: ast.AST, file_path: str) -> list[Issue]:
        issues: list[Issue] = []
        function_defs = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        direct_resources: set[str] = set()
        injected_resources: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_route = route_decorator(node) is not None
            if is_route:
                route_direct = self._direct_resource_calls(node)
                direct_resources.update(route_direct.keys())
                for call in route_direct.values():
                    issues.append(
                        Issue(
                            severity="medium",
                            type="FastAPIMissingDependencyInjection",
                            file=file_path,
                            line=getattr(call, "lineno", node.lineno),
                            message="Route creates a database, client, or service directly.",
                            suggestion="Use Depends to inject dependencies.",
                        )
                    )
                injected_resources.update(self._depends_resource_names(node))

            for depends_call in self._iter_depends_calls(node):
                dependency_expr = depends_call.args[0] if depends_call.args else None
                if dependency_expr is not None and not isinstance(dependency_expr, (ast.Name, ast.Attribute)):
                    issues.append(
                        Issue(
                            severity="low",
                            type="FastAPIComplexDepends",
                            file=file_path,
                            line=getattr(depends_call, "lineno", node.lineno),
                            message="Depends uses a complex expression.",
                            suggestion="Pass a simple dependency function or callable reference to Depends.",
                        )
                    )
                dependency_name = self._dependency_name(dependency_expr)
                dependency_def = function_defs.get(dependency_name or "")
                if dependency_def is not None and self._manages_resource_without_yield(dependency_def):
                    issues.append(
                        Issue(
                            severity="medium",
                            type="FastAPIResourceDependencyRisk",
                            file=file_path,
                            line=dependency_def.lineno,
                            message="Dependency appears to manage a resource without cleanup.",
                            suggestion="Use yield dependencies to manage resource lifecycle.",
                        )
                    )

        if direct_resources and injected_resources and direct_resources & injected_resources:
            issues.append(
                Issue(
                    severity="medium",
                    type="FastAPIInconsistentDependencyUsage",
                    file=file_path,
                    line=1,
                    message="Similar resources are both injected and created directly.",
                    suggestion="Use Depends consistently for shared resources.",
                )
            )
        return issues

    @classmethod
    def _direct_resource_calls(cls, node: ast.AST) -> dict[str, ast.Call]:
        calls: dict[str, ast.Call] = {}
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            name = call_name(child.func)
            resource = cls._resource_name(name)
            if resource:
                calls[resource] = child
        return calls

    @classmethod
    def _resource_name(cls, name: str) -> str:
        if name in cls.resource_factories:
            return name
        tail = name.split(".")[-1]
        if tail in cls.resource_factories or tail in cls.resource_methods:
            return tail
        return ""

    @classmethod
    def _iter_depends_calls(cls, node: ast.AST) -> list[ast.Call]:
        return [
            child
            for child in ast.walk(node)
            if isinstance(child, ast.Call) and call_name(child.func) == "Depends"
        ]

    @classmethod
    def _depends_resource_names(cls, node: ast.AST) -> set[str]:
        names: set[str] = set()
        for call in cls._iter_depends_calls(node):
            dependency_expr = call.args[0] if call.args else None
            dependency_name = cls._dependency_name(dependency_expr)
            if dependency_name:
                lowered = dependency_name.lower()
                if "db" in lowered or "session" in lowered:
                    names.add("SessionLocal")
                if "client" in lowered:
                    names.add("Client")
                if "service" in lowered:
                    names.add("Service")
        return names

    @staticmethod
    def _dependency_name(node: ast.AST | None) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return call_name(node)
        return None

    @classmethod
    def _manages_resource_without_yield(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        has_resource = bool(cls._direct_resource_calls(node))
        has_yield = any(isinstance(child, (ast.Yield, ast.YieldFrom)) for child in ast.walk(node))
        return has_resource and not has_yield
