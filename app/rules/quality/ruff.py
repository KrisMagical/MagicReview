"""Ruff-backed quality rule kept for rule-engine compatibility."""

from __future__ import annotations

import json
import logging
import subprocess

from app.rules.base import Issue, Rule


class RuffLintRule(Rule):
    """Use Ruff to check naming, unused variables, and related lint issues."""

    def __init__(self, ruff_path: str = "ruff"):
        self.ruff_path = ruff_path
        self.logger = logging.getLogger(__name__)

    def analyze(self, file_path: str, file_content: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            result = subprocess.run(
                [self.ruff_path, "check", file_path, "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if not result.stdout:
                return issues

            for item in json.loads(result.stdout):
                issues.append(
                    Issue(
                        severity=self._map_ruff_severity(item.get("code", "")),
                        type=item.get("code", "ruff_issue"),
                        file=item.get("filename", file_path),
                        line=item.get("location", {}).get("row", 1),
                        message=item.get("message", "Ruff found an issue"),
                    )
                )
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            self.logger.warning("Ruff failed for %s", file_path, exc_info=True)
        return issues

    @staticmethod
    def _map_ruff_severity(code: str) -> str:
        if code.startswith("F"):
            return "medium"
        if code.startswith("E"):
            return "high"
        if code.startswith("W"):
            return "low"
        return "low"
