# ReviewAgent MCP Server

ReviewAgent exposes its static review engine through an MCP stdio server.

## Install dependencies

```bash
pip install -r app/requirements.txt
```

The Phase 3 MCP server requires `mcp`. Phase 2 analyzers use `ruff`, `radon`, and `networkx`.

## Start the server

```bash
python -m reviewagent.mcp_server.server
```

The server speaks MCP over stdio. It does not start an HTTP server.

## Claude Desktop

```json
{
  "mcpServers": {
    "reviewagent": {
      "command": "python",
      "args": ["-m", "reviewagent.mcp_server.server"],
      "cwd": "/path/to/ReviewAgent"
    }
  }
}
```

## Cursor

Use the same stdio command in Cursor's MCP configuration:

```json
{
  "mcpServers": {
    "reviewagent": {
      "command": "python",
      "args": ["-m", "reviewagent.mcp_server.server"],
      "cwd": "/path/to/ReviewAgent"
    }
  }
}
```

## Tools

### review_file

Input:

```json
{"path": "examples/mcp/sample_file.py"}
```

Output:

```json
{"issues": []}
```

### review_diff

Input:

```json
{"diff": "diff --git a/a.py b/a.py\n..."}
```

Output:

```json
{"issues": []}
```

### review_project

Input:

```json
{"path": "examples/phase2_bad_project", "enable_llm": false}
```

Output:

```json
{"issues": []}
```

Enable optional LLM architecture review:

```json
{
  "path": "examples/architecture_bad_project",
  "enable_llm": true,
  "llm_provider": "mock"
}
```

Enable enterprise rules with an explicit config:

```json
{
  "path": "examples/enterprise_policy_project",
  "config_path": "examples/enterprise_policy_project/reviewagent.yml",
  "enable_enterprise_rules": true
}
```

Disable enterprise rules:

```json
{
  "path": "examples/enterprise_policy_project",
  "enable_enterprise_rules": false
}
```

Enable Phase 6 multi-agent review:

```json
{
  "path": "examples/multi_agent_project",
  "enable_agents": true,
  "config_path": "examples/multi_agent_project/reviewagent.yml"
}
```

Run only selected agents:

```json
{
  "path": "examples/multi_agent_project",
  "enable_agents": true,
  "agents": ["quality", "security"]
}
```

Enable a real LLM provider with explicit network policy:

```json
{
  "path": ".",
  "enable_llm": true,
  "llm_provider": "openai",
  "network_policy": {
    "enabled": true,
    "allow_llm": true,
    "code_sharing_mode": "summary_only",
    "allowed_providers": ["openai"]
  }
}
```

## Troubleshooting

- If `mcp` is missing, install dependencies from `app/requirements.txt`.
- If Ruff, Radon, or networkx are unavailable, ReviewAgent degrades gracefully and still returns JSON.
- The server only performs static analysis. It does not import, execute, modify, or delete reviewed project code.
- Very large files, diffs, or projects return a review error issue instead of crashing the MCP server.
- LLM architecture review is disabled by default. When enabled, ReviewAgent sends a bounded project summary to the configured provider.
- Enterprise rules are enabled by default for `review_project`; when no config is found, behavior is unchanged.
- Multi-agent review is disabled by default and runs synchronously when `enable_agents` is true.
- MCP remains offline by default. Real LLM providers require `network_policy`.
