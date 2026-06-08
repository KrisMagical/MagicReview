"""LLM provider abstraction for architecture review."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider is unavailable or fails."""


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return raw model text for a prompt."""


class NoneLLMProvider(LLMProvider):
    def complete(self, prompt: str) -> str:
        raise LLMProviderError("LLM architecture review is not configured.")


class OpenAILLMProvider(LLMProvider):
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("REVIEWAGENT_LLM_MODEL") or "gpt-4o-mini"

    def complete(self, prompt: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMProviderError("openai package is not installed.") from exc
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


def provider_from_env(name: str | None = None) -> LLMProvider:
    provider = (name or os.getenv("REVIEWAGENT_LLM_PROVIDER") or "none").lower()
    if provider == "openai":
        return OpenAILLMProvider()
    if provider == "mock":
        from app.llm.mock_provider import MockLLMProvider

        return MockLLMProvider()
    return NoneLLMProvider()
