import json
import subprocess

from app.analyzers.ruff_adapter import RuffAdapter


def test_ruff_adapter_normalizes_and_filters_added_lines(monkeypatch) -> None:
    payload = [
        {
            "code": "F401",
            "message": "`os` imported but unused",
            "filename": "service.py",
            "location": {"row": 1, "column": 8},
        },
        {
            "code": "I001",
            "message": "Import block is un-sorted or un-formatted",
            "filename": "service.py",
            "location": {"row": 8, "column": 1},
        },
    ]

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    issues = RuffAdapter(workspace_root=".").check_file("service.py", added_lines=[(1, "import os")])

    assert len(issues) == 1
    assert issues[0].to_dict() == {
        "severity": "low",
        "type": "RuffUnusedImport",
        "file": "service.py",
        "line": 1,
        "message": "F401: `os` imported but unused",
        "suggestion": "Remove unused imports.",
    }


def test_ruff_adapter_handles_missing_binary() -> None:
    issues = RuffAdapter(ruff_executable="ruff-that-does-not-exist").check_file("service.py")

    assert issues == []


def test_ruff_adapter_rule_mappings() -> None:
    assert RuffAdapter._map_code("F401") == ("RuffUnusedImport", "low", "Remove unused imports.")
    assert RuffAdapter._map_code("F841")[0] == "RuffUnusedVariable"
    assert RuffAdapter._map_code("I001")[0] == "RuffImportOrder"
    assert RuffAdapter._map_code("N802")[0] == "RuffNaming"
    assert RuffAdapter._map_code("E501")[0] == "RuffStyle"
