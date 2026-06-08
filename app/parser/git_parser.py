"""Helpers for retrieving git diff text."""

from __future__ import annotations

import sys
from pathlib import Path


def get_git_diff(repo_path: str, target_sha: str | None = None) -> str:
    """Return raw git diff text for a repository.

    When ``target_sha`` is omitted, the function returns the current working tree
    diff, including staged and unstaged changes. When it is provided, the diff is
    calculated from that target ref to the current ``HEAD``.
    """
    try:
        from git import Repo
        from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError
    except ImportError as exc:
        raise RuntimeError("GitPython is required to read git diffs.") from exc

    try:
        repo = Repo(repo_path)
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise ValueError(f"Invalid git repository: {repo_path}") from exc

    try:
        if target_sha:
            return repo.git.diff(target_sha, "HEAD")

        staged_diff = repo.git.diff("--cached")
        unstaged_diff = repo.git.diff()
        return "\n".join(part for part in (staged_diff, unstaged_diff) if part)
    except GitCommandError as exc:
        raise RuntimeError(f"Failed to get git diff: {exc}") from exc


def get_diff_from_stdin() -> str:
    """Read diff text from standard input."""
    return sys.stdin.read()


def get_diff_from_file(file_path: str | Path) -> str:
    """Read diff text from a UTF-8 file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Diff file not found: {file_path}")
    return path.read_text(encoding="utf-8")
