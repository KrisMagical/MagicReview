"""Pydantic model checks for FastAPI projects."""

from __future__ import annotations

import ast

from app.models.issue import Issue
from app.analyzers.fastapi.utils import annotation_text, call_name, is_basemodel_class


class PydanticModelAnalyzer:
    """Analyze Pydantic BaseModel classes for validation risks."""

    constrained_kwargs = {
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
    }
    constrained_types = {
        "EmailStr",
        "AnyUrl",
        "HttpUrl",
        "PositiveInt",
        "PositiveFloat",
        "NonNegativeInt",
        "NonNegativeFloat",
        "constr",
        "conint",
        "confloat",
        "StringConstraints",
        "Annotated",
    }

    def analyze_tree(self, tree: ast.AST, file_path: str) -> list[Issue]:
        issues: list[Issue] = []
        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef) or not is_basemodel_class(class_node):
                continue
            for statement in class_node.body:
                if isinstance(statement, ast.Assign):
                    issues.append(
                        Issue(
                            severity="medium",
                            type="PydanticMissingTypeAnnotation",
                            file=file_path,
                            line=getattr(statement, "lineno", class_node.lineno),
                            message="Pydantic field is missing a type annotation.",
                            suggestion="Add an explicit type annotation to every Pydantic model field.",
                        )
                    )
                    if self._is_mutable_literal(statement.value):
                        issues.append(self._mutable_default_issue(file_path, getattr(statement, "lineno", class_node.lineno)))
                    continue
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                field_name = statement.target.id
                annotation = annotation_text(statement.annotation)
                if self._is_optional(annotation) and statement.value is None:
                    issues.append(
                        Issue(
                            severity="low",
                            type="PydanticOptionalFieldRisk",
                            file=file_path,
                            line=statement.lineno,
                            message=f"Optional field '{field_name}' has no explicit default or validation constraint.",
                            suggestion="Set an explicit default value or Field(...) constraint for Optional fields.",
                        )
                    )
                if statement.value is not None and self._is_mutable_literal(statement.value):
                    issues.append(self._mutable_default_issue(file_path, statement.lineno))
                if self._needs_validation(annotation) and not self._has_validation(statement):
                    issues.append(
                        Issue(
                            severity="low",
                            type="PydanticMissingFieldValidation",
                            file=file_path,
                            line=statement.lineno,
                            message=f"Pydantic field '{field_name}' is missing validation constraints.",
                            suggestion="Add Field constraints such as min_length, max_length, ge, or le.",
                        )
                    )
        return issues

    @staticmethod
    def _is_optional(annotation: str) -> bool:
        return "Optional[" in annotation or "| None" in annotation or "None |" in annotation

    @staticmethod
    def _needs_validation(annotation: str) -> bool:
        tokens = {"str", "int", "float", "Decimal"}
        return any(token in annotation for token in tokens)

    @classmethod
    def _has_validation(cls, statement: ast.AnnAssign) -> bool:
        annotation = annotation_text(statement.annotation)
        if any(name in annotation for name in cls.constrained_types):
            return True
        value = statement.value
        if isinstance(value, ast.Call) and call_name(value.func) == "Field":
            return any(keyword.arg in cls.constrained_kwargs for keyword in value.keywords)
        return False

    @staticmethod
    def _is_mutable_literal(node: ast.AST) -> bool:
        return isinstance(node, (ast.List, ast.Dict, ast.Set))

    @staticmethod
    def _mutable_default_issue(file_path: str, line: int) -> Issue:
        return Issue(
            severity="medium",
            type="PydanticMutableDefault",
            file=file_path,
            line=line,
            message="Pydantic field uses a mutable default value.",
            suggestion="Use default_factory instead of mutable default values.",
        )
