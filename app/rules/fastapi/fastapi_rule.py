"""FastAPI and Pydantic best-practice checks."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, IssueDict, make_issue


class FastAPIRule(BaseRule):
    """Detect route contract gaps, unsafe Depends usage, and weak schemas."""

    ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
    RESPONSE_KWARGS = {"response_model", "response_class"}
    SENSITIVE_NAMES = {"password", "passwd", "secret", "token", "api_key", "hash"}
    INPUT_MODEL_HINTS = ("request", "create", "update", "input", "payload", "form", "command")
    RESPONSE_MODEL_HINTS = ("response", "read", "out", "view")
    CONSTRAINT_KWARGS = {
        "min_length",
        "max_length",
        "pattern",
        "regex",
        "ge",
        "gt",
        "le",
        "lt",
        "min_items",
        "max_items",
        "min_digits",
        "max_digits",
        "decimal_places",
    }
    CONSTRAINED_TYPES = {
        "EmailStr",
        "AnyUrl",
        "HttpUrl",
        "PositiveInt",
        "PositiveFloat",
        "NegativeInt",
        "NegativeFloat",
        "NonNegativeInt",
        "NonNegativeFloat",
        "NonPositiveInt",
        "NonPositiveFloat",
        "StrictStr",
        "constr",
        "conint",
        "confloat",
        "conlist",
        "StringConstraints",
        "annotated_types",
    }
    BLOCKING_CALLS = {
        "open",
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "time.sleep",
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "sqlite3.connect",
    }

    def match(self, node: ast.AST, file_path: str, source_code: str) -> list[IssueDict]:
        if not isinstance(node, ast.Module):
            return []

        function_defs = self._collect_functions(node)
        issues: list[IssueDict] = []
        issues.extend(self._check_routes(node, file_path))
        issues.extend(self._check_depends(node, file_path, function_defs))
        issues.extend(self._check_pydantic_models(node, file_path))
        return issues

    @classmethod
    def _check_routes(cls, tree: ast.Module, file_path: str) -> list[IssueDict]:
        issues: list[IssueDict] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route_decorator = cls._route_decorator(node)
            if route_decorator is None:
                continue
            if node.returns is not None or cls._has_any_keyword(route_decorator, cls.RESPONSE_KWARGS):
                continue

            severity = "high" if cls._function_uses_sensitive_data(node) else "medium"
            issues.append(
                make_issue(
                    severity=severity,
                    issue_type="fastapi_response_model",
                    file_path=file_path,
                    line=getattr(route_decorator, "lineno", node.lineno),
                    message=(
                        "路径操作未定义 response_model/response_class，且缺少返回类型标注，"
                        "API 契约不明确，可能把敏感字段直接暴露给前端；建议设置 "
                        "response_model 或补充明确的返回类型标注。"
                    ),
                )
            )
        return issues

    @classmethod
    def _check_depends(
        cls,
        tree: ast.Module,
        file_path: str,
        function_defs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> list[IssueDict]:
        issues: list[IssueDict] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            dependencies: dict[str, ast.Call] = {}
            for call in cls._iter_depends_calls(node):
                dependency_expr = call.args[0] if call.args else cls._keyword_value(call, "dependency")
                dependency_name = cls._dependency_name(dependency_expr)

                if dependency_expr is not None and not cls._looks_callable_reference(dependency_expr):
                    issues.append(cls._depends_issue(file_path, call, "Depends 参数不是可调用对象引用，请传入函数、类或可调用实例。"))
                    continue

                if dependency_name:
                    if dependency_name in dependencies:
                        issues.append(
                            cls._depends_issue(
                                file_path,
                                call,
                                f"Depends 重复注入了 `{dependency_name}`，会让路由职责和资源生命周期变得模糊；建议合并依赖或在 Service 层复用。",
                            )
                        )
                    dependencies[dependency_name] = call

                    dependency_def = function_defs.get(dependency_name)
                    if isinstance(dependency_def, ast.AsyncFunctionDef) and cls._has_blocking_io(dependency_def):
                        issues.append(
                            cls._depends_issue(
                                file_path,
                                call,
                                f"Depends 依赖 `{dependency_name}` 定义为 async def 但包含阻塞 I/O；建议改为同步 def 交给线程池执行，或替换为异步客户端。",
                            )
                        )
        return issues

    @classmethod
    def _check_pydantic_models(cls, tree: ast.Module, file_path: str) -> list[IssueDict]:
        issues: list[IssueDict] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not cls._inherits_base_model(node):
                continue
            if not cls._is_input_model(node.name):
                continue

            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                if not cls._needs_constraints(statement.annotation):
                    continue
                if cls._has_constraints(statement):
                    continue

                field_name = statement.target.id
                severity = "high" if cls._is_business_critical_field(field_name) else "medium"
                issues.append(
                    make_issue(
                        severity=severity,
                        issue_type="pydantic_missing_constraints",
                        file_path=file_path,
                        line=getattr(statement, "lineno", node.lineno),
                        message=(
                            f"Pydantic 输入字段 `{field_name}` 缺乏有效约束，存在脏数据或畸形输入风险；"
                            "建议使用 Field(...)、Annotated/StringConstraints 或受约束类型补充长度、范围或格式校验。"
                        ),
                    )
                )
        return issues

    @classmethod
    def _route_decorator(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr in cls.ROUTE_METHODS:
                return decorator
        return None

    @staticmethod
    def _has_any_keyword(call: ast.Call, keyword_names: set[str]) -> bool:
        return any(keyword.arg in keyword_names for keyword in call.keywords)

    @classmethod
    def _function_uses_sensitive_data(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and cls._contains_sensitive_name(child.id):
                return True
            if isinstance(child, ast.Attribute) and cls._contains_sensitive_name(child.attr):
                return True
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and cls._contains_sensitive_name(child.value):
                return True
        return False

    @classmethod
    def _contains_sensitive_name(cls, value: str) -> bool:
        lowered = value.lower()
        return any(name in lowered for name in cls.SENSITIVE_NAMES)

    @classmethod
    def _iter_depends_calls(cls, node: ast.AST) -> list[ast.Call]:
        return [
            child
            for child in ast.walk(node)
            if isinstance(child, ast.Call) and cls._call_name(child.func) == "Depends"
        ]

    @classmethod
    def _call_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = cls._call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    @staticmethod
    def _keyword_value(call: ast.Call, name: str) -> ast.AST | None:
        for keyword in call.keywords:
            if keyword.arg == name:
                return keyword.value
        return None

    @classmethod
    def _dependency_name(cls, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return cls._call_name(node)
        return None

    @staticmethod
    def _looks_callable_reference(node: ast.AST) -> bool:
        return isinstance(node, (ast.Name, ast.Attribute, ast.Lambda))

    @staticmethod
    def _collect_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
        return {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    @classmethod
    def _has_blocking_io(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and cls._call_name(child.func) in cls.BLOCKING_CALLS:
                return True
        return False

    @staticmethod
    def _depends_issue(file_path: str, call: ast.Call, message: str) -> IssueDict:
        return make_issue(
            severity="medium",
            issue_type="fastapi_depends_misuse",
            file_path=file_path,
            line=getattr(call, "lineno", 1),
            message=f"Depends 依赖注入使用不当 / 职责边界模糊：{message}",
        )

    @classmethod
    def _inherits_base_model(cls, node: ast.ClassDef) -> bool:
        return any(cls._call_name(base) in {"BaseModel", "pydantic.BaseModel"} for base in node.bases)

    @classmethod
    def _is_input_model(cls, class_name: str) -> bool:
        lowered = class_name.lower()
        if any(hint in lowered for hint in cls.RESPONSE_MODEL_HINTS):
            return any(hint in lowered for hint in cls.INPUT_MODEL_HINTS)
        return any(hint in lowered for hint in cls.INPUT_MODEL_HINTS)

    @classmethod
    def _needs_constraints(cls, annotation: ast.AST) -> bool:
        name = cls._annotation_text(annotation)
        return any(token in name for token in ("str", "int", "float", "Decimal", "list", "set", "tuple"))

    @classmethod
    def _has_constraints(cls, statement: ast.AnnAssign) -> bool:
        if any(type_name in cls._annotation_text(statement.annotation) for type_name in cls.CONSTRAINED_TYPES):
            return True

        value = statement.value
        if isinstance(value, ast.Call) and cls._call_name(value.func) == "Field":
            return cls._has_any_keyword(value, cls.CONSTRAINT_KWARGS)
        if isinstance(statement.annotation, ast.Subscript) and "Annotated" in cls._annotation_text(statement.annotation):
            return any(name in cls._annotation_text(statement.annotation) for name in (*cls.CONSTRAINT_KWARGS, *cls.CONSTRAINED_TYPES))
        return False

    @staticmethod
    def _annotation_text(annotation: ast.AST) -> str:
        try:
            return ast.unparse(annotation)
        except Exception:
            return ""

    @classmethod
    def _is_business_critical_field(cls, field_name: str) -> bool:
        lowered = field_name.lower()
        critical_tokens = {"id", "email", "phone", "amount", "price", "password", "username", "name"}
        return any(token in lowered for token in critical_tokens)
