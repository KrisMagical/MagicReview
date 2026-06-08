"""Bug-risk AST rules."""

from app.rules.bug.file_leak import FileLeakRule
from app.rules.bug.index_risk import IndexRiskRule
from app.rules.bug.key_error import KeyErrorRule
from app.rules.bug.path_traversal import PathTraversalRule
from app.rules.bug.potential_none_type import NoneRiskRule, PotentialNoneTypeRule
from app.rules.bug.sql_injection import SQLInjectionRule
from app.rules.bug.zero_division import ZeroDivisionRule

__all__ = [
    "FileLeakRule",
    "IndexRiskRule",
    "KeyErrorRule",
    "NoneRiskRule",
    "PathTraversalRule",
    "PotentialNoneTypeRule",
    "SQLInjectionRule",
    "ZeroDivisionRule",
]
