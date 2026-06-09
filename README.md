# ReviewAgent

ReviewAgent is an agent-native software review platform for local static review, enterprise policy checks, optional LLM architecture review, MCP integration, and multi-agent project analysis.

## Quick Start

```bash
pip install -e .
review --help
```

Without installing:

```bash
python -m reviewagent.cli.main --help
```

## Common CLI Commands

```bash
review file examples/bad_code.py --format json
review file examples/bad_code.py --format terminal
cat examples/sample.diff | review diff --format json
review diff --file examples/sample.diff --format markdown --output review-diff.md
review project examples/phase2_bad_project --format terminal
review project examples/enterprise_policy_project --config examples/enterprise_policy_project/reviewagent.yml
review project examples/multi_agent_project --agents --config examples/multi_agent_project/reviewagent.yml
review project examples/multi_agent_project --agents --save --format json
```

## Output Formats

ReviewAgent supports:

- JSON
- Terminal
- Markdown
- HTML

JSON remains the default and always includes the `issues` field.

## MCP Server

```bash
python -m reviewagent.mcp_server.server
```

Installed console script:

```bash
reviewagent-mcp
```

## GitHub App

```bash
python -m reviewagent.integrations.github.app
```

Installed console script:

```bash
reviewagent-github-app
```

See [GitHub App](docs/github_app.md) for permissions, environment variables, webhook setup, and comment behavior.

## Dashboard

```bash
review dashboard init-db
review dashboard serve --host 127.0.0.1 --port 8080
```

Standalone:

```bash
python -m reviewagent.dashboard.app
```

## Docs

- [CLI](docs/cli.md)
- [MCP](docs/mcp.md)
- [Enterprise Rules](docs/enterprise_rules.md)
- [Architecture Review](docs/architecture_review.md)
- [Multi-Agent Review](docs/multi_agent.md)
- [GitHub App](docs/github_app.md)
- [Dashboard](docs/dashboard.md)
- [Connected Services](docs/connected_services.md)
