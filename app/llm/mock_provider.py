"""Mock LLM provider for tests and local dry runs."""

from __future__ import annotations

import json

from app.llm.provider import LLMProvider


class MockLLMProvider(LLMProvider):
    name = "mock"
    requires_network = False

    def __init__(self, response: str | None = None) -> None:
        self.calls: list[str] = []
        self.response = response or json.dumps(
            {
                "issues": [
                    {
                        "severity": "medium",
                        "type": "MaintainabilityRisk",
                        "file": "app/services/user_service.py",
                        "line": 1,
                        "message": "Service responsibilities appear to drift across user, order, and notification concerns.",
                        "suggestion": "Split unrelated orchestration into focused services with clear boundaries.",
                    }
                ]
            }
        )

    def complete(self, prompt: str, policy=None) -> str:
        self.calls.append(prompt)
        return self.response
