from pathlib import Path

from app.reviewer import ReviewService


def test_review_service_file_diff_and_project_return_issues_key(tmp_path: Path) -> None:
    target = tmp_path / "bad.py"
    target.write_text("def run(a):\n    return a + 42\n", encoding="utf-8")

    service = ReviewService()

    assert "issues" in service.review_file(str(target))
    assert "issues" in service.review_project(str(tmp_path))
    assert "issues" in service.review_diff(
        "diff --git a/bad.py b/bad.py\n"
        "--- a/bad.py\n"
        "+++ b/bad.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def run(a):\n"
        "+    return a + 42\n"
    )


def test_review_service_missing_paths_and_empty_diff_are_safe(tmp_path: Path) -> None:
    service = ReviewService()

    file_result = service.review_file(str(tmp_path / "missing.py"))
    project_result = service.review_project(str(tmp_path / "missing"))
    diff_result = service.review_diff("")

    assert file_result["issues"][0]["type"] == "ReviewError"
    assert project_result["issues"][0]["type"] == "ReviewError"
    assert diff_result == {"issues": []}


def test_review_service_limits_large_diff() -> None:
    service = ReviewService()
    service.max_diff_size_bytes = 8

    result = service.review_diff("diff --git a/a.py b/a.py\n")

    assert result["issues"][0]["type"] == "DiffTooLarge"


def test_review_service_does_not_import_reviewed_file(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    target = tmp_path / "danger.py"
    target.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )

    ReviewService().review_file(str(target))

    assert not marker.exists()
