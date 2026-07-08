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
from vendorverdict.lead_followups import build_lead_followup_templates
from vendorverdict.lead_notifications import send_lead_notification
from vendorverdict.leads import LEAD_STATUSES, LeadStore
from vendorverdict.pilots import PILOT_PACKAGES, PILOT_STATUSES, PilotStore
from vendorverdict.pilot_outcomes import build_pilot_outcome, render_pilot_outcome_markdown
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

    def lead_store() -> LeadStore:
        env_db = os.getenv("VENDORVERDICT_API_DB_PATH") or os.getenv("VENDORVERDICT_DB_PATH")
        return LeadStore(env_db or app.state.default_db_path)

    def pilot_store() -> PilotStore:
        env_db = os.getenv("VENDORVERDICT_API_DB_PATH") or os.getenv("VENDORVERDICT_DB_PATH")
        return PilotStore(env_db or app.state.default_db_path)

    def resolved_export_dir() -> Path:
        return Path(
            os.getenv("VENDORVERDICT_API_EXPORT_DIR")
            or os.getenv("VENDORVERDICT_REPORT_EXPORT_DIR")
            or app.state.default_export_dir
            or "reports"
        )

    @app.get("/", response_class=HTMLResponse)
    def landing(request: Request) -> HTMLResponse:
        report_count = len(store().list_reports(limit=100))
        return TEMPLATES.TemplateResponse(
            request,
            "landing.html",
            {
                "request": request,
                "report_count": report_count,
                "version": __version__,
                "auth": _auth_context(request),
            },
        )

    @app.get("/demo", response_class=HTMLResponse)
    def public_demo_report(request: Request) -> HTMLResponse:
        verdict = build_vendor_verdict(DEMO_QUERY, collector=EvidenceCollector(use_live_checks=False))
        report_text = render_verdict(verdict)
        return TEMPLATES.TemplateResponse(
            request,
            "sample_report.html",
            {
                "request": request,
                "query": DEMO_QUERY,
                "verdict": verdict,
                "scorecard": verdict.scores,
                "winner": verdict.recommendation,
                "report_text": report_text,
                "auth": _auth_context(request),
            },
        )

    @app.get("/pilot", response_class=HTMLResponse)
    def pilot_request_form(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "pilot_request.html",
            {
                "request": request,
                "errors": [],
                "values": _lead_default_values(source="pilot"),
                "pilot_packages": _pilot_packages(),
                "auth": _auth_context(request),
            },
        )

    @app.get("/pricing", response_class=HTMLResponse)
    def pilot_pricing(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "pricing.html",
            {
                "request": request,
                "pilot_packages": _pilot_packages(),
                "auth": _auth_context(request),
            },
        )

    @app.get("/trust", response_class=HTMLResponse)
    def trust_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "trust.html",
            {
                "request": request,
                "auth": _auth_context(request),
            },
        )

    @app.get("/privacy", response_class=HTMLResponse)
    def privacy_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "privacy.html",
            {
                "request": request,
                "auth": _auth_context(request),
            },
        )

    @app.get("/disclaimer", response_class=HTMLResponse)
    def disclaimer_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "disclaimer.html",
            {
                "request": request,
                "auth": _auth_context(request),
            },
        )

    @app.post("/leads/request", response_class=HTMLResponse)
    async def submit_lead_request(request: Request) -> Any:
        form = _parse_urlencoded_form(await request.body())
        values = _lead_values_from_form(form)
        errors = _validate_lead_values(values)

        if errors:
            return TEMPLATES.TemplateResponse(
                request,
                "pilot_request.html",
                {
                    "request": request,
                    "errors": errors,
                    "values": values,
                    "pilot_packages": _pilot_packages(),
                    "auth": _auth_context(request),
                },
                status_code=400,
            )

        leads = lead_store()
        lead_id = leads.save_lead(
            name=values["name"],
            email=values["email"],
            company=values["company"],
            use_case=values["use_case"],
            vendors=values["vendors"],
            message=values["message"],
            source=values["source"],
        )
        lead = leads.get_lead(lead_id)
        if lead is not None:
            result = send_lead_notification(lead, app_base_url=_public_base_url(request))
            leads.update_notification_status(lead_id, status=result.status, error=result.message)
        return RedirectResponse(url=f"/pilot/thanks?lead_id={quote(lead_id)}", status_code=303)

    @app.get("/pilot/thanks", response_class=HTMLResponse)
    def pilot_request_thanks(request: Request, lead_id: str = "") -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "pilot_thanks.html",
            {
                "request": request,
                "lead_id": lead_id,
                "auth": _auth_context(request),
            },
        )

    @app.get("/favicon.ico")
    def favicon_ico() -> FileResponse:
        return FileResponse(str(WEB_DIR / "static" / "favicon.ico"), media_type="image/x-icon")

    @app.get("/favicon.png")
    def favicon_png() -> FileResponse:
        return FileResponse(str(WEB_DIR / "static" / "favicon.png"), media_type="image/png")

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
                "lead_count": len(lead_store().list_leads(limit=200)),
                "pilot_count": len(pilot_store().list_pilots(limit=200)),
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
                "values": _dashboard_default_values(),
                "auth": _auth_context(request),
            },
        )

    @app.post("/reviews/sample")
    def run_sample_review() -> RedirectResponse:
        report_store = store()
        collector = EvidenceCollector(use_live_checks=False)
        verdict = build_vendor_verdict(DEMO_QUERY, collector=collector)
        report_text = render_verdict(verdict)
        if verdict.request.missing_fields or verdict.recommendation is None:
            raise HTTPException(status_code=500, detail="Sample review could not be generated.")

        report_id = report_store.save_report(
            verdict,
            report_text,
            raw_query=DEMO_QUERY,
            metadata={
                "client": "vendorverdict-dashboard-sample",
                "live_evidence": False,
                "sample_review": True,
                "demo_flow": "customer-demo",
            },
        )
        export_report_markdown(report_id, output_dir=resolved_export_dir(), store=report_store)
        export_report_pdf(report_id, output_dir=resolved_export_dir(), store=report_store)
        return RedirectResponse(url=f"/dashboard/reports/{report_id}", status_code=303)

    @app.post("/reviews/run", response_class=HTMLResponse)
    async def run_review_from_dashboard(request: Request):
        form = _parse_urlencoded_form(await request.body())
        query = _compose_dashboard_query(form)
        values = _dashboard_values_from_form(form, query=query)
        use_live_evidence = form.get("live_evidence") in {"1", "true", "on", "yes"}
        export_markdown = form.get("export_markdown") in {"1", "true", "on", "yes"}
        export_pdf = form.get("export_pdf") in {"1", "true", "on", "yes"}

        errors: list[str] = []
        if len(query) < 5:
            errors.append("Enter at least two vendors and a use case, or write a full review question.")

        if errors:
            return TEMPLATES.TemplateResponse(
                request,
                "new_review.html",
                {
                    "request": request,
                    "default_query": DEMO_QUERY,
                    "errors": errors,
                    "draft_response": "",
                    "values": values,
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
                    "values": values,
                    "auth": _auth_context(request),
                },
                status_code=200,
            )

        report_store = store()
        report_id = report_store.save_report(
            verdict,
            report_text,
            raw_query=query,
            metadata={
                "client": "vendorverdict-dashboard",
                "live_evidence": use_live_evidence,
                "dashboard_form": {
                    "vendors": values.get("vendors", ""),
                    "use_case": values.get("use_case", ""),
                    "team_size": values.get("team_size", ""),
                    "region": values.get("region", ""),
                    "data_sensitivity": values.get("data_sensitivity", ""),
                },
            },
        )
        if export_markdown:
            export_report_markdown(report_id, output_dir=resolved_export_dir(), store=report_store)
        if export_pdf:
            export_report_pdf(report_id, output_dir=resolved_export_dir(), store=report_store)

        return RedirectResponse(url=f"/dashboard/reports/{report_id}", status_code=303)

    @app.get("/dashboard/leads", response_class=HTMLResponse)
    def dashboard_leads(request: Request) -> HTMLResponse:
        leads = lead_store()
        return TEMPLATES.TemplateResponse(
            request,
            "leads.html",
            {
                "request": request,
                "leads": leads.list_leads(limit=100),
                "status_counts": leads.status_counts(),
                "lead_statuses": LEAD_STATUSES,
                "auth": _auth_context(request),
            },
        )

    @app.post("/dashboard/leads/{lead_id}/status")
    async def update_dashboard_lead_status(request: Request, lead_id: str) -> RedirectResponse:
        form = _parse_urlencoded_form(await request.body())
        updated = lead_store().update_lead_status(
            lead_id,
            status=form.get("status", "new"),
            notes=form.get("notes", ""),
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Lead not found: {lead_id}")
        next_url = form.get("next", "/dashboard/leads")
        if not next_url.startswith("/dashboard/leads"):
            next_url = "/dashboard/leads"
        return RedirectResponse(url=next_url, status_code=303)

    @app.get("/dashboard/leads.csv")
    def export_dashboard_leads_csv() -> PlainTextResponse:
        csv_text = lead_store().export_csv(limit=2000)
        return PlainTextResponse(
            csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="vendorverdict-leads.csv"'},
        )


    @app.get("/dashboard/leads/{lead_id}", response_class=HTMLResponse)
    def dashboard_lead_detail(request: Request, lead_id: str) -> HTMLResponse:
        lead = lead_store().get_lead(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail=f"Lead not found: {lead_id}")
        return TEMPLATES.TemplateResponse(
            request,
            "lead_detail.html",
            {
                "request": request,
                "lead": lead,
                "lead_statuses": LEAD_STATUSES,
                "followups": build_lead_followup_templates(lead, app_base_url=_public_base_url(request)),
                "auth": _auth_context(request),
            },
        )

    @app.post("/dashboard/leads/{lead_id}/pilot")
    async def create_pilot_from_lead(request: Request, lead_id: str) -> RedirectResponse:
        lead = lead_store().get_lead(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail=f"Lead not found: {lead_id}")
        form = _parse_urlencoded_form(await request.body())
        pilot_id = pilot_store().create_from_lead(
            lead,
            package=form.get("package", "founding"),
            objective=form.get("objective", lead.use_case),
            review_target=form.get("review_target", "20"),
            notes=form.get("notes", "Created from lead detail."),
        )
        if lead.status in {"new", "contacted", "qualified"}:
            lead_store().update_lead_status(
                lead_id,
                status="won",
                notes=(lead.notes + "\n" if lead.notes else "") + "Pilot workspace created.",
            )
        return RedirectResponse(url=f"/dashboard/pilots/{pilot_id}", status_code=303)

    @app.get("/dashboard/pilots", response_class=HTMLResponse)
    def dashboard_pilots(request: Request) -> HTMLResponse:
        pilots = pilot_store()
        return TEMPLATES.TemplateResponse(
            request,
            "pilots.html",
            {
                "request": request,
                "pilots": pilots.list_pilots(limit=100),
                "status_counts": pilots.status_counts(),
                "pilot_statuses": PILOT_STATUSES,
                "auth": _auth_context(request),
            },
        )

    @app.get("/dashboard/pilots.csv")
    def export_dashboard_pilots_csv() -> PlainTextResponse:
        csv_text = pilot_store().export_csv(limit=2000)
        return PlainTextResponse(
            csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="vendorverdict-pilots.csv"'},
        )

    @app.get("/dashboard/pilots/{pilot_id}", response_class=HTMLResponse)
    def dashboard_pilot_detail(request: Request, pilot_id: str) -> HTMLResponse:
        pilots = pilot_store()
        pilot = pilots.get_pilot(pilot_id)
        if pilot is None:
            raise HTTPException(status_code=404, detail=f"Pilot not found: {pilot_id}")
        lead = lead_store().get_lead(pilot.lead_id) if pilot.lead_id else None
        return TEMPLATES.TemplateResponse(
            request,
            "pilot_detail.html",
            {
                "request": request,
                "pilot": pilot,
                "lead": lead,
                "tasks": pilots.list_tasks(pilot_id),
                "reviews": pilots.list_reviews(pilot_id),
                "review_count": pilots.review_count(pilot_id),
                "review_values": _pilot_review_default_values(pilot),
                "review_errors": [],
                "draft_response": "",
                "pilot_statuses": PILOT_STATUSES,
                "pilot_packages": PILOT_PACKAGES,
                "auth": _auth_context(request),
            },
        )

    @app.post("/dashboard/pilots/{pilot_id}/update")
    async def update_dashboard_pilot(request: Request, pilot_id: str) -> RedirectResponse:
        form = _parse_urlencoded_form(await request.body())
        updated = pilot_store().update_pilot(
            pilot_id,
            status=form.get("status", "planned"),
            package=form.get("package", "founding"),
            objective=form.get("objective", ""),
            review_target=form.get("review_target", "20"),
            start_date=form.get("start_date", ""),
            end_date=form.get("end_date", ""),
            notes=form.get("notes", ""),
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Pilot not found: {pilot_id}")
        return RedirectResponse(url=f"/dashboard/pilots/{pilot_id}", status_code=303)

    @app.post("/dashboard/pilots/{pilot_id}/tasks/{task_key}")
    async def update_dashboard_pilot_task(request: Request, pilot_id: str, task_key: str) -> RedirectResponse:
        form = _parse_urlencoded_form(await request.body())
        completed = form.get("completed", "") in {"1", "true", "on", "yes"}
        updated = pilot_store().set_task_completed(pilot_id, task_key, completed)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Pilot task not found: {pilot_id}/{task_key}")
        return RedirectResponse(url=f"/dashboard/pilots/{pilot_id}", status_code=303)

    @app.get("/dashboard/pilots/{pilot_id}/reviews.csv")
    def export_dashboard_pilot_reviews_csv(pilot_id: str) -> PlainTextResponse:
        pilots = pilot_store()
        if pilots.get_pilot(pilot_id) is None:
            raise HTTPException(status_code=404, detail=f"Pilot not found: {pilot_id}")
        csv_text = pilots.export_reviews_csv(pilot_id)
        return PlainTextResponse(
            csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="vendorverdict-pilot-reviews.csv"'},
        )

    @app.get("/dashboard/pilots/{pilot_id}/outcome", response_class=HTMLResponse)
    def dashboard_pilot_outcome(request: Request, pilot_id: str) -> HTMLResponse:
        pilots = pilot_store()
        pilot = pilots.get_pilot(pilot_id)
        if pilot is None:
            raise HTTPException(status_code=404, detail=f"Pilot not found: {pilot_id}")
        outcome = build_pilot_outcome(
            pilot,
            pilots.list_tasks(pilot_id),
            pilots.list_reviews(pilot_id),
        )
        return TEMPLATES.TemplateResponse(
            request,
            "pilot_outcome.html",
            {
                "request": request,
                "pilot": pilot,
                "outcome": outcome,
                "auth": _auth_context(request),
            },
        )

    @app.get("/dashboard/pilots/{pilot_id}/outcome.md")
    def export_dashboard_pilot_outcome_markdown(pilot_id: str) -> PlainTextResponse:
        pilots = pilot_store()
        pilot = pilots.get_pilot(pilot_id)
        if pilot is None:
            raise HTTPException(status_code=404, detail=f"Pilot not found: {pilot_id}")
        outcome = build_pilot_outcome(
            pilot,
            pilots.list_tasks(pilot_id),
            pilots.list_reviews(pilot_id),
        )
        return PlainTextResponse(
            render_pilot_outcome_markdown(outcome),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="vendorverdict-pilot-outcome.md"'},
        )

    @app.post("/dashboard/pilots/{pilot_id}/complete")
    async def complete_dashboard_pilot(pilot_id: str) -> RedirectResponse:
        pilots = pilot_store()
        pilot = pilots.get_pilot(pilot_id)
        if pilot is None:
            raise HTTPException(status_code=404, detail=f"Pilot not found: {pilot_id}")
        pilots.update_pilot(
            pilot_id,
            status="completed",
            package=pilot.package,
            objective=pilot.objective,
            review_target=pilot.review_target,
            start_date=pilot.start_date,
            end_date=pilot.end_date,
            notes=pilot.notes,
        )
        pilots.set_task_completed(pilot_id, "final_review", True)
        return RedirectResponse(url=f"/dashboard/pilots/{pilot_id}/outcome", status_code=303)

    @app.post("/dashboard/pilots/{pilot_id}/reviews/run", response_class=HTMLResponse)
    async def run_dashboard_pilot_review(request: Request, pilot_id: str):
        pilots = pilot_store()
        pilot = pilots.get_pilot(pilot_id)
        if pilot is None:
            raise HTTPException(status_code=404, detail=f"Pilot not found: {pilot_id}")

        form = _parse_urlencoded_form(await request.body())
        query = _compose_dashboard_query(form)
        values = _dashboard_values_from_form(form, query=query)
        review_label = (form.get("label") or values.get("use_case") or "Pilot vendor review").strip()
        use_live_evidence = form.get("live_evidence") in {"1", "true", "on", "yes"}
        export_markdown = form.get("export_markdown") in {"1", "true", "on", "yes"}
        export_pdf = form.get("export_pdf") in {"1", "true", "on", "yes"}

        errors: list[str] = []
        if len(query) < 5:
            errors.append("Enter vendors and a use case before running a pilot review.")

        if errors:
            lead = lead_store().get_lead(pilot.lead_id) if pilot.lead_id else None
            return TEMPLATES.TemplateResponse(
                request,
                "pilot_detail.html",
                {
                    "request": request,
                    "pilot": pilot,
                    "lead": lead,
                    "tasks": pilots.list_tasks(pilot_id),
                    "reviews": pilots.list_reviews(pilot_id),
                    "review_count": pilots.review_count(pilot_id),
                    "review_values": {**values, "label": review_label},
                    "review_errors": errors,
                    "draft_response": "",
                    "pilot_statuses": PILOT_STATUSES,
                    "pilot_packages": PILOT_PACKAGES,
                    "auth": _auth_context(request),
                },
                status_code=400,
            )

        collector = EvidenceCollector(use_live_checks=use_live_evidence)
        verdict = build_vendor_verdict(query, collector=collector)
        report_text = render_verdict(verdict)

        if verdict.request.missing_fields or verdict.recommendation is None:
            lead = lead_store().get_lead(pilot.lead_id) if pilot.lead_id else None
            return TEMPLATES.TemplateResponse(
                request,
                "pilot_detail.html",
                {
                    "request": request,
                    "pilot": pilot,
                    "lead": lead,
                    "tasks": pilots.list_tasks(pilot_id),
                    "reviews": pilots.list_reviews(pilot_id),
                    "review_count": pilots.review_count(pilot_id),
                    "review_values": {**values, "label": review_label},
                    "review_errors": ["VendorVerdict needs clarification before it can save this pilot review."],
                    "draft_response": report_text,
                    "pilot_statuses": PILOT_STATUSES,
                    "pilot_packages": PILOT_PACKAGES,
                    "auth": _auth_context(request),
                },
                status_code=200,
            )

        report_store = store()
        report_id = report_store.save_report(
            verdict,
            report_text,
            raw_query=query,
            metadata={
                "client": "vendorverdict-pilot-workspace",
                "pilot_id": pilot_id,
                "pilot_company": pilot.company,
                "pilot_review_label": review_label,
                "live_evidence": use_live_evidence,
                "dashboard_form": {
                    "vendors": values.get("vendors", ""),
                    "use_case": values.get("use_case", ""),
                    "team_size": values.get("team_size", ""),
                    "region": values.get("region", ""),
                    "data_sensitivity": values.get("data_sensitivity", ""),
                },
            },
        )
        if export_markdown:
            export_report_markdown(report_id, output_dir=resolved_export_dir(), store=report_store)
        if export_pdf:
            export_report_pdf(report_id, output_dir=resolved_export_dir(), store=report_store)
        pilots.link_report(pilot_id, report_id, label=review_label, status="completed")
        if pilots.review_count(pilot_id) >= 1:
            pilots.set_task_completed(pilot_id, "run_first_reports", True)
        if export_markdown or export_pdf:
            pilots.set_task_completed(pilot_id, "export_artifacts", True)
        return RedirectResponse(url=f"/dashboard/pilots/{pilot_id}", status_code=303)

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
                "source_count": len(report.evidence_items),
                "finding_count": len(report.evidence_findings),
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
    if path in {
        "/",
        "/demo",
        "/pricing",
        "/pilot",
        "/pilot/thanks",
        "/trust",
        "/privacy",
        "/disclaimer",
        "/leads/request",
        "/health",
        "/login",
        "/logout",
        "/favicon.ico",
        "/favicon.png",
    }:
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
    return path == "/" or path == "/docs" or path.startswith("/pilot") or path.startswith("/dashboard") or path.startswith("/reviews")


def _public_base_url(request: Request) -> str:
    configured = os.getenv("VENDORVERDICT_PUBLIC_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _auth_context(request: Request) -> dict[str, Any]:
    settings = get_auth_settings()
    username = authenticated_username(request, settings)
    return {
        "enabled": settings.enabled,
        "configured": auth_is_configured(settings),
        "username": username,
        "is_authenticated": bool(username),
    }



def _pilot_review_default_values(pilot: Any) -> dict[str, str]:
    return {
        "label": "First pilot review",
        "vendors": "",
        "use_case": pilot.objective or "",
        "team_size": "",
        "region": "UK",
        "data_sensitivity": "medium",
        "query": "",
    }


def _pilot_packages() -> list[dict[str, Any]]:
    return [
        {
            "name": "Founding pilot",
            "price": "From £1,500",
            "duration": "4 weeks",
            "cases": "10–20 reviews",
            "badge": "Best first step",
            "description": "A focused pilot for one team choosing SaaS tools for client or business data.",
            "features": [
                "Guided setup call to define your review workflow",
                "10–20 SaaS vendor reviews using real buying scenarios",
                "PDF and Markdown reports for internal decision records",
                "Due-diligence questions for the chosen vendors",
                "End-of-pilot review session with recommended next steps",
            ],
        },
        {
            "name": "Team pilot",
            "price": "From £3,000",
            "duration": "4 weeks",
            "cases": "20–40 reviews",
            "badge": "For busier teams",
            "description": "For teams that want to test VendorVerdict across multiple buying scenarios or departments.",
            "features": [
                "Everything in the founding pilot",
                "More vendor reviews and saved procurement artifacts",
                "Two review sessions for workflow calibration",
                "Simple pilot summary with themes, gaps, and process recommendations",
                "Support for refining the scoring rubric around your risk appetite",
            ],
        },
        {
            "name": "Advisor / agency pilot",
            "price": "Custom",
            "duration": "4–6 weeks",
            "cases": "Client-facing workflow",
            "badge": "For consultants",
            "description": "For consultants, agencies, or advisors who want to use VendorVerdict with clients.",
            "features": [
                "Client-ready sample reports",
                "Reusable due-diligence question packs",
                "Workflow mapping for your advisory process",
                "Optional white-label discussion",
                "Commercial model review for ongoing usage",
            ],
        },
    ]

def _lead_default_values(*, source: str = "demo") -> dict[str, str]:
    return {
        "name": "",
        "email": "",
        "company": "",
        "use_case": "",
        "vendors": "",
        "message": "",
        "source": source,
    }


def _lead_values_from_form(form: dict[str, str]) -> dict[str, str]:
    values = _lead_default_values(source=form.get("source", "demo") or "demo")
    for key in values:
        values[key] = form.get(key, values[key]).strip()
    return values


def _validate_lead_values(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if len(values.get("name", "")) < 2:
        errors.append("Enter your name.")
    email = values.get("email", "")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        errors.append("Enter a valid email address.")
    if len(values.get("use_case", "")) < 5 and len(values.get("vendors", "")) < 3:
        errors.append("Tell us what you want to review, or which vendors you are considering.")
    return errors


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



def _dashboard_default_values() -> dict[str, Any]:
    return {
        "vendors": "Notion, Airtable",
        "use_case": "storing client project data",
        "team_size": "10",
        "region": "UK",
        "data_sensitivity": "medium-high",
        "query": DEMO_QUERY,
        "live_evidence": False,
        "export_markdown": True,
        "export_pdf": True,
    }


def _dashboard_values_from_form(form: dict[str, str], *, query: str) -> dict[str, Any]:
    return {
        "vendors": form.get("vendors", "").strip(),
        "use_case": form.get("use_case", "").strip(),
        "team_size": form.get("team_size", "").strip(),
        "region": form.get("region", "").strip(),
        "data_sensitivity": form.get("data_sensitivity", "").strip(),
        "query": query or form.get("query", "").strip(),
        "live_evidence": form.get("live_evidence") in {"1", "true", "on", "yes"},
        "export_markdown": form.get("export_markdown") in {"1", "true", "on", "yes"},
        "export_pdf": form.get("export_pdf") in {"1", "true", "on", "yes"},
    }


def _compose_dashboard_query(form: dict[str, str]) -> str:
    explicit_query = form.get("query", "").strip()
    vendors = form.get("vendors", "").strip()
    use_case = form.get("use_case", "").strip()
    team_size = form.get("team_size", "").strip()
    region = form.get("region", "").strip()
    data_sensitivity = form.get("data_sensitivity", "").strip()

    if vendors and use_case:
        details: list[str] = []
        if team_size:
            details.append(f"for a {team_size}-person team")
        if region:
            details.append(f"in {region}")
        if data_sensitivity:
            details.append(f"with {data_sensitivity} data sensitivity")
        suffix = " " + " ".join(details) if details else ""
        return f"Compare {vendors} for {use_case}{suffix}."

    return explicit_query

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
