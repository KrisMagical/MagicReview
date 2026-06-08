# PR Review Agent

基于三层架构（规则引擎 + AST 静态分析 + LLM）的代码审查工具，输入 `git diff`，输出结构化 JSON 报告。

## 快速开始

# 安装依赖
pip install -r requirements.txt

# 设置 OpenAI API Key（用于 LLM 分析）
export OPENAI_API_KEY="your-key"

# 使用示例
git diff | python -m app.main
# 或
python -m app.main --diff-file changes.diff

## 输出示例
```json
{
  "issues": [
    {
      "severity": "high",
      "type": "sql_injection",
      "file": "user_service.py",
      "line": 45,
      "message": "SQL Injection Risk"
    }
  ]
}
```

支持的分析
规则层：Ruff (命名规范、未使用变量)

AST 层：Magic Number、函数复杂度 (radon)

LLM 层：SQL注入、NoneType错误、单一职责原则

配置
复杂度阈值：修改 app/analyzers/complexity_analyzer.py 中的 THRESHOLD

忽略的魔法数字：修改 MagicNumberAnalyzer.ALLOWED_CONSTANTS

