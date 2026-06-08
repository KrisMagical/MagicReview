"""GitHub App environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GitHubAppConfig:
    app_id: str = ""
    private_key: str = ""
    webhook_secret: str = ""
    app_name: str = "ReviewAgent"
    enable_inline_comments: bool = True
    enable_summary_comment: bool = True
    enable_agents: bool = False
    enable_llm: bool = False
    save_results: bool = False
    config_path: str | None = None
    max_inline_comments: int = 30
    fail_on: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_env(cls) -> "GitHubAppConfig":
        return cls(
            app_id=os.getenv("GITHUB_APP_ID", ""),
            private_key=os.getenv("GITHUB_PRIVATE_KEY", ""),
            webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
            app_name=os.getenv("GITHUB_APP_NAME", "ReviewAgent"),
            enable_inline_comments=_bool_env("REVIEWAGENT_GITHUB_ENABLE_INLINE_COMMENTS", True),
            enable_summary_comment=_bool_env("REVIEWAGENT_GITHUB_ENABLE_SUMMARY_COMMENT", True),
            enable_agents=_bool_env("REVIEWAGENT_GITHUB_ENABLE_AGENTS", False),
            enable_llm=_bool_env("REVIEWAGENT_GITHUB_ENABLE_LLM", False),
            save_results=_bool_env("REVIEWAGENT_GITHUB_SAVE_RESULTS", False),
            config_path=os.getenv("REVIEWAGENT_GITHUB_CONFIG_PATH") or None,
            max_inline_comments=int(os.getenv("REVIEWAGENT_GITHUB_MAX_INLINE_COMMENTS", "30")),
            fail_on=os.getenv("REVIEWAGENT_GITHUB_FAIL_ON") or None,
            host=os.getenv("REVIEWAGENT_GITHUB_HOST", "0.0.0.0"),
            port=int(os.getenv("REVIEWAGENT_GITHUB_PORT", "8000")),
        )

    def validate_for_webhook(self) -> list[str]:
        missing = []
        if not self.webhook_secret:
            missing.append("GITHUB_WEBHOOK_SECRET")
        if not self.app_id:
            missing.append("GITHUB_APP_ID")
        if not self.private_key:
            missing.append("GITHUB_PRIVATE_KEY")
        return missing
