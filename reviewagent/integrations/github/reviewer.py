"""Pull request review orchestration for GitHub App webhooks."""

from __future__ import annotations

from typing import Any

from app.report.cli_formatters import has_fail_on_issue
from app.reviewer import ReviewService
from reviewagent.storage import ReviewPersistenceService
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
