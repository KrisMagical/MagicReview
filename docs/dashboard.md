# Phase 9 Dashboard

Phase 9 adds a local governance dashboard for ReviewAgent review history, issue trends, risk statistics, and team review summaries.

The Dashboard does not replace CLI, MCP, or GitHub App workflows. It stores optional review results and reads them from SQLite.

## What It Shows

- Projects
- Review runs
- Stored issues
- Severity overview
- Bug trends
- Technical debt trends
- Architecture risk trends
- Team review statistics
- Risky files

## SQLite Storage

Default path:

```text
.reviewagent/reviewagent.db
```

Override:

```bash
REVIEWAGENT_DB_PATH=/path/to/reviewagent.db
```

Initialize:

```bash
review dashboard init-db
```

## Save CLI Results

Saving is opt-in:

```bash
review project . --save
review project examples/multi_agent_project --agents --save --format json
review file app/main.py --save
review diff --file changes.patch --save
```

Without `--save`, CLI behavior is unchanged and no database write occurs.

## Save GitHub PR Results

Enable:

```bash
REVIEWAGENT_GITHUB_SAVE_RESULTS=true
```

GitHub App saves issue summaries and sanitized metadata. It does not save tokens, private keys, or full diff text.

## Start Dashboard

```bash
review dashboard serve --host 127.0.0.1 --port 8080
python -m reviewagent.dashboard.app
reviewagent-dashboard
```

Environment:

```bash
REVIEWAGENT_DASHBOARD_HOST=127.0.0.1
REVIEWAGENT_DASHBOARD_PORT=8080
REVIEWAGENT_DB_PATH=.reviewagent/reviewagent.db
```

## API Routes

- `GET /health`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/reviews`
- `GET /api/reviews`
- `GET /api/reviews/{review_run_id}`
- `GET /api/reviews/{review_run_id}/issues`
- `GET /api/stats/overview`
- `GET /api/stats/trends/issues`
- `GET /api/stats/trends/bugs`
- `GET /api/stats/trends/technical-debt`
- `GET /api/stats/trends/architecture-risk`
- `GET /api/stats/team`
- `GET /api/audit/network`
- `GET /api/audit/network/{id}`

## Pages

- `/` or `/dashboard`: overview
- `/projects`: project list
- `/projects/{id}`: project detail
- `/reviews/{id}`: review detail
- `/audit/network`: connected-service audit events

## Security

The Dashboard defaults to `127.0.0.1` and is intended for local or controlled internal use. It has no authentication in Phase 9 and should not be exposed directly to the public internet.

The Dashboard does not execute project code, modify source files, expose environment variables, or display GitHub tokens/private keys.

## Current Limits

- No RBAC or multi-tenant auth.
- No distributed queue.
- No advanced charts or frontend framework.
- No long-term SaaS deployment tooling.
- V1.0+ can add auth, team dashboards, richer trend visualizations, and deployment hardening.
