from textwrap import dedent

from app.analyzers.complexity_analyzer import ComplexityAnalyzer


def test_radon_adapter_flags_high_complexity_function() -> None:
    source = dedent(
        """
        def process(value: int) -> int:
            total = 0
            if value > 0: total += 1
            if value > 1: total += 1
            if value > 2: total += 1
            if value > 3: total += 1
            if value > 4: total += 1
            if value > 5: total += 1
            if value > 6: total += 1
            if value > 7: total += 1
            if value > 8: total += 1
            if value > 9: total += 1
            if value > 10: total += 1
            if value > 11: total += 1
            if value > 12: total += 1
            if value > 13: total += 1
            return total
        """
    ).lstrip()

    issues = ComplexityAnalyzer().analyze_file("app/service.py", source)

    assert any(issue.type == "CyclomaticComplexity" for issue in issues)


def test_radon_adapter_flags_low_maintainability_index() -> None:
    branches = "\n".join(f"    if value > {index}: total += {index}" for index in range(80))
    source = f"def hard_to_maintain(value: int) -> int:\n    total = 0\n{branches}\n    return total\n"

    issues = ComplexityAnalyzer(min_maintainability_medium=100).analyze_file("app/service.py", source)

    assert any(issue.type == "MaintainabilityIndex" for issue in issues)


def test_radon_adapter_handles_syntax_error() -> None:
    issues = ComplexityAnalyzer().analyze_file("broken.py", "def broken(:\n")

    assert issues[0].type == "ParseError"
    assert issues[0].file == "broken.py"
