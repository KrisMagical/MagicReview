# ReviewAgent CLI

Phase 7 turns ReviewAgent into a local developer CLI while keeping the same ReviewService core used by MCP.

## Install

```bash
pip install -e .
```

This installs:

- `review`
- `reviewagent`
- `reviewagent-mcp`

You can also run without installing:

```bash
python -m reviewagent.cli.main --help
```

## Help

```bash
review --help
review file --help
review diff --help
review project --help
```

## Review A File

```bash
review file examples/bad_code.py
review file examples/bad_code.py --format terminal
review file examples/bad_code.py --format json --fail-on high
review file examples/bad_code.py --config reviewagent.yml
review file examples/bad_code.py --save
```

## Review A Diff

```bash
git diff | review diff --format terminal
review diff --file examples/sample.diff --format markdown --output diff-review.md
review diff --file examples/sample.diff --save
```

By default, `review diff` reads from stdin.

## Review A Project

```bash
review project .
review project . --format terminal
review project examples/phase2_bad_project --format markdown --output review.md
review project examples/architecture_bad_project --llm --llm-provider mock
review project examples/enterprise_policy_project --config examples/enterprise_policy_project/reviewagent.yml
review project examples/multi_agent_project --agents
review project examples/multi_agent_project --agents quality,security
review project examples/multi_agent_project --agents --save
```

## Output Formats

Supported values:

- `json`
- `terminal`
- `markdown`
- `html`

JSON remains the default for compatibility with automation. JSON reports include `issues` and `summary`.

## Output Files

```bash
review project . --format html --output review.html
review diff --file changes.patch --format markdown --output review.md
```

`--output` writes only the report file requested by the user. ReviewAgent does not modify source files.

## Filtering

```bash
review project . --severity high
review project . --max-issues 50
```

`--severity high` includes only `high` and `critical` issues.

## Exit Codes

- `0`: command succeeded and no `--fail-on` threshold was reached.
- `1`: `--fail-on` was provided and an issue at that severity or higher exists.
- `2`: CLI argument or local CLI execution error.

Example:

```bash
review project . --fail-on high
```

## Enterprise Rules

```bash
review project . --config reviewagent.yml
review project . --no-enterprise
```

Project review auto-loads YAML/JSON enterprise configs when present. `--no-enterprise` disables that behavior.

## LLM Review

LLM architecture review is disabled by default.

```bash
review project . --llm --llm-provider mock
review project . --llm --llm-provider openai
```

Without a configured provider/API key, ReviewAgent returns a normal issue instead of crashing.

## Multi-Agent Review

```bash
review project . --agents
review project . --agents quality,bug,security
```

Agents run synchronously and never modify source files.

## Dashboard

```bash
review dashboard init-db
review dashboard serve --host 127.0.0.1 --port 8080
review project . --save
review file app/main.py --save
review diff --file changes.patch --save
```

Saved reviews are written to the SQLite database configured by `REVIEWAGENT_DB_PATH`, or `.reviewagent/reviewagent.db` by default.

## Common Errors

- Missing file or directory: returned as a normal `ReviewError` issue.
- Missing LLM provider: returned as an `ArchitectureReviewError` issue.
- Unknown agent: returned as an `UnknownAgent` issue.
- Output path cannot be written: CLI exits with code `2`.

Use `--debug` to print traceback details to stderr. JSON stdout remains clean.
