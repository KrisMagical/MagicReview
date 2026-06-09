"""Pull request review orchestration for GitHub App webhooks."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from tempfile import TemporaryDirectory

from app.report.cli_formatters import has_fail_on_issue
from app.reviewer import ReviewService
from reviewagent.storage import ReviewPersistenceService
from reviewagent.connected import NetworkPolicy
from reviewagent.integrations.github.client import GitHubAppClient
from reviewagent.integrations.github.commenter import GitHubCommenter
from reviewagent.integrations.github.config import GitHubAppConfig
from reviewagent.integrations.github.formatter import format_summary_comment
from reviewagent.integrations.github.models import GitHubReviewResult, PullRequestEvent


class GitHubPullRequestReviewer:
    def __init__(
        self,
        *,
        client: GitHubAppClient,
        config: GitHubAppConfig,
        review_service: ReviewService | None = None,
        commenter: GitHubCommenter | None = None,
        persistence_service: ReviewPersistenceService | None = None,
    ) -> None:
        self.client = client
        self.config = config
        self.review_service = review_service or ReviewService()
        self.commenter = commenter or GitHubCommenter(client, max_inline_comments=config.max_inline_comments)
        self.persistence_service = persistence_service

    def review_pull_request(self, event: PullRequestEvent) -> GitHubReviewResult:
        errors: list[str] = []
        try:
            self.client.get_installation_token(event.installation_id)
            diff_text = self.client.get_pull_request_diff(event.owner, event.repo, event.pull_number)
        except Exception as exc:
            return GitHubReviewResult(status="failed", errors=[f"GitHub API error: {exc}"])
        try:
            if self.config.review_mode == "full_project":
                result = self._review_full_project(event)
            else:
                result = self.review_service.review_diff(diff_text)
        except Exception as exc:
            result = {"issues": []}
            errors.append(f"ReviewService failed: {exc}")
        if self.config.save_results:
            try:
                persistence = self.persistence_service or ReviewPersistenceService()
                persistence.save_review_result(
                    result,
                    source="github",
                    target_type="pull_request",
                    target_ref=f"{event.repository_full_name}#{event.pull_number}",
                    project_name=event.repository_full_name,
                    repository_url=f"https://github.com/{event.repository_full_name}",
                    commit_sha=event.head_sha,
                    pull_request_number=event.pull_number,
                    metadata=event.metadata,
                )
            except Exception as exc:
                errors.append(f"Dashboard persistence failed: {exc}")
        try:
            published = self.commenter.publish(
                event,
                result,
                diff_text,
                summary=self.config.enable_summary_comment,
                inline=self.config.enable_inline_comments,
                errors=errors,
            )
            if self.config.fail_on:
                conclusion = "failure" if has_fail_on_issue(result, self.config.fail_on) else "success"
                self.client.create_check_run(
                    event.owner,
                    event.repo,
                    name=self.config.app_name,
                    head_sha=event.head_sha,
                    conclusion=conclusion,
                    summary=format_summary_comment(result, errors=errors),
                )
            return published
        except Exception as exc:
            return GitHubReviewResult(status="failed", issues_count=len(result.get("issues", [])), errors=[*errors, f"Comment publishing failed: {exc}"])

    @staticmethod
    def from_config(config: GitHubAppConfig) -> "GitHubPullRequestReviewer":
        client = GitHubAppClient(app_id=config.app_id, private_key=config.private_key)
        return GitHubPullRequestReviewer(client=client, config=config)

    def _review_full_project(self, event: PullRequestEvent) -> dict[str, Any]:
        with TemporaryDirectory(prefix="reviewagent-pr-") as temp_dir:
            root = Path(temp_dir)
            for item in self.client.list_pull_request_files(event.owner, event.repo, event.pull_number):
                filename = str(item.get("filename", ""))
                if not filename.endswith(".py"):
                    continue
                content = item.get("content")
                if content is None and item.get("raw_url"):
                    content = self.client.get_url_text(str(item["raw_url"]))
                if content is None and item.get("patch"):
                    content = self._content_from_patch(str(item["patch"]))
                if content is None:
                    continue
                target = root / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(content), encoding="utf-8")
            return self.review_service.review_project(
                str(root),
                enable_llm=self.config.enable_llm,
                config_path=self.config.config_path,
                enable_agents=self.config.enable_agents,
                network_policy=NetworkPolicy(
                    enabled=False,
                    allow_llm=False,
                    allow_github_api=True,
                    code_sharing_mode="none",
                ),
            )

    @staticmethod
    def _content_from_patch(patch: str) -> str:
        lines = []
        for line in patch.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(line[1:])
            elif line.startswith(" ") and not line.startswith("@@"):
                lines.append(line[1:])
        return "\n".join(lines) + ("\n" if lines else "")
