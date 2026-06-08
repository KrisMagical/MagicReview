"""Rule exports for the PR Review Agent."""

from app.rules.base import BaseRule, Issue, IssueDict, Rule
from app.rules.bug import (
    FileLeakRule,
    IndexRiskRule,
    KeyErrorRule,
    NoneRiskRule,
    PathTraversalRule,
    PotentialNoneTypeRule,
    SQLInjectionRule,
    ZeroDivisionRule,
)
from app.rules.engine import RuleEngine, default_phase1_rules
from app.rules.fastapi import FastAPIRule
from app.rules.quality import (
    FunctionTooLongRule,
    MagicNumberRule,
    MissingTypeHintRule,
    RuffLintRule,
    TooManyParametersRule,
    TypeHintRule,
    TooManyArgumentsRule,
)

__all__ = [
    "BaseRule",
    "FileLeakRule",
    "FastAPIRule",
    "FunctionTooLongRule",
    "IndexRiskRule",
    "Issue",
    "IssueDict",
    "KeyErrorRule",
    "MagicNumberRule",
    "MissingTypeHintRule",
    "NoneRiskRule",
    "PathTraversalRule",
    "PotentialNoneTypeRule",
    "RuleEngine",
    "RuffLintRule",
    "RuffAdapter",
    "Rule",
    "TooManyArgumentsRule",
    "TooManyParametersRule",
    "TypeHintRule",
    "ZeroDivisionRule",
    "default_phase1_rules",
]


def __getattr__(name: str):
    if name == "RuffAdapter":
        from app.rules.ruff_adapter import RuffAdapter

        return RuffAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
