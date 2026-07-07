from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from vendorverdict import __version__
from vendorverdict.auth import (
    authenticated_username,
    auth_is_configured,
    clear_session_cookie,
    credentials_are_valid,
    get_auth_settings,
    set_session_cookie,
)
from vendorverdict.cli import DEMO_QUERY
from vendorverdict.pdf_export import export_report_pdf
from vendorverdict.reporting import export_report_markdown, render_report_markdown
from vendorverdict.storage import ReportRecord, ReportStore, ReportSummary
from vendorverdict.tools.evidence import EvidenceCollector
from vendorverdict.verdict import build_vendor_verdict, render_response, render_verdict


WEB_DIR = Path(__file__).resolve().parent / "web"
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))


class RunReportRequest(BaseModel):
    """Request body for creating a production VendorVerdict report."""

    query: str = Field(..., min_length=5, description="Natural-language vendor comparison or audit request.")
    use_live_evidence: bool | None = Field(
        default=None,
        description="Override live evidence checks. If omitted, VENDORVERDICT_API_LIVE_EVIDENCE is used.",
    )
    # Backward-compatible alias used in early API tests/examples.
    live_evidence: bool | None = Field(default=None, description="Alias for use_live_evidence.")
    export_markdown: bool = Field(default=False, description="Also export Markdown after saving the report.")
    export_pdf: bool = Field(default=False, description="Also export PDF after saving the report.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional caller metadata stored with the report.")


class RunReportResponse(BaseModel):
    status: Literal["completed", "needs_clarification"]
    report_id: str | None = None
    report_url: str | None = None
    markdown_url: str | None = None
    pdf_url: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
    recommendation: str | None = None
    confidence: str | None = None
    vendors: list[str] = Field(default_factory=list)
    use_case: str = ""
    report_text: str
    rendered_response: str
    scorecard: list[dict[str, Any]] = Field(default_factory=list)
    evidence_source_count: int = 0
    evidence_finding_count: int = 0
    exports: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


def create_app(
    *,
    db_path: str | Path | None = None,
    export_dir: str | Path | None = None,
) -> FastAPI:
    """Create the VendorVerdict FastAPI app.

    The API is the production-facing report-management layer. It reuses the same
    report engine as the CLI and ASI:One agent, but exposes it over HTTP so a web
    dashboard, another service, or another agent can create, list, view, and
    export stored reports.
    """

    default_live_evidence = _env_bool("VENDORVERDICT_API_LIVE_EVIDENCE", default=True)

    app = FastAPI(
        title="VendorVerdict API",
        version=__version__,
        description=(
            "Production report-management API for VendorVerdict. It can run "
            "vendor-risk reviews, persist reports, and export Markdown/PDF artifacts."
        ),
    )
    app.state.default_db_path = Path(db_path) if db_path is not None else None
    app.state.default_export_dir = Path(export_dir) if export_dir is not None else None

    cors_origins = [origin.strip() for origin in os.getenv("VENDORVERDICT_API_CORS_ORIGINS", "").split(",") if origin.strip()]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def require_authentication(request: Request, call_next):
        settings = get_auth_settings()
        if not settings.enabled or _is_public_path(request.url.path):
            return await call_next(request)

        if not auth_is_configured(settings):
            return JSONResponse(
                {
                    "detail": (
                        "Authentication is enabled but VENDORVERDICT_AUTH_PASSWORD "
                        "is not configured."
                    )
                },
                status_code=503,
            )

        if authenticated_username(request, settings):
            return await call_next(request)

        if _wants_html(request) or _is_browser_route(request):
            next_path = quote(str(request.url.path), safe="/")
            return RedirectResponse(url=f"/login?next={next_path}", status_code=303)
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request, next: str = "/dashboard") -> Any:
        settings = get_auth_settings()
        if not settings.enabled:
            return RedirectResponse(url=next or "/dashboard", status_code=303)
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "next_url": next or "/dashboard",
                "errors": [],
                "auth": _auth_context(request),
            },
        )

    @app.post("/login", response_class=HTMLResponse)
    async def login_submit(request: Request) -> Any:
        settings = get_auth_settings()
        form = _parse_urlencoded_form(await request.body())
        username = form.get("username", "")
        password = form.get("password", "")
        next_url = form.get("next", "/dashboard") or "/dashboard"

        if credentials_are_valid(username, password, settings):
            response = RedirectResponse(url=next_url, status_code=303)
            set_session_cookie(response, username, settings)
            return response

        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "next_url": next_url,
                "errors": ["Invalid username or password."],
                "auth": _auth_context(request),
            },
            status_code=401,
        )

    @app.get("/logout")
    def logout() -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        clear_session_cookie(response)
        return response

    def store() -> ReportStore:
        env_db = os.getenv("VENDORVERDICT_API_DB_PATH") or os.getenv("VENDORVERDICT_DB_PATH")
        return ReportStore(env_db or app.state.default_db_path)

    def resolved_export_dir() -> Path:
        return Path(
            os.getenv("VENDORVERDICT_API_EXPORT_DIR")
            or os.getenv("VENDORVERDICT_REPORT_EXPORT_DIR")
            or app.state.default_export_dir
            or "reports"
        )

    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "service": "vendorverdict-api",
            "version": __version__,
            "docs": "/docs",
            "dashboard": "/dashboard",
            "health": "/health",
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        report_store = store()
        report_store.list_reports(limit=1)  # Ensures SQLite schema exists and is reachable.
        output = render_response(DEMO_QUERY, use_live_evidence=False)
        required_markers = [
            "VendorVerdict: SaaS Procurement Review",
            "Multi-agent collaboration completed",
            "Procurement Intent Agent",
            "Evidence Agent",
            "Risk Scoring Agent",
            "Recommendation Agent",
            "Email Agent",
            "Critic Agent",
            "Due-diligence email",
        ]
        missing = [marker for marker in required_markers if marker not in output]
        return {
            "status": "ok" if not missing else "fail",
            "service": "vendorverdict-api",
            "version": __version__,
            "db_path": str(report_store.db_path),
            "export_dir": str(resolved_export_dir()),
            "default_live_evidence": default_live_evidence,
            "missing_markers": missing,
            "checks": [
                "parser",
                "specialist-agent workflow",
                "scoring",
                "recommendation",
                "email rendering",
                "report storage",
            ],
        }

    @app.post("/reports/run", response_model=RunReportResponse)
    def run_report(payload: RunReportRequest) -> RunReportResponse:
        if payload.use_live_evidence is not None:
            use_live_evidence = payload.use_live_evidence
        elif payload.live_evidence is not None:
            use_live_evidence = payload.live_evidence
        else:
            use_live_evidence = default_live_evidence

        collector = EvidenceCollector(use_live_checks=use_live_evidence)
        verdict = build_vendor_verdict(payload.query, collector=collector)
        report_text = render_verdict(verdict)

        if verdict.request.missing_fields or verdict.recommendation is None:
            return RunReportResponse(
                status="needs_clarification",
                report_id=None,
                recommendation=None,
                confidence=verdict.confidence,
                vendors=list(verdict.request.vendors),
                use_case=verdict.request.use_case,
                report_text=report_text,
                rendered_response=report_text,
                scorecard=[],
                missing_fields=list(verdict.request.missing_fields),
            )

        report_store = store()
        metadata = {
            "client": "vendorverdict-api",
            "live_evidence": use_live_evidence,
            **payload.metadata,
        }
        report_id = report_store.save_report(verdict, report_text, raw_query=payload.query, metadata=metadata)
        exports: dict[str, str] = {}
        if payload.export_markdown:
            path = export_report_markdown(report_id, output_dir=resolved_export_dir(), store=report_store)
            exports["markdown_path"] = str(path)
        if payload.export_pdf:
            path = export_report_pdf(report_id, output_dir=resolved_export_dir(), store=report_store)
            exports["pdf_path"] = str(path)

        record = _get_report_or_404(report_store, report_id)
        return _run_response(record, exports=exports)

    @app.get("/reports")
    def list_reports(limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        return [_summary_to_dict(summary) for summary in store().list_reports(limit=safe_limit)]

    @app.get("/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, Any]:
        return _record_to_dict(_get_report_or_404(store(), report_id))

    @app.get("/reports/{report_id}/markdown", response_class=PlainTextResponse)
    def get_report_markdown(report_id: str) -> PlainTextResponse:
        report_store = store()
        report = _get_report_or_404(report_store, report_id)
        markdown = render_report_markdown(report)
        return PlainTextResponse(markdown, media_type="text/markdown; charset=utf-8")

    @app.get("/reports/{report_id}/pdf")
    def get_report_pdf(report_id: str) -> FileResponse:
        report_store = store()
        _get_report_or_404(report_store, report_id)
        path = export_report_pdf(report_id, output_dir=resolved_export_dir(), store=report_store)
        return FileResponse(
            path=str(path),
            media_type="application/pdf",
            filename=path.name,
        )

    if (WEB_DIR / "static").exists():
        app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        report_store = store()
        reports = report_store.list_reports(limit=25)
        return TEMPLATES.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "reports": reports,
                "service": "VendorVerdict",
                "version": __version__,
                "auth": _auth_context(request),
            },
        )

    @app.get("/reviews/new", response_class=HTMLResponse)
    def new_review(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "new_review.html",
            {
                "request": request,
                "default_query": DEMO_QUERY,
                "errors": [],
                "draft_response": "",
                "values": {
                    "query": DEMO_QUERY,
                    "live_evidence": False,
                    "export_markdown": True,
                    "export_pdf": True,
                },
                "auth": _auth_context(request),
            },
        )

    @app.post("/reviews/run", response_class=HTMLResponse)
    async def run_review_from_dashboard(request: Request):
        form = _parse_urlencoded_form(await request.body())
        query = form.get("query", "").strip()
        use_live_evidence = form.get("live_evidence") in {"1", "true", "on", "yes"}
        export_markdown = form.get("export_markdown") in {"1", "true", "on", "yes"}
        export_pdf = form.get("export_pdf") in {"1", "true", "on", "yes"}

        errors: list[str] = []
        if len(query) < 5:
            errors.append("Enter a vendor review question with at least one vendor and a use case.")

        if errors:
            return TEMPLATES.TemplateResponse(
                request,
                "new_review.html",
                {
                    "request": request,
                    "default_query": DEMO_QUERY,
                    "errors": errors,
                    "draft_response": "",
                    "values": {
                        "query": query,
                        "live_evidence": use_live_evidence,
                        "export_markdown": export_markdown,
                        "export_pdf": export_pdf,
                    },
                    "auth": _auth_context(request),
                },
                status_code=400,
            )

        collector = EvidenceCollector(use_live_checks=use_live_evidence)
        verdict = build_vendor_verdict(query, collector=collector)
        report_text = render_verdict(verdict)

        if verdict.request.missing_fields or verdict.recommendation is None:
            return TEMPLATES.TemplateResponse(
                request,
                "new_review.html",
                {
                    "request": request,
                    "default_query": DEMO_QUERY,
                    "errors": ["VendorVerdict needs clarification before it can save a report."],
                    "draft_response": report_text,
                    "values": {
                        "query": query,
                        "live_evidence": use_live_evidence,
                        "export_markdown": export_markdown,
                        "export_pdf": export_pdf,
                    },
                    "auth": _auth_context(request),
                },
                status_code=200,
            )

        report_store = store()
        report_id = report_store.save_report(
            verdict,
            report_text,
            raw_query=query,
            metadata={"client": "vendorverdict-dashboard", "live_evidence": use_live_evidence},
        )
        if export_markdown:
            export_report_markdown(report_id, output_dir=resolved_export_dir(), store=report_store)
        if export_pdf:
            export_report_pdf(report_id, output_dir=resolved_export_dir(), store=report_store)

        return RedirectResponse(url=f"/dashboard/reports/{report_id}", status_code=303)

    @app.get("/dashboard/reports/{report_id}", response_class=HTMLResponse)
    def dashboard_report_detail(request: Request, report_id: str) -> HTMLResponse:
        report_store = store()
        report = _get_report_or_404(report_store, report_id)
        return TEMPLATES.TemplateResponse(
            request,
            "report.html",
            {
                "request": request,
                "report": report,
                "scorecard": report.scores_json,
                "findings": report.evidence_findings,
                "sources": report.evidence_items,
                "markdown_url": f"/reports/{report_id}/markdown",
                "pdf_url": f"/reports/{report_id}/pdf",
                "auth": _auth_context(request),
            },
        )

    return app


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_public_path(path: str) -> bool:
    if path in {"/health", "/login", "/logout", "/favicon.ico"}:
        return True
    if path.startswith("/static/"):
        return True
    return False


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "application/xhtml+xml" in accept


def _is_browser_route(request: Request) -> bool:
    if request.method != "GET":
        return False
    path = request.url.path
    return path == "/" or path == "/docs" or path.startswith("/dashboard") or path.startswith("/reviews")


def _auth_context(request: Request) -> dict[str, Any]:
    settings = get_auth_settings()
    username = authenticated_username(request, settings)
    return {
        "enabled": settings.enabled,
        "configured": auth_is_configured(settings),
        "username": username,
        "is_authenticated": bool(username),
    }


def _get_report_or_404(store: ReportStore, report_id: str) -> ReportRecord:
    report = store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")
    return report


def _summary_to_dict(summary: ReportSummary) -> dict[str, Any]:
    return {
        "id": summary.report_id,
        "report_id": summary.report_id,
        "created_at": summary.created_at,
        "mode": summary.mode,
        "report_type": summary.mode,
        "vendors": list(summary.vendors),
        "use_case": summary.use_case,
        "recommendation": summary.recommended_vendor,
        "confidence": summary.overall_confidence,
        "report_url": f"/reports/{summary.report_id}",
        "markdown_url": f"/reports/{summary.report_id}/markdown",
        "pdf_url": f"/reports/{summary.report_id}/pdf",
    }


def _run_response(record: ReportRecord, exports: dict[str, str] | None = None) -> RunReportResponse:
    links = {
        "self": f"/reports/{record.report_id}",
        "markdown": f"/reports/{record.report_id}/markdown",
        "pdf": f"/reports/{record.report_id}/pdf",
    }
    return RunReportResponse(
        status="completed",
        report_id=record.report_id,
        report_url=links["self"],
        markdown_url=links["markdown"],
        pdf_url=links["pdf"],
        links=links,
        recommendation=record.recommended_vendor,
        confidence=record.overall_confidence,
        vendors=list(record.vendors),
        use_case=record.use_case,
        report_text=record.report_text,
        rendered_response=record.report_text,
        scorecard=record.scores_json,
        evidence_source_count=len(record.evidence_items),
        evidence_finding_count=len(record.evidence_findings),
        exports=exports or {},
    )


def _parse_urlencoded_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _record_to_dict(report: ReportRecord) -> dict[str, Any]:
    return {
        "id": report.report_id,
        "report_id": report.report_id,
        "created_at": report.created_at,
        "raw_query": report.raw_query,
        "mode": report.mode,
        "report_type": report.mode,
        "vendors": list(report.vendors),
        "use_case": report.use_case,
        "recommendation": report.recommended_vendor,
        "confidence": report.overall_confidence,
        "report_text": report.report_text,
        "rendered_response": report.report_text,
        "request": report.request_json,
        "scores": report.scores_json,
        "scorecard": report.scores_json,
        "collaboration_steps": list(report.collaboration_steps),
        "critic_warnings": list(report.critic_warnings),
        "metadata": report.metadata_json,
        "evidence_items": report.evidence_items,
        "evidence_sources": report.evidence_items,
        "evidence_findings": report.evidence_findings,
        "markdown_url": f"/reports/{report.report_id}/markdown",
        "pdf_url": f"/reports/{report.report_id}/pdf",
    }


app = create_app()


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Run the VendorVerdict FastAPI report-management backend.")
    parser.add_argument("--host", default=os.getenv("VENDORVERDICT_API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VENDORVERDICT_API_PORT", "8080")))
    args = parser.parse_args()

    uvicorn.run("vendorverdict.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
