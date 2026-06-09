# Connected Services

ReviewAgent is local-first and offline by default.

By default, ReviewAgent does not:

- call real LLM providers
- upload code
- call remote MCP services
- send project summaries outside the machine
- enable LLM architecture review with a network provider

Connected services require explicit opt-in.

## NetworkPolicy

ReviewAgent uses a `NetworkPolicy` gate:

```json
{
  "enabled": false,
  "allow_llm": false,
  "allow_github_api": false,
  "allow_remote_mcp": false,
  "code_sharing_mode": "none",
  "allowed_providers": [],
  "require_explicit_consent": true,
  "audit_enabled": true
}
```

`code_sharing_mode` values:

- `none`: no code or project summary may be sent
- `summary_only`: bounded architecture/project summary only
- `snippets`: selected snippets may be sent
- `full_context`: broad context may be sent

## CLI

Mock LLM stays offline:

```bash
review project . --llm --llm-provider mock
```

Real providers require explicit authorization:

```bash
review project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
review project . --llm --llm-provider anthropic --allow-network --allow-llm --code-sharing summary-only
```

`--llm` alone is not network consent.

## Providers

Implemented provider center:

- `none`
- `mock`
- `openai`
- `anthropic`
- `azure_openai`, placeholder

Environment variables:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
REVIEWAGENT_LLM_MODEL=...
REVIEWAGENT_ANTHROPIC_MODEL=...
```

Provider errors become normal ReviewAgent issues, not tracebacks.

## GitHub App

GitHub App necessarily calls GitHub APIs for webhook PR review. Its PR review mode is:

```bash
REVIEWAGENT_GITHUB_REVIEW_MODE=diff_only
```

Optional:

```bash
REVIEWAGENT_GITHUB_REVIEW_MODE=full_project
```

`full_project` builds a temporary changed-files project context from PR files and calls `ReviewService.review_project`. It does not execute PR code and cleans the temporary directory.

## MCP

MCP `review_project` accepts:

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

Without `network_policy`, MCP remains offline.

## Network Audit

ReviewAgent records connected-service audit metadata when audit is enabled:

- source
- provider
- operation
- code sharing mode
- status
- error type
- target/project identifiers

It does not store:

- API keys
- tokens
- private keys
- full prompts
- full source code

Dashboard routes:

- `GET /api/audit/network`
- `GET /api/audit/network/{id}`
- `/audit/network`

## Enterprise Deployment

Recommended enterprise defaults:

- keep `NetworkPolicy.enabled=false` by default
- allow only approved providers
- use `summary_only` unless snippets are formally approved
- route LLM traffic through a private gateway if needed
- keep Dashboard behind VPN/internal auth
- review audit logs regularly
