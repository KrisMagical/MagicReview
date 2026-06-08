"""LangGraph-backed semantic review stage."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.parser.diff_parser import DiffParser
from app.report.formatter import ReviewIssue
from app.rules.base import Issue


LLMSeverity = Literal["critical", "high", "medium", "low"]
LLMStatus = Literal["success", "failed"]
LLMIssueType = Literal[
    "srp",
    "fat_controller",
    "data_access_layer",
    "god_class",
    "potential_none_type",
    "key_error",
    "index_error",
    "zero_division",
    "resource_leak",
    "sql_injection",
    "path_traversal",
    "response_model",
    "pydantic_validation",
    "dependency_injection",
    "fastapi_response_model",
    "fastapi_depends_misuse",
    "pydantic_missing_constraints",
    "function_too_long",
    "too_many_arguments",
    "magic_number",
    "missing_type_hint",
    "file_leak",
    "parse_failure",
]


class LLMInfrastructureError(RuntimeError):
    """Raised when the semantic review stage cannot be trusted."""


class LLMIssue(BaseModel):
    """Strict issue schema expected from the semantic review model."""

    model_config = ConfigDict(extra="ignore")

    severity: LLMSeverity
    type: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line: int | None = Field(default=None, ge=1)
    message: str = Field(min_length=1)
    suggestion: str | None = Field(default=None, min_length=1)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower()
        return value

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.lower()
            legacy_type_map = {
                "security": "sql_injection",
                "logic_bug": "potential_none_type",
                "fastapi_spec": "response_model",
                "response_model": "fastapi_response_model",
                "dependency_injection": "fastapi_depends_misuse",
                "pydantic_validation": "pydantic_missing_constraints",
            }
            normalized = legacy_type_map.get(normalized, normalized)
            if normalized == "naming":
                raise ValueError("Out-of-scope LLM issue type.")
            return normalized
        return value


class LLMReviewReport(BaseModel):
    """Top-level schema for LLM review output."""

    model_config = ConfigDict(extra="ignore")

    status: LLMStatus = "success"
    error_message: str | None = None
    issues: list[LLMIssue] = Field(default_factory=list)

    @classmethod
    def failed(cls, message: str) -> "LLMReviewReport":
        return cls(status="failed", error_message=message, issues=[])


class ReviewState(TypedDict):
    """LangGraph state passed between review nodes."""

    diff_text: str
    context: str
    report: LLMReviewReport


class LLMReviewer:
    """Run semantic, architecture, and deep-risk review over a git diff."""

    logger = logging.getLogger(__name__)

    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None
        self._structured_llm = None

    def review(self, diff_text: str, context: str = "") -> list[ReviewIssue]:
        """Execute the LLM review and return issues in the public report shape."""

        graph = self.build_graph()
        initial_state: ReviewState = {
            "diff_text": diff_text,
            "context": context,
            "report": LLMReviewReport(),
        }
        final_state = graph.invoke(initial_state)
        report = self._snap_report_to_changed_lines(final_state["report"], diff_text)
        if report.status == "failed":
            raise LLMInfrastructureError(report.error_message or "LLM review failed.")
        return [
            ReviewIssue(
                severity=issue.severity,
                type=issue.type,
                file=issue.file,
                line=issue.line,
                message=issue.message,
                suggestion=issue.suggestion,
                rule_id="llm_semantic_review",
            )
            for issue in report.issues
        ]

    def review_file_context(
        self,
        *,
        file_path: str,
        source_code: str,
        ast_findings: list[Issue] | list[dict[str, Any]] | None = None,
    ) -> list[Issue]:
        """Run semantic analysis after rule-engine and AST findings.

        The first two tiers should already have produced candidate issues. This
        method asks the configured model to confirm false positives, enrich
        suggestions, and look for semantic runtime risks that AST alone cannot
        guarantee, then maps the result into the unified ``Issue`` model.
        """

        prompt = self._semantic_prompt(
            file_path=file_path,
            source_code=source_code,
            ast_findings=ast_findings or [],
        )
        report = self._invoke_structured(prompt)
        return [
            Issue(
                severity=issue.severity,
                type=issue.type,
                file=issue.file or file_path,
                line=issue.line or 1,
                message=issue.message,
                suggestion=issue.suggestion or "结合上下文确认该风险，并优先修复可触发运行时错误或安全问题的路径。",
            )
            for issue in report.issues
        ]

    def build_graph(self):
        """Build the two-node LangGraph workflow lazily."""

        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:
            raise RuntimeError("LLM review requires langgraph to be installed.") from exc

        workflow = StateGraph(ReviewState)
        workflow.add_node("prepare_prompt", self._prepare_prompt)
        workflow.add_node("call_llm", self._call_llm)
        workflow.set_entry_point("prepare_prompt")
        workflow.add_edge("prepare_prompt", "call_llm")
        workflow.add_edge("call_llm", END)
        return workflow.compile()

    def _prepare_prompt(self, state: ReviewState) -> ReviewState:
        """Keep this node explicit so future context enrichment has a stable hook."""

        return state

    def _call_llm(self, state: ReviewState) -> ReviewState:
        prompt = USER_PROMPT_TEMPLATE.format(
            git_diff=state["diff_text"],
            context=state.get("context", ""),
        )

        try:
            state["report"] = self._invoke_structured(prompt)
        except LLMInfrastructureError as exc:
            state["report"] = LLMReviewReport.failed(str(exc))
            self.logger.error("LLM review failed closed: %s", exc, exc_info=True)
            raise
        except Exception as exc:
            state["report"] = LLMReviewReport.failed(str(exc))
            self.logger.error("LLM review infrastructure failed closed.", exc_info=True)
            raise LLMInfrastructureError("LLM review infrastructure failed.") from exc

        return state

    def _invoke_structured(self, prompt: str) -> LLMReviewReport:
        """Prefer model-native structured output, then fall back to JSON parsing."""

        llm = self._get_llm()

        if hasattr(llm, "with_structured_output"):
            try:
                structured = self._get_structured_llm(llm)
                result = structured.invoke(self._messages(prompt))
                return self._coerce_report(result)
            except Exception:
                self.logger.warning("Structured output adapter failed; retrying raw JSON mode.", exc_info=True)

        result = llm.invoke(self._messages(prompt))
        content = getattr(result, "content", result)
        return self._parse_report_text(str(content))

    def _get_llm(self):
        if self._llm is None:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise RuntimeError("LLM review requires langchain-openai to be installed.") from exc

            self._llm = ChatOpenAI(model=self.model_name, temperature=self.temperature)
        return self._llm

    def _get_structured_llm(self, llm):
        if self._structured_llm is None:
            self._structured_llm = llm.with_structured_output(LLMReviewReport)
        return self._structured_llm

    @staticmethod
    def _messages(prompt: str) -> list[tuple[str, str]]:
        return [
            ("system", SYSTEM_PROMPT),
            ("human", prompt),
        ]

    @staticmethod
    def _semantic_prompt(
        *,
        file_path: str,
        source_code: str,
        ast_findings: list[Issue] | list[dict[str, Any]],
    ) -> str:
        findings_payload = [
            finding.to_dict() if isinstance(finding, Issue) else dict(finding)
            for finding in ast_findings
        ]
        return (
            "You are the Semantic Analysis tier in a three-stage Python 3.12 review pipeline.\n"
            "Input candidates already passed Rule Engine filtering and AST Analysis.\n"
            "Confirm true positives, remove false positives, and add semantic-only risks such as "
            "IndexError, KeyError, ZeroDivisionError, or business-edge cases when evidence is strong.\n"
            "Return a valid JSON object with an issues array. Each issue must contain exactly: "
            "severity, type, file, line, message, suggestion.\n\n"
            f"File: {file_path}\n\n"
            f"AST findings JSON:\n{json.dumps(findings_payload, ensure_ascii=False, indent=2)}\n\n"
            f"Source code:\n```python\n{source_code}\n```"
        )

    @classmethod
    def _coerce_report(cls, raw: Any) -> LLMReviewReport:
        if isinstance(raw, LLMReviewReport):
            return raw
        if isinstance(raw, BaseModel):
            return LLMReviewReport.model_validate(raw.model_dump())
        if isinstance(raw, dict):
            if isinstance(raw.get("issues"), list):
                return LLMReviewReport(
                    issues=[
                        issue
                        for item in raw["issues"]
                        if (issue := cls._coerce_issue(item)) is not None
                    ]
                )
            return LLMReviewReport.model_validate(raw)
        if isinstance(raw, list):
            return LLMReviewReport(
                issues=[
                    issue
                    for item in raw
                    if (issue := cls._coerce_issue(item)) is not None
                ]
            )
        return cls._parse_report_text(str(raw))

    @classmethod
    def _coerce_issue(cls, raw: Any) -> LLMIssue | None:
        try:
            return LLMIssue.model_validate(raw)
        except ValidationError:
            cls.logger.warning("Invalid LLM review issue skipped: %r", raw)
            return None

    @classmethod
    def _parse_report_text(cls, text: str) -> LLMReviewReport:
        payload = cls._extract_json_payload(text)
        try:
            data = json.loads(payload)
            return cls._coerce_report(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            cls.logger.error("Invalid LLM review JSON caused fail-closed: %r", text, exc_info=True)
            raise LLMInfrastructureError("LLM review returned invalid JSON.") from exc

    @staticmethod
    def _extract_json_payload(text: str) -> str:
        fenced = re.search(r"```(?:json|markdown)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        return text.strip()

    @staticmethod
    def _snap_report_to_changed_lines(report: LLMReviewReport, diff_text: str) -> LLMReviewReport:
        """Keep changed-file LLM findings and snap approximate lines to edits."""

        if report.status == "failed":
            return report

        changed_lines = {
            file_path: set(file_diff.all_changed_lines)
            for file_path, file_diff in DiffParser.parse(diff_text).items()
        }
        if not changed_lines:
            return LLMReviewReport()

        return LLMReviewReport(
            issues=[
                issue.model_copy(
                    update={
                        "line": (
                            None
                            if issue.line is None
                            else LLMReviewer._nearest_changed_line(issue.line, changed_lines[issue.file])
                        )
                    }
                )
                for issue in report.issues
                if issue.file in changed_lines and changed_lines[issue.file]
            ]
        )

    @staticmethod
    def _filter_report_to_changed_lines(report: LLMReviewReport, diff_text: str) -> LLMReviewReport:
        """Backward-compatible alias for the new LLM line snapping behavior."""

        return LLMReviewer._snap_report_to_changed_lines(report, diff_text)

    @staticmethod
    def _nearest_changed_line(line: int, changed_lines: set[int]) -> int:
        return min(changed_lines, key=lambda changed_line: (abs(changed_line - line), changed_line))


def llm_review_code(git_diff: str, context: str = "", reviewer: LLMReviewer | None = None) -> LLMReviewReport:
    """Phase-seven convenience API returning the strict LLM report schema."""

    active_reviewer = reviewer or LLMReviewer()
    issues: list[ReviewIssue] = []
    for raw_issue in active_reviewer.review(git_diff, context=context):
        try:
            issues.append(ReviewIssue.model_validate(raw_issue))
        except ValidationError:
            LLMReviewer.logger.warning("Invalid public LLM issue skipped: %r", raw_issue)

    return LLMReviewReport(
        issues=[
            LLMIssue(
                severity=issue.severity,
                type=issue.type,
                file=issue.file,
                line=issue.line,
                message=issue.message,
                suggestion=issue.suggestion,
            )
            for issue in issues
        ]
    )
