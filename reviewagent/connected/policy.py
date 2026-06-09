"""Network access policy for connected ReviewAgent services."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal


CodeSharingMode = Literal["none", "summary_only", "snippets", "full_context"]


@dataclass(frozen=True)
class NetworkPolicy:
    """Explicit consent gate for networked providers and hosted services."""

    enabled: bool = False
    allow_llm: bool = False
    allow_github_api: bool = False
    allow_remote_mcp: bool = False
    code_sharing_mode: CodeSharingMode = "none"
    allowed_providers: list[str] = field(default_factory=list)
    require_explicit_consent: bool = True
    audit_enabled: bool = True

    @classmethod
    def offline(cls) -> "NetworkPolicy":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "NetworkPolicy":
        if not data:
            return cls.offline()
        mode = str(data.get("code_sharing_mode", data.get("codeSharingMode", "none"))).replace("-", "_")
        if mode not in {"none", "summary_only", "snippets", "full_context"}:
            mode = "none"
        providers = data.get("allowed_providers") or data.get("allowedProviders") or []
        if isinstance(providers, str):
            providers = [item.strip() for item in providers.split(",") if item.strip()]
        return cls(
            enabled=bool(data.get("enabled", False)),
            allow_llm=bool(data.get("allow_llm", data.get("allowLlm", False))),
            allow_github_api=bool(data.get("allow_github_api", data.get("allowGithubApi", False))),
            allow_remote_mcp=bool(data.get("allow_remote_mcp", data.get("allowRemoteMcp", False))),
            code_sharing_mode=mode,  # type: ignore[arg-type]
            allowed_providers=list(providers) if isinstance(providers, list) else [],
            require_explicit_consent=bool(data.get("require_explicit_consent", data.get("requireExplicitConsent", True))),
            audit_enabled=bool(data.get("audit_enabled", data.get("auditEnabled", True))),
        )

    @classmethod
    def from_env(cls) -> "NetworkPolicy":
        return cls(
            enabled=_bool("REVIEWAGENT_NETWORK_ENABLED", False),
            allow_llm=_bool("REVIEWAGENT_ALLOW_LLM", False),
            allow_github_api=_bool("REVIEWAGENT_ALLOW_GITHUB_API", False),
            allow_remote_mcp=_bool("REVIEWAGENT_ALLOW_REMOTE_MCP", False),
            code_sharing_mode=_mode(os.getenv("REVIEWAGENT_CODE_SHARING_MODE", "none")),
            allowed_providers=[item.strip() for item in os.getenv("REVIEWAGENT_ALLOWED_PROVIDERS", "").split(",") if item.strip()],
            require_explicit_consent=_bool("REVIEWAGENT_REQUIRE_EXPLICIT_CONSENT", True),
            audit_enabled=_bool("REVIEWAGENT_AUDIT_NETWORK", True),
        )

    def allows_provider(self, provider: str, *, needs_llm: bool = True) -> bool:
        if not self.enabled:
            return False
        if needs_llm and not self.allow_llm:
            return False
        if self.code_sharing_mode == "none":
            return False
        if self.allowed_providers and provider not in self.allowed_providers:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "allow_llm": self.allow_llm,
            "allow_github_api": self.allow_github_api,
            "allow_remote_mcp": self.allow_remote_mcp,
            "code_sharing_mode": self.code_sharing_mode,
            "allowed_providers": list(self.allowed_providers),
            "require_explicit_consent": self.require_explicit_consent,
            "audit_enabled": self.audit_enabled,
        }


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mode(value: str) -> CodeSharingMode:
    normalized = value.replace("-", "_")
    if normalized in {"summary_only", "snippets", "full_context"}:
        return normalized  # type: ignore[return-value]
    return "none"
