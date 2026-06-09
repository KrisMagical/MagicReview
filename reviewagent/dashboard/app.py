"""FastAPI Dashboard for ReviewAgent governance data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from reviewagent.dashboard.service import StatisticsService
from reviewagent.storage.database import init_db
from reviewagent.storage.repository import ReviewRepository

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
except ModuleNotFoundError:  # pragma: no cover
    class FastAPI:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.routes = {}

        def get(self, path: str, **_kwargs: Any):
            def decorator(func):
                self.routes[f"GET {path}"] = func
                return func

            return decorator

    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class HTMLResponse(str):  # type: ignore[no-redef]
        pass

    Request = Any  # type: ignore[assignment]
    Jinja2Templates = None  # type: ignore[assignment]
    StaticFiles = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).parent
app = FastAPI(title="ReviewAgent Dashboard")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates")) if Jinja2Templates else None
if StaticFiles is not None:
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def repository() -> ReviewRepository:
    return ReviewRepository()


def stats_service() -> StatisticsService:
    return StatisticsService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/projects")
def api_projects(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_projects(limit=limit, offset=offset)


@app.get("/api/projects/{project_id}")
def api_project(project_id: int) -> dict[str, Any]:
    project = repository().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@app.get("/api/projects/{project_id}/reviews")
def api_project_reviews(project_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_reviews(project_id=project_id, limit=limit, offset=offset)


@app.get("/api/reviews")
def api_reviews(project_id: int | None = None, severity: str | None = None, source: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_reviews(project_id=project_id, severity=severity, source=source, limit=limit, offset=offset)


@app.get("/api/reviews/{review_run_id}")
def api_review(review_run_id: int) -> dict[str, Any]:
    review = repository().get_review_run(review_run_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review run not found.")
    return review


@app.get("/api/reviews/{review_run_id}/issues")
def api_review_issues(review_run_id: int, severity: str | None = None, limit: int = 500, offset: int = 0) -> list[dict[str, Any]]:
    return repository().get_review_issues(review_run_id, severity=severity, limit=limit, offset=offset)


@app.get("/api/stats/overview")
def api_stats_overview() -> dict[str, int]:
    return stats_service().overview()


@app.get("/api/stats/trends/issues")
def api_issue_trend() -> list[dict[str, Any]]:
    return stats_service().issue_trend()


@app.get("/api/stats/trends/bugs")
def api_bug_trend() -> list[dict[str, Any]]:
    return stats_service().bug_trend()


@app.get("/api/stats/trends/technical-debt")
def api_technical_debt_trend() -> list[dict[str, Any]]:
    return stats_service().technical_debt_trend()


@app.get("/api/stats/trends/architecture-risk")
def api_architecture_risk_trend() -> list[dict[str, Any]]:
    return stats_service().architecture_risk_trend()


@app.get("/api/stats/team")
def api_team_stats() -> dict[str, Any]:
    return stats_service().team_stats()


@app.get("/api/audit/network")
def api_network_audit(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_network_audit(limit=limit, offset=offset)


@app.get("/api/audit/network/{audit_id}")
def api_network_audit_detail(audit_id: int) -> dict[str, Any]:
    record = repository().get_network_audit(audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Network audit record not found.")
    return record


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_index(request: Request) -> Any:
    if templates is None:
        return HTMLResponse("<h1>ReviewAgent Dashboard</h1>")
    return templates.TemplateResponse("index.html", {"request": request, "overview": stats_service().overview()})


@app.get("/projects", response_class=HTMLResponse)
def dashboard_projects(request: Request) -> Any:
    if templates is None:
        return HTMLResponse("<h1>Projects</h1>")
    return templates.TemplateResponse("projects.html", {"request": request, "projects": repository().list_projects()})


@app.get("/projects/{project_id}", response_class=HTMLResponse)
def dashboard_project_detail(request: Request, project_id: int) -> Any:
    repo = repository()
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if templates is None:
        return HTMLResponse(f"<h1>{project['name']}</h1>")
    return templates.TemplateResponse("project_detail.html", {"request": request, "project": project, "reviews": repo.list_reviews(project_id=project_id)})


@app.get("/reviews/{review_run_id}", response_class=HTMLResponse)
def dashboard_review_detail(request: Request, review_run_id: int) -> Any:
    repo = repository()
    review = repo.get_review_run(review_run_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review run not found.")
    if templates is None:
        return HTMLResponse(f"<h1>Review #{review['id']}</h1>")
    return templates.TemplateResponse("review_detail.html", {"request": request, "review": review, "issues": repo.get_review_issues(review_run_id)})


@app.get("/audit/network", response_class=HTMLResponse)
def dashboard_network_audit(request: Request) -> Any:
    records = repository().list_network_audit(limit=200)
    if templates is None:
        return HTMLResponse("<h1>Network Audit</h1>")
    return templates.TemplateResponse("network_audit.html", {"request": request, "records": records})


def main() -> None:
    init_db()
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("uvicorn is required to run the dashboard.") from exc
    host = os.getenv("REVIEWAGENT_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("REVIEWAGENT_DASHBOARD_PORT", "8080"))
    uvicorn.run("reviewagent.dashboard.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
