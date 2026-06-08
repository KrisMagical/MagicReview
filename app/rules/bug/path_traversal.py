"""Rule for detecting insecure user-controlled file paths."""

from __future__ import annotations

import ast

from app.rules.base import BaseRule, Issue, RuleContext, make_issue


class PathTraversalRule(BaseRule):
    """Detect path operations using untrusted function or request input."""

    name = "PathTraversalRule"
    category = "security"
    safe_wrappers = {"safe_join", "secure_filename", "resolve_workspace_path"}
    sensitive_calls = {
        "open",
        "send_file",
        "Path",
        "pathlib.Path",
        "os.path.join",
        "os.path.abspath",
        "os.path.normpath",
    }

    def check(self, context: RuleContext) -> list[Issue]:
        if context.tree is None:
            return []
        untrusted = self._untrusted_names(context.tree)
        issues: list[Issue] = []
        for node in ast.walk(context.tree):
            if isinstance(node, ast.Call) and self._call_name(node.func) in self.sensitive_calls:
                args = node.args if self._call_name(node.func) != "os.path.join" else node.args[1:]
                if any(self._uses_untrusted(arg, untrusted) for arg in args) and not any(
                    self._is_safely_wrapped(arg) for arg in args
                ):
                    issues.append(self._issue(context.file_path, getattr(node, "lineno", 1)))
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                if self._looks_like_path_base(node.left) and self._uses_untrusted(node.right, untrusted):
                    issues.append(self._issue(context.file_path, getattr(node, "lineno", 1)))
        return issues

    @staticmethod
    def _issue(file_path: str, line: int) -> Issue:
        return make_issue(
            severity="high",
            issue_type="PathTraversalRule",
            file_path=file_path,
            line=line,
            message="Path traversal risk.",
            suggestion="Validate and normalize user-controlled paths, and restrict access to an allowed base directory.",
        )

    @classmethod
    def _untrusted_names(cls, tree: ast.AST) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.update(arg.arg for arg in node.args.args)
                names.update(arg.arg for arg in node.args.kwonlyargs)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call_name = cls._call_name(node.value.func)
                if call_name in {"input", "request.args.get", "request.form.get", "request.json.get"}:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            names.add(target.id)
        return names

    @classmethod
    def _uses_untrusted(cls, node: ast.AST, untrusted: set[str]) -> bool:
        if isinstance(node, ast.Name):
            return node.id in untrusted
        if isinstance(node, ast.Attribute):
            return cls._root_name(node) in {"request"} or cls._root_name(node) in untrusted
        if isinstance(node, ast.Subscript):
            return cls._uses_untrusted(node.value, untrusted)
        if isinstance(node, ast.JoinedStr):
            return any(cls._uses_untrusted(child, untrusted) for child in ast.walk(node))
        if isinstance(node, ast.BinOp):
            return cls._uses_untrusted(node.left, untrusted) or cls._uses_untrusted(node.right, untrusted)
        if isinstance(node, ast.Call):
            return any(cls._uses_untrusted(arg, untrusted) for arg in node.args)
        return False

    @classmethod
    def _is_safely_wrapped(cls, node: ast.AST) -> bool:
        return isinstance(node, ast.Call) and cls._call_name(node.func) in cls.safe_wrappers

    @classmethod
    def _looks_like_path_base(cls, node: ast.AST) -> bool:
        if isinstance(node, ast.Call):
            return cls._call_name(node.func) in {"Path", "pathlib.Path"}
        if isinstance(node, ast.Name):
            return node.id.lower() in {"base", "base_dir", "root", "root_dir", "path", "safe_path"}
        return False

    @classmethod
    def _call_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = cls._call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    @classmethod
    def _root_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return cls._root_name(node.value)
        return ""
