from __future__ import annotations

import json
import os
from contextlib import closing
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from vendorverdict.models import VendorScore, VendorVerdict


@dataclass(frozen=True)
class EvidenceItem:
    vendor: str
    source_label: str
    source_url: str
    source_type: str
    ok: bool | None
    status_code: int | None
    final_url: str | None
    note: str
    confidence: str


@dataclass(frozen=True)
class ReportSummary:
    report_id: str
    created_at: str
    mode: str
    vendors: tuple[str, ...]
    use_case: str
    recommended_vendor: str | None
    overall_confidence: str

    def __getitem__(self, key: str) -> Any:
        mapping = {
            "id": self.report_id,
            "created_at": self.created_at,
            "report_type": self.mode,
            "mode": self.mode,
            "vendors_json": json.dumps(list(self.vendors)),
            "vendors": self.vendors,
            "use_case": self.use_case,
            "recommendation": self.recommended_vendor,
            "recommended_vendor": self.recommended_vendor,
            "confidence": self.overall_confidence,
            "overall_confidence": self.overall_confidence,
        }
        return mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


@dataclass(frozen=True)
class ReportRecord(ReportSummary):
    raw_query: str
    report_text: str
    request_json: dict[str, Any]
    scores_json: list[dict[str, Any]]
    collaboration_steps: tuple[str, ...]
    critic_warnings: tuple[str, ...]
    metadata_json: dict[str, Any] = field(default_factory=dict)
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    evidence_findings: list[dict[str, Any]] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        if key == "raw_query":
            return self.raw_query
        if key in {"rendered_response", "report_text"}:
            return self.report_text
        if key in {"request", "request_json"}:
            return self.request_json
        if key in {"scores", "scores_json"}:
            return self.scores_json
        if key == "collaboration_steps":
            return self.collaboration_steps
        if key == "critic_warnings":
            return self.critic_warnings
        if key in {"metadata", "metadata_json"}:
            return self.metadata_json
        if key == "evidence_items":
            return self.evidence_items
        if key == "evidence_findings":
            return self.evidence_findings
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class ReportStore:
    """SQLite-backed report store for the first production persistence layer."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = Path(db_path or default_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save_report(
        self,
        verdict: VendorVerdict,
        report_text: str,
        *,
        raw_query: str | None = None,
        mode: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        report_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        request = verdict.request
        recommendation = verdict.recommendation
        report_mode = mode or infer_report_mode(verdict)
        scores_json = [asdict(score) for score in verdict.scores]

        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO reports (
                    id, created_at, raw_query, mode, vendors_json, use_case,
                    recommended_vendor, overall_confidence, report_text,
                    request_json, scores_json, collaboration_steps_json,
                    critic_warnings_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    created_at,
                    raw_query or request.raw_query,
                    report_mode,
                    json.dumps(list(request.vendors)),
                    request.use_case,
                    recommendation.vendor if recommendation else None,
                    verdict.confidence,
                    report_text,
                    json.dumps(asdict(request), ensure_ascii=False),
                    json.dumps(scores_json, ensure_ascii=False),
                    json.dumps(list(verdict.collaboration_steps), ensure_ascii=False),
                    json.dumps(list(verdict.critic_warnings), ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            self._insert_scores(conn, report_id, verdict.scores)
            self._insert_sources(conn, report_id, verdict.scores)
            self._insert_findings(conn, report_id, verdict.scores)
            conn.commit()
        return report_id

    def list_reports(self, limit: int = 20) -> list[ReportSummary]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, mode, vendors_json, use_case,
                       recommended_vendor, overall_confidence
                FROM reports
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ReportSummary(
                report_id=row["id"],
                created_at=row["created_at"],
                mode=row["mode"],
                vendors=tuple(json.loads(row["vendors_json"])),
                use_case=row["use_case"],
                recommended_vendor=row["recommended_vendor"],
                overall_confidence=row["overall_confidence"],
            )
            for row in rows
        ]

    def get_report(self, report_id: str) -> ReportRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT id, created_at, raw_query, mode, vendors_json, use_case,
                       recommended_vendor, overall_confidence, report_text,
                       request_json, scores_json, collaboration_steps_json,
                       critic_warnings_json, metadata_json
                FROM reports
                WHERE id = ?
                """,
                (report_id,),
            ).fetchone()
        if row is None:
            return None
        evidence_items = self.list_sources(report_id)
        evidence_findings = self.list_findings(report_id)
        return ReportRecord(
            report_id=row["id"],
            created_at=row["created_at"],
            raw_query=row["raw_query"],
            mode=row["mode"],
            vendors=tuple(json.loads(row["vendors_json"])),
            use_case=row["use_case"],
            recommended_vendor=row["recommended_vendor"],
            overall_confidence=row["overall_confidence"],
            report_text=row["report_text"],
            request_json=json.loads(row["request_json"]),
            scores_json=json.loads(row["scores_json"]),
            collaboration_steps=tuple(json.loads(row["collaboration_steps_json"])),
            critic_warnings=tuple(json.loads(row["critic_warnings_json"])),
            metadata_json=json.loads(row["metadata_json"]),
            evidence_items=evidence_items,
            evidence_findings=evidence_findings,
        )

    def list_sources(self, report_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT vendor, label, url, ok, status_code, final_url, note, source_type, confidence
                FROM report_sources
                WHERE report_id = ?
                ORDER BY vendor, label
                """,
                (report_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_findings(self, report_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT vendor, signal, label, source_label, source_url, snippet, confidence, checked_at
                FROM report_findings
                WHERE report_id = ?
                ORDER BY vendor, source_label, label
                """,
                (report_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def render_markdown(self, report_id: str) -> str:
        record = self.get_report(report_id)
        if record is None:
            raise KeyError(f"Report not found: {report_id}")
        return render_report_markdown(record, sources=self.list_sources(report_id))

    def export_markdown(self, report_id: str, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(self.render_markdown(report_id), encoding="utf-8")
        return output

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    raw_query TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    vendors_json TEXT NOT NULL,
                    use_case TEXT NOT NULL,
                    recommended_vendor TEXT,
                    overall_confidence TEXT NOT NULL,
                    report_text TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    scores_json TEXT NOT NULL,
                    collaboration_steps_json TEXT NOT NULL,
                    critic_warnings_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS report_scores (
                    report_id TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    overall INTEGER NOT NULL,
                    security INTEGER NOT NULL,
                    privacy INTEGER NOT NULL,
                    pricing_predictability INTEGER NOT NULL,
                    lock_in INTEGER NOT NULL,
                    sme_fit INTEGER NOT NULL,
                    operational_maturity INTEGER NOT NULL,
                    confidence TEXT NOT NULL,
                    PRIMARY KEY (report_id, vendor),
                    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS report_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    label TEXT NOT NULL,
                    url TEXT NOT NULL,
                    ok INTEGER,
                    status_code INTEGER,
                    final_url TEXT,
                    note TEXT,
                    source_type TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS report_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    label TEXT NOT NULL,
                    source_label TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    snippet TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    checked_at TEXT,
                    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_report_sources_report ON report_sources(report_id);
                CREATE INDEX IF NOT EXISTS idx_report_findings_report ON report_findings(report_id);
                """
            )
            conn.commit()

    def _insert_scores(self, conn: sqlite3.Connection, report_id: str, scores: tuple[VendorScore, ...]) -> None:
        for score in scores:
            conn.execute(
                """
                INSERT INTO report_scores (
                    report_id, vendor, overall, security, privacy,
                    pricing_predictability, lock_in, sme_fit,
                    operational_maturity, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    score.vendor,
                    score.overall,
                    score.security,
                    score.privacy,
                    score.pricing_predictability,
                    score.lock_in,
                    score.sme_fit,
                    score.operational_maturity,
                    score.confidence,
                ),
            )

    def _insert_sources(self, conn: sqlite3.Connection, report_id: str, scores: tuple[VendorScore, ...]) -> None:
        for score in scores:
            if score.source_checks:
                for check in score.source_checks:
                    conn.execute(
                        """
                        INSERT INTO report_sources (
                            report_id, vendor, label, url, ok, status_code,
                            final_url, note, source_type, confidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            report_id,
                            score.vendor,
                            check.label,
                            check.url,
                            1 if check.ok else 0,
                            check.status_code,
                            check.final_url,
                            check.note,
                            "live_check",
                            score.confidence,
                        ),
                    )
            else:
                for idx, url in enumerate(score.evidence_urls, start=1):
                    conn.execute(
                        """
                        INSERT INTO report_sources (
                            report_id, vendor, label, url, ok, status_code,
                            final_url, note, source_type, confidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            report_id,
                            score.vendor,
                            f"fallback_source_{idx}",
                            url,
                            None,
                            None,
                            None,
                            "curated fallback official-source target",
                            "fallback",
                            score.confidence,
                        ),
                    )

    def _insert_findings(self, conn: sqlite3.Connection, report_id: str, scores: tuple[VendorScore, ...]) -> None:
        for score in scores:
            for finding in score.extracted_findings:
                conn.execute(
                    """
                    INSERT INTO report_findings (
                        report_id, vendor, signal, label, source_label, source_url,
                        snippet, confidence, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        finding.vendor or score.vendor,
                        finding.signal,
                        finding.label,
                        finding.source_label,
                        finding.source_url,
                        finding.snippet,
                        finding.confidence,
                        finding.checked_at,
                    ),
                )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def default_db_path() -> Path:
    env_path = os.getenv("VENDORVERDICT_DB_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return Path.home() / ".vendorverdict" / "vendorverdict.sqlite3"


def infer_report_mode(verdict: VendorVerdict) -> str:
    return "single_vendor_audit" if len(verdict.request.vendors) == 1 else "multi_vendor_comparison"


def evidence_items_from_verdict(verdict: VendorVerdict) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for score in verdict.scores:
        if score.source_checks:
            for check in score.source_checks:
                items.append(
                    EvidenceItem(
                        vendor=score.vendor,
                        source_label=check.label,
                        source_url=check.url,
                        source_type="live_check",
                        ok=check.ok,
                        status_code=check.status_code,
                        final_url=check.final_url,
                        note=check.note,
                        confidence=score.confidence,
                    )
                )
        else:
            for idx, url in enumerate(score.evidence_urls, start=1):
                items.append(
                    EvidenceItem(
                        vendor=score.vendor,
                        source_label=f"fallback_source_{idx}",
                        source_url=url,
                        source_type="fallback",
                        ok=None,
                        status_code=None,
                        final_url=None,
                        note="curated fallback official-source target; live evidence not checked",
                        confidence=score.confidence,
                    )
                )
    return items


def render_report_markdown(record: ReportRecord, sources: list[dict[str, Any]] | None = None) -> str:
    vendors = ", ".join(record.vendors)
    lines = [
        f"# VendorVerdict Report: {vendors}",
        "",
        f"- Report ID: `{record.report_id}`",
        f"- Created: {record.created_at}",
        f"- Mode: {record.mode}",
        f"- Use case: {record.use_case}",
        f"- Recommended vendor: {record.recommended_vendor or 'N/A'}",
        f"- Confidence: {record.overall_confidence}",
        "",
        "## Report",
        "",
        record.report_text,
        "",
        "## Structured scores",
        "",
        "| Vendor | Overall | Security | Privacy | Pricing | Lock-in | SME fit | Confidence |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for score in record.scores_json:
        lines.append(
            f"| {score['vendor']} | {score['overall']} | {score['security']} | "
            f"{score['privacy']} | {score['pricing_predictability']} | {score['lock_in']} | "
            f"{score['sme_fit']} | {score['confidence']} |"
        )
    lines.extend(["", "## Evidence snapshot", ""])
    sources = sources or []
    if sources:
        lines.append("| Vendor | Source | Type | Reachable | Status | URL | Note |")
        lines.append("|---|---|---|---|---:|---|---|")
        for source in sources:
            reachable = "yes" if source.get("ok") == 1 else "no" if source.get("ok") == 0 else "fallback"
            status = source.get("status_code") or ""
            url = source.get("url") or ""
            if source.get("final_url"):
                url = f"{url} → {source['final_url']}"
            lines.append(
                f"| {source.get('vendor', '')} | {source.get('label', '')} | {source.get('source_type', '')} | "
                f"{reachable} | {status} | {url} | {source.get('note', '')} |"
            )
    else:
        lines.append("No structured evidence rows were stored for this report.")
    lines.extend(["", "## Extracted evidence findings", ""])
    findings = record.evidence_findings
    if findings:
        lines.append("| Vendor | Finding | Source | Confidence | Snippet |")
        lines.append("|---|---|---|---|---|")
        for finding in findings:
            snippet = str(finding.get("snippet", "")).replace("|", "\\|")
            source = f"{finding.get('source_label', '')}: {finding.get('source_url', '')}"
            lines.append(
                f"| {finding.get('vendor', '')} | {finding.get('label', '')} | {source} | "
                f"{finding.get('confidence', '')} | {snippet} |"
            )
    else:
        lines.append("No extracted evidence findings were stored for this report.")
    lines.extend(["", "---", "", "Generated by VendorVerdict."])
    return "\n".join(lines)
