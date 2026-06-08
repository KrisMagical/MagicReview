from pathlib import Path

import pytest

from app import main


def test_read_file_content_rejects_parent_path_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "WORKSPACE_ROOT", tmp_path.resolve())

    with pytest.raises(ValueError, match="Unsafe path traversal detected"):
        main.read_file_content("../secret.py")


def test_read_file_content_rejects_absolute_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "WORKSPACE_ROOT", tmp_path.resolve())

    with pytest.raises(ValueError, match="Unsafe path traversal detected"):
        main.read_file_content(str((tmp_path / "service.py").resolve()))


def test_read_file_content_allows_workspace_relative_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "WORKSPACE_ROOT", tmp_path.resolve())
    service_file = tmp_path / "app" / "service.py"
    service_file.parent.mkdir()
    service_file.write_text("value = 1\n", encoding="utf-8")

    assert main.read_file_content(Path("app") / "service.py") == "value = 1\n"
