import pytest

from app.llm.reviewer import (
    LLMIssue,
    LLMInfrastructureError,
    LLMReviewer,
    LLMReviewReport,
    llm_review_code,
)
from app.llm.prompts import USER_PROMPT_TEMPLATE
from app.report.formatter import ReportFormatter


def test_parse_report_text_accepts_markdown_json_block() -> None:
    text = """```json
{
  "issues": [
    {
      "severity": "HIGH",
      "type": "security",
      "file": "app/user.py",
      "line": 12,
      "message": "Dynamic SQL is built from request data.",
      "suggestion": "Use parameterized ORM filters instead of string concatenation."
    }
  ]
}
```"""

    report = LLMReviewer._parse_report_text(text)

    assert len(report.issues) == 1
    assert report.issues[0].severity == "high"
    assert report.issues[0].type == "sql_injection"
    assert report.issues[0].suggestion.startswith("Use parameterized")


def test_parse_report_text_accepts_direct_json_without_suggestion() -> None:
    text = """{
  "issues": [
    {
      "severity": "HIGH",
      "type": "sql_injection",
      "file": "app/user.py",
      "line": 12,
      "message": "Dynamic SQL is built from request data; use parameter binding."
    }
  ]
}"""

    report = LLMReviewer._parse_report_text(text)

    assert len(report.issues) == 1
    assert report.issues[0].severity == "high"
    assert report.issues[0].type == "sql_injection"
    assert report.issues[0].suggestion is None


def test_parse_report_text_accepts_empty_markdown_json_report() -> None:
    report = LLMReviewer._parse_report_text("""```json
{"issues": []}
```""")

    assert report.issues == []


def test_user_prompt_template_has_clear_review_sections() -> None:
    prompt = USER_PROMPT_TEMPLATE.format(git_diff="+value = 1", context="value = 1")

    assert "### Project Type" in prompt
    assert "### Git Diff" in prompt
    assert "### Related Context" in prompt
    assert "### Review Request" in prompt
    assert "### Git Diff " not in prompt


def test_system_prompt_requires_direct_json_object() -> None:
    from app.llm.prompts import SYSTEM_PROMPT

    assert "Return a valid JSON object directly" in SYSTEM_PROMPT
    assert "Do not use Markdown fences" in SYSTEM_PROMPT
    assert "response_model" in SYSTEM_PROMPT
    assert "potential_none_type" in SYSTEM_PROMPT


def test_parse_report_text_rejects_out_of_scope_issue_type() -> None:
    text = """{
  "issues": [
    {
      "severity": "low",
      "type": "naming",
      "file": "app/user.py",
      "line": 12,
      "message": "Bad name.",
      "suggestion": "Rename it."
    }
  ]
}"""

    report = LLMReviewer._parse_report_text(text)

    assert report.issues == []


def test_parse_report_text_keeps_valid_items_when_one_issue_is_invalid() -> None:
    text = """{
  "issues": [
    {
      "severity": "high",
      "type": "naming",
      "file": "app/user.py",
      "line": 12,
      "message": "Bad name.",
      "suggestion": "Rename it."
    },
    {
      "severity": "MEDIUM",
      "type": "Potential_None_Type",
      "file": "app/user.py",
      "line": 13,
      "message": "Boundary condition is missing.",
      "suggestion": "Validate the empty input before using it."
    }
  ]
}"""

    report = LLMReviewer._parse_report_text(text)

    assert len(report.issues) == 1
    assert report.issues[0].severity == "medium"
    assert report.issues[0].type == "potential_none_type"


def test_filter_report_to_changed_lines_snaps_to_nearest_added_diff_line() -> None:
    diff_text = """diff --git a/app/user.py b/app/user.py
--- a/app/user.py
+++ b/app/user.py
@@ -10,2 +10,4 @@
 def get_user():
+    query = f"select * from users where id = {user_id}"
+    return query
     log_query(query)
"""
    report = LLMReviewReport(
        issues=[
            LLMIssue(
                severity="high",
                type="sql_injection",
                file="app/user.py",
                line=13,
                message="Dynamic SQL is built from request data.",
                suggestion="Use parameterized ORM filters.",
            ),
            LLMIssue(
                severity="medium",
                type="key_error",
                file="app/other.py",
                line=12,
                message="Unchanged file should not be reported.",
                suggestion="Report only changed files.",
            ),
        ]
    )

    filtered = LLMReviewer._filter_report_to_changed_lines(report, diff_text)

    assert len(filtered.issues) == 1
    assert filtered.issues[0].line == 12


def test_parse_report_text_invalid_json_fails_closed() -> None:
    with pytest.raises(LLMInfrastructureError):
        LLMReviewer._parse_report_text("not json")


def test_llm_review_code_returns_strict_report_schema() -> None:
    class FakeReviewer:
        def review(self, git_diff: str, context: str = ""):
            return [
                {
                    "severity": "low",
                    "type": "fastapi_response_model",
                    "file": "app/api.py",
                    "line": 3,
                    "message": "Route returns a raw response; wrap responses in the project response envelope.",
                }
            ]

    report = llm_review_code("diff", reviewer=FakeReviewer())

    assert isinstance(report, LLMReviewReport)
    assert report.issues[0].type == "fastapi_response_model"
    assert report.issues[0].suggestion is None


def test_report_formatter_preserves_llm_suggestion() -> None:
    payload = ReportFormatter.to_dict(
        [
            {
                "severity": "medium",
                "type": "fat_controller",
                "file": "app/api.py",
                "line": 20,
                "message": "Route handler mixes validation and order state transitions.",
                "suggestion": "Move order state transitions into an OrderService method.",
            }
        ]
    )

    assert payload["issues"][0]["suggestion"] == "Move order state transitions into an OrderService method."
