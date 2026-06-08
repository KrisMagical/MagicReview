"""Unified review report models and formatting helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.rules.base import Issue


Severity = Literal["critical", "high", "medium", "low"]


class ReviewIssue(BaseModel):
    """Public issue schema shared by Rule Engine, analyzers, Ruff, and LLM."""

    model_config = ConfigDict(extra="ignore")

    severity: Severity
    type: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    message: str = Field(min_length=1)
    suggestion: str | None = Field(default=None, min_length=1)
    rule_id: str | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower()
        return value

    def to_dict(self) -> dict[str, Any]:
        """Compatibility helper used by older callers."""

        return self.model_dump(exclude_none=True)


class ReviewReport(BaseModel):
    """Top-level JSON report schema."""

    issues: list[ReviewIssue] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2, exclude_none=True)


IssueLike: TypeAlias = ReviewIssue | Issue | Mapping[str, Any] | BaseModel


class ReportFormatter:
    """Merge, deduplicate, filter, sort, and serialize review issues."""

    SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    logger = logging.getLogger(__name__)

    @classmethod
    def merge_review_results(
        cls,
        *,
        ast_issues: Iterable[IssueLike] | None = None,
        complexity_issues: Iterable[IssueLike] | None = None,
        ruff_issues: Iterable[IssueLike] | None = None,
        llm_issues: Iterable[IssueLike] | None = None,
        changed_lines_per_file: Mapping[str, Iterable[int]] | None = None,
        context_lines: int = 0,
    ) -> ReviewReport:
        """Merge AST, Radon, Ruff, and optional LLM results into one report."""

        issue_groups = [
            ast_issues or [],
            complexity_issues or [],
            ruff_issues or [],
            llm_issues or [],
        ]
        merged = cls.merge_and_filter(
            issue_groups,
            changed_lines_per_file=dict(changed_lines_per_file or {}),
            context_lines=context_lines,
        )
        return ReviewReport(issues=merged)

    @classmethod
    def merge_and_filter(
        cls,
        issues_list: Sequence[Iterable[IssueLike]],
        changed_lines_per_file: Mapping[str, Iterable[int]] | None = None,
        context_lines: int = 0,
    ) -> list[ReviewIssue]:
        """Merge multiple issue sources, deduplicate, and keep changed-line issues.

        Deduplication uses ``file + line + type + rule_id``. When two findings
        collide, the higher-severity finding wins.
        """

        changed_lines = cls._normalize_changed_lines(changed_lines_per_file or {})
        unique: dict[tuple[str, int | None, str, str | None], ReviewIssue] = {}

        for issues in issues_list:
            for raw_issue in issues:
                issue = cls._coerce_issue(raw_issue)
                if issue is None:
                    continue
                if changed_lines and not cls._is_on_changed_line(issue, changed_lines, context_lines):
                    continue

                key = (issue.file, issue.line, issue.type, issue.rule_id)
                existing = unique.get(key)
                if existing is None or cls._severity_rank(issue) < cls._severity_rank(existing):
                    unique[key] = issue

        return sorted(
            unique.values(),
            key=lambda item: (cls._severity_rank(item), item.file, item.line or 0, item.column or 0, item.type),
        )

    @classmethod
    def to_json(cls, issues: Iterable[IssueLike] | ReviewReport) -> str:
        """Serialize issues or a prepared report to standard JSON."""

        if isinstance(issues, ReviewReport):
            return issues.to_json()

        normalized = [issue for raw in issues if (issue := cls._coerce_issue(raw)) is not None]
        return ReviewReport(issues=normalized).to_json()

    @classmethod
    def to_dict(cls, issues: Iterable[IssueLike] | ReviewReport) -> dict[str, Any]:
        """Return a JSON-serializable report dictionary."""

        if isinstance(issues, ReviewReport):
            return issues.model_dump(exclude_none=True)

        normalized = [issue for raw in issues if (issue := cls._coerce_issue(raw)) is not None]
        return ReviewReport(issues=normalized).model_dump(exclude_none=True)

    @classmethod
    def _coerce_issue(cls, raw_issue: IssueLike) -> ReviewIssue | None:
        if isinstance(raw_issue, ReviewIssue):
            return raw_issue

        if isinstance(raw_issue, Issue):
            data: Mapping[str, Any] = raw_issue.to_dict()
        elif isinstance(raw_issue, BaseModel):
            data = raw_issue.model_dump()
        elif isinstance(raw_issue, Mapping):
            data = raw_issue
        else:
            cls.logger.warning("Unsupported issue object skipped: %r", raw_issue)
            return None

        try:
            return ReviewIssue.model_validate(data)
        except ValidationError:
            cls.logger.warning("Invalid issue skipped: %r", data, exc_info=True)
            return None

    @classmethod
    def _normalize_changed_lines(cls, changed_lines_per_file: Mapping[str, Iterable[int]]) -> dict[str, set[int]]:
        normalized: dict[str, set[int]] = {}
        for file_path, raw_lines in changed_lines_per_file.items():
            normalized[str(file_path)] = {line for line in raw_lines if isinstance(line, int) and line > 0}
        return normalized

    @classmethod
    def _is_on_changed_line(
        cls,
        issue: ReviewIssue,
        changed_lines_per_file: Mapping[str, set[int]],
        context_lines: int,
    ) -> bool:
        lines = changed_lines_per_file.get(issue.file)
        if issue.line is None:
            return True
        if not lines:
            return False
        if context_lines <= 0:
            return issue.line in lines
        return any(abs(issue.line - changed_line) <= context_lines for changed_line in lines)

    @classmethod
    def _severity_rank(cls, issue: ReviewIssue) -> int:
        return cls.SEVERITY_ORDER.get(issue.severity, cls.SEVERITY_ORDER["low"])
