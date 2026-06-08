from pathlib import Path

from app.analyzers.dependency_analyzer import DependencyAnalyzer


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_import_graph_detects_internal_cycle_and_ignores_external_imports(tmp_path: Path) -> None:
    write(tmp_path / "pkg" / "__init__.py", "")
    write(tmp_path / "pkg" / "a.py", "import os\nfrom pkg import b\n")
    write(tmp_path / "pkg" / "b.py", "import requests\nfrom pkg import a\n")

    analyzer = DependencyAnalyzer(tmp_path)
    graph = analyzer.build_graph()
    issues = analyzer.detect_cycles(graph)

    assert "os" not in graph.nodes
    assert "requests" not in graph.nodes
    assert any(issue.type == "CircularDependency" for issue in issues)


def test_import_graph_detects_high_coupling(tmp_path: Path) -> None:
    write(tmp_path / "pkg" / "__init__.py", "")
    imports = []
    for index in range(3):
        write(tmp_path / "pkg" / f"dep_{index}.py", "")
        imports.append(f"from pkg import dep_{index}")
    write(tmp_path / "pkg" / "hub.py", "\n".join(imports))

    analyzer = DependencyAnalyzer(tmp_path, outgoing_threshold=3)
    issues = analyzer.detect_high_coupling(analyzer.build_graph())

    assert any(issue.type == "HighModuleCoupling" for issue in issues)
