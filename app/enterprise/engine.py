"""Enterprise rule execution engine."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from app.enterprise.config_loader import EnterpriseRuleConfig
from app.models.issue import Issue


class EnterpriseRuleEngine:
    """Execute configured enterprise rules and normalize findings."""

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def __init__(self, config: EnterpriseRuleConfig) -> None:
        self.config = config

    def run_project(self, project_root: str | Path, files: list[Path]) -> list[Issue]:
        issues: list[Issue] = [*self.config.errors]
        root = Path(project_root).resolve()
        for relative_path in files:
            try:
                source = (root / relative_path).read_text(encoding="utf-8")
            except OSError:
                continue
            issues.extend(self.run_file(relative_path.as_posix(), source))
        return self._dedupe_and_sort(issues)

    def run_file(self, file_path: str, source: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return issues
        for rule_name, handler in self._handlers().items():
            rule_config = self.config.rules.get(rule_name, {})
            if not rule_config.get("enabled", False):
                continue
            try:
                issues.extend(handler(file_path, source, tree, rule_config))
            except Exception:
                issues.append(
                    Issue(
                        severity="low",
                        type="EnterpriseRuleExecutionError",
                        file=file_path or "<project>",
                        line=1,
                        message="Enterprise rule execution failed.",
                        suggestion="Check the rule configuration or disable the problematic rule.",
                    )
                )
        return self._dedupe_and_sort(issues)

    def _handlers(self):
        return {
            "max_function_length": self._max_function_length,
            "max_parameters": self._max_parameters,
            "no_select_star": self._no_select_star,
            "no_controller_repository": self._no_controller_repository,
            "service_log_required": self._service_log_required,
            "forbidden_imports": self._forbidden_imports,
            "layer_rules": self._layer_rules,
        }

    def _max_function_length(self, file_path: str, source: str, tree: ast.AST, config: dict[str, Any]) -> list[Issue]:
        max_lines = int(config.get("max_lines", 80))
        severity = config["severity"]
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                if end_lineno - node.lineno + 1 > max_lines:
                    issues.append(self._issue(severity, "EnterpriseMaxFunctionLength", file_path, node.lineno, "Function exceeds enterprise maximum length.", "Split this function according to enterprise coding standards."))
        return issues

    def _max_parameters(self, file_path: str, source: str, tree: ast.AST, config: dict[str, Any]) -> list[Issue]:
        max_params = int(config.get("max_params", 5))
        severity = config["severity"]
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                params.extend(arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None)
                count = len([arg for arg in params if arg.arg not in {"self", "cls"}])
                if count > max_params:
                    issues.append(self._issue(severity, "EnterpriseMaxParameters", file_path, node.lineno, "Function exceeds enterprise maximum parameter count.", "Group related parameters into a request object or configuration model."))
        return issues

    def _no_select_star(self, file_path: str, source: str, tree: ast.AST, config: dict[str, Any]) -> list[Issue]:
        severity = config["severity"]
        issues: list[Issue] = []
        assigned_sql: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value if isinstance(node, ast.AnnAssign) else node.value
                if value is not None and self._contains_select_star(value):
                    for target in self._assignment_targets(node):
                        assigned_sql[target] = getattr(node, "lineno", 1)
            if self._contains_select_star(node):
                issues.append(self._issue(severity, "EnterpriseNoSelectStar", file_path, getattr(node, "lineno", 1), "SELECT * is forbidden by enterprise SQL policy.", "Select explicit columns to reduce coupling and improve performance."))
            if isinstance(node, ast.Name) and node.id in assigned_sql:
                issues.append(self._issue(severity, "EnterpriseNoSelectStar", file_path, assigned_sql[node.id], "SELECT * is forbidden by enterprise SQL policy.", "Select explicit columns to reduce coupling and improve performance."))
        return issues

    def _no_controller_repository(self, file_path: str, source: str, tree: ast.AST, config: dict[str, Any]) -> list[Issue]:
        controller_patterns = config.get("controller_patterns", ["controllers/", "api/", "routers/"])
        repository_patterns = config.get("repository_patterns", ["repositories/", "repository/", "db"])
        if not self._matches_any(file_path, controller_patterns):
            return []
        severity = config["severity"]
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = self._import_names(node)
                if any(self._matches_any(name.replace(".", "/"), repository_patterns) for name in imported):
                    issues.append(self._issue(severity, "EnterpriseNoControllerRepository", file_path, getattr(node, "lineno", 1), "Controller layer should not directly depend on repository layer.", "Move data access logic into a service layer."))
            elif isinstance(node, ast.Call) and "Repository" in self._call_name(node.func):
                issues.append(self._issue(severity, "EnterpriseNoControllerRepository", file_path, getattr(node, "lineno", 1), "Controller layer should not directly depend on repository layer.", "Move data access logic into a service layer."))
        return issues

    def _service_log_required(self, file_path: str, source: str, tree: ast.AST, config: dict[str, Any]) -> list[Issue]:
        service_patterns = config.get("service_patterns", ["services/", "service/"])
        if not self._matches_any(file_path, service_patterns):
            return []
        logger_names = set(config.get("logger_names", ["logger", "log"]))
        severity = config["severity"]
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_") or self._is_simple_getter(node):
                    continue
                if not self._has_logging(node, logger_names):
                    issues.append(self._issue(severity, "EnterpriseServiceLogRequired", file_path, node.lineno, "Service function does not contain required logging.", "Add structured logging according to enterprise standards."))
        return issues

    def _forbidden_imports(self, file_path: str, source: str, tree: ast.AST, config: dict[str, Any]) -> list[Issue]:
        forbidden = set(config.get("imports", []))
        severity = config["severity"]
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for name in self._import_names(node):
                    if name in forbidden:
                        issues.append(self._issue(severity, "EnterpriseForbiddenImport", file_path, getattr(node, "lineno", 1), "Forbidden import or API usage detected.", "Use approved alternatives according to enterprise standards."))
            elif isinstance(node, ast.Call):
                name = self._call_name(node.func)
                if name in forbidden:
                    issues.append(self._issue(severity, "EnterpriseForbiddenImport", file_path, getattr(node, "lineno", 1), "Forbidden import or API usage detected.", "Use approved alternatives according to enterprise standards."))
        return issues

    def _layer_rules(self, file_path: str, source: str, tree: ast.AST, config: dict[str, Any]) -> list[Issue]:
        severity = config["severity"]
        issues: list[Issue] = []
        for rule in config.get("rules", []):
            if not isinstance(rule, dict):
                continue
            from_layer = str(rule.get("from", ""))
            cannot_import = [str(item) for item in rule.get("cannot_import", [])]
            if from_layer not in file_path.replace("\\", "/"):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imported = self._import_names(node)
                    if any(blocked in name for blocked in cannot_import for name in imported):
                        issues.append(self._issue(severity, "EnterpriseLayerViolation", file_path, getattr(node, "lineno", 1), "Layer dependency rule violated.", "Follow the configured enterprise dependency direction."))
        return issues

    @staticmethod
    def _issue(severity: str, issue_type: str, file_path: str, line: int, message: str, suggestion: str) -> Issue:
        return Issue(severity=severity, type=issue_type, file=file_path, line=line, message=message, suggestion=suggestion)

    @staticmethod
    def _contains_select_star(node: ast.AST) -> bool:
        text = ""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            try:
                text = ast.unparse(node)
            except Exception:
                text = ""
        elif isinstance(node, ast.Call) and node.args:
            return any(EnterpriseRuleEngine._contains_select_star(arg) for arg in node.args)
        return bool(re.search(r"\bselect\s+\*", text, flags=re.IGNORECASE))

    @staticmethod
    def _assignment_targets(node: ast.Assign | ast.AnnAssign) -> list[str]:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return [target.id for target in targets if isinstance(target, ast.Name)]

    @staticmethod
    def _matches_any(value: str, patterns: list[str]) -> bool:
        normalized = value.replace("\\", "/").lower()
        return any(str(pattern).lower() in normalized for pattern in patterns)

    @staticmethod
    def _import_names(node: ast.Import | ast.ImportFrom) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        base = node.module or ""
        return [f"{base}.{alias.name}" if base else alias.name for alias in node.names]

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = EnterpriseRuleEngine._call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    @staticmethod
    def _is_simple_getter(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
            return False
        return isinstance(node.body[0].value, (ast.Name, ast.Attribute, ast.Constant))

    @staticmethod
    def _has_logging(node: ast.FunctionDef | ast.AsyncFunctionDef, logger_names: set[str]) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = EnterpriseRuleEngine._call_name(child.func)
                if name.split(".")[0] in logger_names:
                    return True
        return False

    @classmethod
    def _dedupe_and_sort(cls, issues: list[Issue]) -> list[Issue]:
        unique: dict[tuple[str, str, int, str], Issue] = {}
        for issue in issues:
            key = (issue.type, issue.file, issue.line, issue.message)
            existing = unique.get(key)
            if existing is None or cls.severity_order[issue.severity] < cls.severity_order[existing.severity]:
                unique[key] = issue
        return sorted(unique.values(), key=lambda issue: (cls.severity_order[issue.severity], issue.file, issue.line, issue.type))
