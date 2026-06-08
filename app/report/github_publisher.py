"""GitHub API integration for publishing PR review comments."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

import httpx
from pydantic import BaseModel

from app.report.formatter import ReviewIssue


GITHUB_API_URL = "https://api.github.com"


class GitHubPublisherError(RuntimeError):
    """Raised when GitHub publishing cannot complete cleanly."""


class GitHubPublisher:
    """Small async wrapper around the GitHub REST API."""

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        token: str,
        *,
        api_url: str = GITHUB_API_URL,
        timeout: float = 30.0,
    ) -> None:
        if not token:
            raise ValueError("GitHub token is required.")
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    async def fetch_pull_request_diff(self, repository: str, pull_number: int) -> str:
        """Fetch a PR's unified diff text."""

        response = await self._request(
            "GET",
            f"/repos/{repository}/pulls/{pull_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        return response.text

    async def fetch_file_contents(
        self,
        repository: str,
        paths: Iterable[str],
        *,
        ref: str,
    ) -> dict[str, str]:
        """Fetch changed file contents at the PR head SHA for analyzer context."""

        contents: dict[str, str] = {}
        for path in paths:
            if not path.endswith(".py"):
                continue
            try:
                response = await self._request(
                    "GET",
                    f"/repos/{repository}/contents/{path}",
                    params={"ref": ref},
                    headers={"Accept": "application/vnd.github.raw"},
                )
            except GitHubPublisherError:
                self.logger.warning("Could not fetch file content from GitHub: %s", path, exc_info=True)
                continue
            contents[path] = response.text
        return contents

    async def publish_review(
        self,
        *,
        repository: str,
        pull_number: int,
        commit_id: str,
        issues: Iterable[ReviewIssue | Mapping[str, Any] | BaseModel],
    ) -> None:
        """Publish inline comments in one review and fall back to a PR comment."""

        normalized = [issue for issue in (self._coerce_issue(raw) for raw in issues) if issue is not None]
        if not normalized:
            await self.create_issue_comment(
                repository=repository,
                pull_number=pull_number,
                body="pr-review-agent completed. No issues found.",
            )
            return

        comments, general_comments = self._build_review_comments(normalized)
        if comments:
            try:
                await self._create_pull_request_review(
                    repository=repository,
                    pull_number=pull_number,
                    commit_id=commit_id,
                    comments=comments,
                    body="Automated review by pr-review-agent.",
                )
            except GitHubPublisherError:
                self.logger.warning(
                    "GitHub inline review failed; falling back to a PR-level comment.",
                    exc_info=True,
                )
                general_comments = normalized

        if general_comments:
            await self.create_issue_comment(
                repository=repository,
                pull_number=pull_number,
                body=self.format_general_comment(general_comments),
            )

    async def create_issue_comment(self, *, repository: str, pull_number: int, body: str) -> None:
        """Create a normal PR conversation comment via the Issues API."""

        await self._request(
            "POST",
            f"/repos/{repository}/issues/{pull_number}/comments",
            json={"body": body},
        )

    async def _create_pull_request_review(
        self,
        *,
        repository: str,
        pull_number: int,
        commit_id: str,
        comments: list[dict[str, str | int]],
        body: str,
    ) -> None:
        await self._request(
            "POST",
            f"/repos/{repository}/pulls/{pull_number}/reviews",
            json={
                "commit_id": commit_id,
                "event": "COMMENT",
                "body": body,
                "comments": comments,
            },
        )

    def _build_review_comments(
        self,
        issues: list[ReviewIssue],
    ) -> tuple[list[dict[str, str | int]], list[ReviewIssue]]:
        comments: list[dict[str, str | int]] = []
        general_comments: list[ReviewIssue] = []

        for issue in issues:
            if issue.line is None:
                general_comments.append(issue)
                continue
            comments.append(
                {
                    "path": issue.file,
                    "line": issue.line,
                    "side": "RIGHT",
                    "body": self.format_issue_body(issue),
                }
            )

        return comments, general_comments

    @classmethod
    def format_issue_body(cls, issue: ReviewIssue) -> str:
        """Format one issue as a tidy Markdown review comment."""

        title = cls._severity_title(issue.severity)
        return (
            f"### {title}\n\n"
            f"**Type:** {issue.type}\n"
            f"**Message:** {issue.message}\n\n"
            "> *Generated by pr-review-agent*"
        )

    @classmethod
    def format_general_comment(cls, issues: list[ReviewIssue]) -> str:
        """Format non-inline or fallback findings as a PR-level comment."""

        blocks = []
        for issue in issues:
            location = issue.file if issue.line is None else f"{issue.file}:{issue.line}"
            blocks.append(f"**Location:** `{location}`\n\n{cls.format_issue_body(issue)}")
        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _severity_title(severity: str) -> str:
        return {
            "critical": "Critical Risk",
            "high": "High Risk",
            "medium": "Medium Warning",
            "low": "Low Notice",
        }.get(severity.lower(), "Low Notice")

    @classmethod
    def _coerce_issue(cls, raw_issue: ReviewIssue | Mapping[str, Any] | BaseModel) -> ReviewIssue | None:
        if isinstance(raw_issue, ReviewIssue):
            return raw_issue
        if isinstance(raw_issue, BaseModel):
            data = raw_issue.model_dump()
        else:
            data = raw_issue
        try:
            return ReviewIssue.model_validate(data)
        except Exception:
            cls.logger.warning("Invalid GitHub issue skipped: %r", raw_issue, exc_info=True)
            return None

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        headers.update(kwargs.pop("headers", {}))

        async with httpx.AsyncClient(base_url=self.api_url, timeout=self.timeout) as client:
            response = await client.request(method, path, headers=headers, **kwargs)

        if response.status_code in {401, 403}:
            rate_remaining = response.headers.get("x-ratelimit-remaining")
            if response.status_code == 403 and rate_remaining == "0":
                raise GitHubPublisherError("GitHub API rate limit exceeded.")
            raise GitHubPublisherError("GitHub token is invalid or lacks required permissions.")

        if response.status_code == 422:
            raise GitHubPublisherError(f"GitHub rejected review comment line mapping: {response.text}")

        if response.status_code >= 400:
            raise GitHubPublisherError(f"GitHub API request failed ({response.status_code}): {response.text}")

        return response
