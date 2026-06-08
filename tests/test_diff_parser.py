from app.parser.diff_parser import DiffParser, parse_diff


def test_parse_diff_tracks_added_line_numbers_across_multiple_hunks() -> None:
    diff_text = """diff --git a/app/user.py b/app/user.py
index 1111111..2222222 100644
--- a/app/user.py
+++ b/app/user.py
@@ -10,6 +10,8 @@ def get_user(id):
 context_before()
 old_value = 1
+user = get_user(id)
+print(user.name)
 context_after()
@@ -30,5 +32,7 @@ def update_user(user):
 keep_this()
-remove_this()
+name = user.name
 still_context()
+return name
"""

    result = parse_diff(diff_text)

    assert result == [
        {
            "file": "app/user.py",
            "added_lines": [
                (12, "user = get_user(id)"),
                (13, "print(user.name)"),
                (33, "name = user.name"),
                (35, "return name"),
            ],
        }
    ]


def test_parse_diff_keeps_only_python_files() -> None:
    diff_text = """diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
 hello
+ignored
diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -1 +1,2 @@
 def run():
+    return True
"""

    result = parse_diff(diff_text)

    assert result == [{"file": "app/service.py", "added_lines": [(2, "    return True")]}]


def test_parse_diff_handles_new_deleted_and_binary_files_without_crashing() -> None:
    diff_text = """diff --git a/app/new_file.py b/app/new_file.py
new file mode 100644
index 0000000..2222222
--- /dev/null
+++ b/app/new_file.py
@@ -0,0 +1,2 @@
+def created():
+    return 1
diff --git a/app/deleted.py b/app/deleted.py
deleted file mode 100644
index 1111111..0000000
--- a/app/deleted.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def deleted():
-    return 1
diff --git a/app/image.py b/app/image.py
index 1111111..2222222 100644
Binary files a/app/image.py and b/app/image.py differ
"""

    result = parse_diff(diff_text)

    assert result == [{"file": "app/new_file.py", "added_lines": [(1, "def created():"), (2, "    return 1")]}]


def test_diff_parser_parse_keeps_existing_mapping_api() -> None:
    diff_text = """diff --git a/app/user.py b/app/user.py
index 1111111..2222222 100644
--- a/app/user.py
+++ b/app/user.py
@@ -1 +1,2 @@
 def run():
+    pass
"""

    result = DiffParser.parse(diff_text)

    assert list(result) == ["app/user.py"]
    assert result["app/user.py"].all_changed_lines == [2]
    assert result["app/user.py"].changes[0].content == "    pass"
