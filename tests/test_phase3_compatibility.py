from pathlib import Path

from app.analyzers.ruff_adapter import RuffAdapter
from app.reviewer import ProjectReviewer, ReviewService


def test_review_project_survives_missing_ruff(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def run(a):\n    return a + 42\n", encoding="utf-8")
    reviewer = ProjectReviewer(ruff_adapter=RuffAdapter(ruff_executable="ruff-missing"))
    service = ReviewService(project_reviewer=reviewer)

    result = service.review_project(str(tmp_path))

    assert "issues" in result


def test_review_project_survives_missing_radon(tmp_path: Path, monkeypatch) -> None:
    import app.analyzers.complexity_analyzer as complexity_analyzer

    (tmp_path / "a.py").write_text("def run(a):\n    return a + 42\n", encoding="utf-8")
    monkeypatch.setattr(complexity_analyzer, "ComplexityVisitor", None)
    monkeypatch.setattr(complexity_analyzer, "mi_visit", None)

    result = ReviewService().review_project(str(tmp_path))

    assert "issues" in result


def test_review_project_survives_missing_networkx(tmp_path: Path, monkeypatch) -> None:
    import app.analyzers.dependency_analyzer as dependency_analyzer

    (tmp_path / "a.py").write_text("def run(a):\n    return a + 42\n", encoding="utf-8")
    monkeypatch.setattr(dependency_analyzer, "nx", None)

    result = ReviewService().review_project(str(tmp_path))

    assert "issues" in result


def test_review_project_does_not_execute_project_code(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    (tmp_path / "danger.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )

    ReviewService().review_project(str(tmp_path))

    assert not marker.exists()
