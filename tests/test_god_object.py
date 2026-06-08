from app.rules.architecture import GodObjectDetector


def test_god_object_detects_god_file() -> None:
    source = "\n".join(f"def func_{index}():\n    return {index}" for index in range(30))

    issues = GodObjectDetector(god_file_max_functions=30).analyze_file("large.py", source)

    assert any(issue.type == "GodFile" for issue in issues)


def test_god_object_detects_god_class() -> None:
    methods = "\n".join(f"    def method_{index}(self):\n        return {index}" for index in range(20))
    source = f"class BigService:\n{methods}\n"

    issues = GodObjectDetector(god_class_max_methods=20).analyze_file("service.py", source)

    assert any(issue.type == "GodClass" for issue in issues)


def test_god_object_ignores_small_class() -> None:
    source = "class Small:\n    def run(self):\n        return 1\n"

    issues = GodObjectDetector().analyze_file("small.py", source)

    assert issues == []
