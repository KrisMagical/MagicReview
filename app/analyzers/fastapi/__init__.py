"""FastAPI-specific static analyzers."""

from app.analyzers.fastapi.dependency_analyzer import FastAPIDependencyAnalyzer
from app.analyzers.fastapi.detector import FastAPIDetector
from app.analyzers.fastapi.pydantic_analyzer import PydanticModelAnalyzer
from app.analyzers.fastapi.route_analyzer import FastAPIRouteAnalyzer
from app.analyzers.fastapi.service import FastAPIProjectAnalyzer

__all__ = [
    "FastAPIDependencyAnalyzer",
    "FastAPIDetector",
    "FastAPIProjectAnalyzer",
    "FastAPIRouteAnalyzer",
    "PydanticModelAnalyzer",
]
