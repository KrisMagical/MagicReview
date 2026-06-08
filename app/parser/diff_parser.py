"""Parse unified git diff text into Python file line changes."""

from __future__ import annotations

import re
from dataclasses import dataclass


AddedLine = tuple[int, str]
ParsedDiffItem = dict[str, str | list[AddedLine]]


@dataclass(frozen=True)
class Change:
    """A single added line in the target file."""

    line_num: int
    content: str
    change_type: str = "add"


@dataclass(frozen=True)
class FileDiff:
    """Changed line data for one file."""

    file_path: str
    added_lines: list[AddedLine]

    @property
    def changes(self) -> list[Change]:
        return [Change(line_num=line_num, content=content) for line_num, content in self.added_lines]

    @property
    def all_changed_lines(self) -> list[int]:
        return [line_num for line_num, _ in self.added_lines]


class DiffParser:
    """Parser for standard unified git diff output."""

    HUNK_HEADER_PATTERN = re.compile(
        r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
        r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
    )

    @classmethod
    def parse_added_lines(cls, diff_text: str) -> list[ParsedDiffItem]:
        """Return Python files and their added target-file lines from git diff text."""
        if not diff_text.strip():
            return []

        parsed_files: list[ParsedDiffItem] = []
        lines = diff_text.splitlines()
        index = 0

        while index < len(lines):
            if not lines[index].startswith("diff --git ") and not lines[index].startswith("--- "):
                index += 1
                continue

            next_file_index = cls._find_next_file_header(lines, index + 1)
            file_block = lines[index:next_file_index]
            file_path = cls._extract_target_path(file_block)

            if file_path is not None and file_path.endswith(".py"):
                added_lines = cls._parse_file_block_added_lines(file_block)
                if added_lines:
                    parsed_files.append({"file": file_path, "added_lines": added_lines})

            index = next_file_index

        return parsed_files

    @classmethod
    def parse(cls, diff_text: str) -> dict[str, FileDiff]:
        """Return a mapping kept for existing analyzer code in this project."""
        parsed = cls.parse_added_lines(diff_text)
        return {
            item["file"]: FileDiff(file_path=item["file"], added_lines=item["added_lines"])
            for item in parsed
            if isinstance(item["file"], str) and isinstance(item["added_lines"], list)
        }

    @classmethod
    def _parse_file_block_added_lines(cls, file_block: list[str]) -> list[AddedLine]:
        added_lines: list[AddedLine] = []
        index = 0

        while index < len(file_block):
            hunk_match = cls.HUNK_HEADER_PATTERN.match(file_block[index])
            if hunk_match is None:
                index += 1
                continue

            new_line_number = int(hunk_match.group("new_start"))
            index += 1

            while index < len(file_block) and not file_block[index].startswith("@@ "):
                raw_line = file_block[index]

                if raw_line.startswith("\\"):
                    index += 1
                    continue

                if raw_line.startswith("+"):
                    added_lines.append((new_line_number, raw_line[1:]))
                    new_line_number += 1
                elif raw_line.startswith("-"):
                    pass
                else:
                    new_line_number += 1

                index += 1

        return added_lines

    @staticmethod
    def _find_next_file_header(lines: list[str], start_index: int) -> int:
        index = start_index
        while index < len(lines) and not lines[index].startswith("diff --git "):
            if lines[index].startswith("--- ") and any(
                candidate.startswith("@@ ") for candidate in lines[index + 1 : index + 4]
            ):
                break
            index += 1
        return index

    @classmethod
    def _extract_target_path(cls, file_block: list[str]) -> str | None:
        """Extract the new file path, skipping deleted or malformed file blocks."""
        for line in file_block:
            if not line.startswith("+++ "):
                continue

            path = cls._normalize_diff_path(line[4:].strip())
            if path == "/dev/null":
                return None
            return path

        return None

    @staticmethod
    def _normalize_diff_path(path: str) -> str:
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1].replace('\\"', '"')

        if path.startswith("b/"):
            return path[2:]

        return path


def build_changed_source(added_lines: list[AddedLine]) -> str:
    """Build a sparse source snippet that preserves target line numbers."""

    if not added_lines:
        return ""
    max_line = max(line for line, _content in added_lines)
    lines = [""] * max_line
    for line_number, content in added_lines:
        if line_number > 0:
            lines[line_number - 1] = content
    return "\n".join(lines) + "\n"


def parse_diff(diff_text: str) -> list[ParsedDiffItem]:
    """Parse git diff text into the phase-two target output structure."""
    return DiffParser.parse_added_lines(diff_text)
