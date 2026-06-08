from pathlib import Path

from app.enterprise import EnterpriseRuleConfig, EnterpriseRuleEngine


def engine(rules: dict) -> EnterpriseRuleEngine:
    normalized = {}
    for name, config in rules.items():
        normalized[name] = {"enabled": True, "severity": "medium", **config}
    return EnterpriseRuleEngine(EnterpriseRuleConfig(rules=normalized))


def types_for(rules: dict, source: str, file_path: str = "app/service.py") -> set[str]:
    return {issue.type for issue in engine(rules).run_file(file_path, source)}


def test_enterprise_max_function_length_hit_and_no_false_positive() -> None:
    source = "def long():\n    a = 1\n    b = 2\n    c = 3\n    return a + b + c\n"
    assert "EnterpriseMaxFunctionLength" in types_for({"max_function_length": {"max_lines": 3}}, source)
    assert "EnterpriseMaxFunctionLength" not in types_for({"max_function_length": {"max_lines": 10}}, source)


def test_enterprise_max_parameters_hit_and_no_false_positive() -> None:
    assert "EnterpriseMaxParameters" in types_for({"max_parameters": {"max_params": 2}}, "def run(a, b, c):\n    return a\n")
    assert "EnterpriseMaxParameters" not in types_for({"max_parameters": {"max_params": 2}}, "def run(self, a, b):\n    return a\n")


def test_enterprise_no_select_star_hit_and_no_false_positive() -> None:
    rules = {"no_select_star": {"severity": "high"}}
    assert "EnterpriseNoSelectStar" in types_for(rules, "def run(cursor):\n    cursor.execute('SELECT * FROM users')\n")
    assert "EnterpriseNoSelectStar" not in types_for(rules, "def run(cursor):\n    cursor.execute('SELECT id FROM users')\n")


def test_enterprise_no_controller_repository_hit_and_no_false_positive() -> None:
    rules = {"no_controller_repository": {"controller_patterns": ["api/"], "repository_patterns": ["repositories/"]}}
    assert "EnterpriseNoControllerRepository" in types_for(rules, "from app.repositories.user import UserRepository\n", "app/api/users.py")
    assert "EnterpriseNoControllerRepository" not in types_for(rules, "from app.repositories.user import UserRepository\n", "app/services/users.py")


def test_enterprise_service_log_required_hit_and_no_false_positive() -> None:
    rules = {"service_log_required": {"service_patterns": ["services/"], "logger_names": ["logger"]}}
    assert "EnterpriseServiceLogRequired" in types_for(rules, "def create_user(payload):\n    return {'id': payload['id']}\n", "app/services/user.py")
    assert "EnterpriseServiceLogRequired" not in types_for(rules, "def create_user(payload):\n    logger.info('create')\n    return payload\n", "app/services/user.py")


def test_enterprise_forbidden_imports_hit_and_no_false_positive() -> None:
    rules = {"forbidden_imports": {"imports": ["os.system", "subprocess.Popen"]}}
    assert "EnterpriseForbiddenImport" in types_for(rules, "import os\ndef run():\n    os.system('echo x')\n")
    assert "EnterpriseForbiddenImport" not in types_for(rules, "import os\ndef run():\n    return os.getcwd()\n")


def test_enterprise_layer_rules_hit_and_no_false_positive() -> None:
    rules = {"layer_rules": {"rules": [{"from": "api", "cannot_import": ["repositories"]}]}}
    assert "EnterpriseLayerViolation" in types_for(rules, "from app.repositories.user import UserRepository\n", "app/api/users.py")
    assert "EnterpriseLayerViolation" not in types_for(rules, "from app.services.user import UserService\n", "app/api/users.py")


def test_enterprise_project_run_uses_relative_files(tmp_path: Path) -> None:
    (tmp_path / "app" / "api").mkdir(parents=True)
    (tmp_path / "app" / "api" / "users.py").write_text("def run(a, b, c):\n    return a\n", encoding="utf-8")
    issues = engine({"max_parameters": {"max_params": 2}}).run_project(tmp_path, [Path("app/api/users.py")])

    assert issues[0].file == "app/api/users.py"
