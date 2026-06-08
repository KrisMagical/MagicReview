import json

from app.report.formatter import ReportFormatter, ReviewIssue
from app.rules.base import Issue


def test_report_formatter_merges_sources_and_keeps_highest_severity() -> None:
    report = ReportFormatter.merge_review_results(
        ast_issues=[
            {
                "severity": "medium",
                "type": "magic_number",
                "file": "service.py",
                "line": 10,
                "message": "Magic Number: 3",
            }
        ],
        complexity_issues=[
            Issue(
                severity="high",
                type="cyclomatic_complexity",
                file="service.py",
                line=12,
                message="Function complexity too high",
            )
        ],
        ruff_issues=[
            ReviewIssue(
                severity="low",
                type="import_order",
                file="service.py",
                line=2,
                column=1,
                message="[I001] Import block is un-sorted or un-formatted",
                rule_id="I001",
            )
        ],
        changed_lines_per_file={"service.py": {2, 10, 12}},
    )

    assert [issue.type for issue in report.issues] == [
        "cyclomatic_complexity",
        "magic_number",
        "import_order",
    ]


def test_report_formatter_to_json_omits_none_fields() -> None:
    payload = ReportFormatter.to_json(
        [
            {
                "severity": "low",
                "type": "code_style",
                "file": "service.py",
                "line": 3,
                "message": "Style issue",
            }
        ]
    )

    assert json.loads(payload) == {
        "issues": [
            {
                "severity": "low",
                "type": "code_style",
                "file": "service.py",
                "line": 3,
                "message": "Style issue",
            }
        ]
    }
