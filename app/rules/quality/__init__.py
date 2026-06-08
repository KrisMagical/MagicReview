"""Quality AST rules and compatibility lint rules."""

from app.rules.quality.function_too_long import FunctionTooLongRule
from app.rules.quality.magic_number import MagicNumberRule
from app.rules.quality.missing_type_hint import MissingTypeHintRule, TypeHintRule
from app.rules.quality.ruff import RuffLintRule
from app.rules.quality.too_many_arguments import TooManyArgumentsRule, TooManyParametersRule

__all__ = [
    "FunctionTooLongRule",
    "MagicNumberRule",
    "MissingTypeHintRule",
    "TypeHintRule",
    "RuffLintRule",
    "TooManyArgumentsRule",
    "TooManyParametersRule",
]
