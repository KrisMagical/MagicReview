"""Base interface for ReviewAgent Phase 6 agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.agents.context import AgentContext, AgentResult


class ReviewAgent(ABC):
    """Common contract for all project review agents."""

    name: str
    category: str

    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult:
        """Run the agent and return normalized issues."""
