# MCP examples

Run the sample file through the CLI:

```bash
python -m reviewagent.cli.main file examples/mcp/sample_file.py
```

Run the sample diff through the CLI:

```bash
cat examples/mcp/sample.diff | python -m reviewagent.cli.main diff
```

Review a project:

```bash
python -m reviewagent.cli.main project examples/phase2_bad_project
```

Start the MCP server:

```bash
python -m reviewagent.mcp_server.server
```

MCP tool inputs:

```json
{"path": "examples/mcp/sample_file.py"}
```

```json
{"diff": "diff --git a/a.py b/a.py\n..."}
```

```json
{"path": "examples/phase2_bad_project"}
```
