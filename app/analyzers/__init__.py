"""Analyzer exports."""

from app.analyzers.ast_analyzer import ASTAnalyzer, MagicNumberAnalyzer
from app.analyzers.dependency_analyzer import DependencyAnalyzer
from app.analyzers.ruff_adapter import RuffAdapter

__all__ = ["ASTAnalyzer", "ComplexityAnalyzer", "DependencyAnalyzer", "MagicNumberAnalyzer", "RadonAdapter", "RuffAdapter"]


def __getattr__(name: str):
    if name == "ComplexityAnalyzer":
        from app.analyzers.complexity_analyzer import ComplexityAnalyzer

        return ComplexityAnalyzer
    if name == "RadonAdapter":
        from app.analyzers.complexity_analyzer import RadonAdapter

        return RadonAdapter
    raise AttributeError(f"module 'app.analyzers' has no attribute {name!r}")
