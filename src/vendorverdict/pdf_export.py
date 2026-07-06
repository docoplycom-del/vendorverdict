from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from vendorverdict.storage import ReportRecord, ReportStore


DISCLAIMER = (
    "VendorVerdict provides procurement guidance based on public evidence and configured "
    "fallback sources. It is not legal advice, financial advice, or a formal security audit."
)


def export_report_pdf(
    report_id: str,
    output_dir: str | Path = "reports",
    store: ReportStore | None = None,
) -> Path:
    """Export a stored VendorVerdict report as a client-ready PDF file."""
    report_store = store or ReportStore()
    report = report_store.get_report(report_id)
    if report is None:
        raise KeyError(f"Report not found: {report_id}")

    output_path = Path(output_dir) / f"vendorverdict-report-{report_id}.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_report_pdf(report, output_path)
    return output_path


def build_report_pdf(report: ReportRecord, output_path: str | Path) -> Path:
    """Create a structured PDF from a stored report record."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.6 * inch,
        title=f"VendorVerdict Report {report.report_id}",
        author="VendorVerdict",
    )
    styles = _styles()
    story: list[Any] = []

    vendors = ", ".join(report.vendors)
    story.append(Paragraph("VendorVerdict", styles["TitleBrand"]))
    story.append(Paragraph("SaaS Vendor-Risk Report", styles["Subtitle"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(_safe(vendors), styles["Heading1"]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(_metadata_table(report, styles))
    story.append(Spacer(1, 0.22 * inch))
    story.append(Paragraph(_safe(DISCLAIMER), styles["SmallMuted"]))
    story.append(PageBreak())

    story.append(Paragraph("Executive Summary", styles["Heading1"]))
    story.extend(_bullets([
        f"Recommended vendor: {report.recommended_vendor or 'N/A'}",
        f"Use case: {report.use_case}",
        f"Overall confidence: {report.overall_confidence}",
        f"Report type: {report.mode.replace('_', ' ')}",
    ], styles))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Structured Scorecard", styles["Heading1"]))
    story.append(_score_table(report, styles))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Multi-Agent Workflow", styles["Heading1"]))
    story.extend(_numbered_list(report.collaboration_steps, styles))
    story.append(Spacer(1, 0.2 * inch))

    if report.critic_warnings:
        story.append(Paragraph("Critic Agent Notes", styles["Heading1"]))
        story.extend(_bullets(report.critic_warnings, styles))
        story.append(Spacer(1, 0.2 * inch))

    story.append(PageBreak())
    story.append(Paragraph("Evidence-Backed Findings", styles["Heading1"]))
    story.append(Paragraph(
        "These findings are extracted from reachable public vendor pages and stored with source URLs, snippets, confidence, and timestamps.",
        styles["Body"],
    ))
    story.append(Spacer(1, 0.12 * inch))
    story.extend(_finding_sections(report, styles))

    story.append(PageBreak())
    story.append(Paragraph("Source Snapshot", styles["Heading1"]))
    story.append(_source_table(report, styles))
    story.append(Spacer(1, 0.2 * inch))

    email = _extract_due_diligence_email(report.report_text)
    if email:
        story.append(Paragraph("Due-Diligence Email", styles["Heading1"]))
        story.append(Paragraph(_safe(email).replace("\n", "<br/>"), styles["MonoBlock"]))
        story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Disclaimer", styles["Heading1"]))
    story.append(Paragraph(_safe(DISCLAIMER), styles["Body"]))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {
        "TitleBrand": ParagraphStyle(
            "TitleBrand",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=30,
            textColor=colors.HexColor("#1F2A7A"),
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#3B4A68"),
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "Heading1": ParagraphStyle(
            "Heading1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#18233F"),
            spaceBefore=4,
            spaceAfter=8,
        ),
        "Heading2": ParagraphStyle(
            "Heading2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#263B7A"),
            spaceBefore=6,
            spaceAfter=5,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.2,
            textColor=colors.HexColor("#222222"),
            spaceAfter=4,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.4,
            textColor=colors.HexColor("#222222"),
        ),
        "SmallHeader": ParagraphStyle(
            "SmallHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.4,
            textColor=colors.white,
        ),
        "SmallMuted": ParagraphStyle(
            "SmallMuted",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#5A657A"),
        ),
        "MonoBlock": ParagraphStyle(
            "MonoBlock",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=7.7,
            leading=9.6,
            backColor=colors.HexColor("#F4F6FB"),
            borderColor=colors.HexColor("#D8DEEF"),
            borderWidth=0.5,
            borderPadding=6,
            textColor=colors.HexColor("#1E2430"),
        ),
    }
    return styles


def _metadata_table(report: ReportRecord, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["Report ID", report.report_id],
        ["Created", report.created_at],
        ["Mode", report.mode.replace("_", " ")],
        ["Use case", report.use_case],
        ["Recommended", report.recommended_vendor or "N/A"],
        ["Confidence", report.overall_confidence],
    ]
    return _two_col_table(rows, styles)


def _two_col_table(rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(_safe(k), styles["Small"]), Paragraph(_safe(v), styles["Small"])] for k, v in rows]
    table = Table(data, colWidths=[1.35 * inch, 5.0 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FF")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D6DCEA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _score_table(report: ReportRecord, styles: dict[str, ParagraphStyle]) -> Table:
    headers = ["Vendor", "Overall", "Security", "Privacy", "Pricing", "Lock-in", "SME", "Conf."]
    data: list[list[Any]] = [[Paragraph(h, styles["SmallHeader"]) for h in headers]]
    for score in report.scores_json:
        data.append([
            Paragraph(_safe(score.get("vendor", "")), styles["Small"]),
            score.get("overall", ""),
            score.get("security", ""),
            score.get("privacy", ""),
            score.get("pricing_predictability", ""),
            score.get("lock_in", ""),
            score.get("sme_fit", ""),
            Paragraph(_safe(score.get("confidence", "")), styles["Small"]),
        ])
    col_widths = [1.3 * inch, 0.65 * inch, 0.65 * inch, 0.65 * inch, 0.65 * inch, 0.65 * inch, 0.55 * inch, 0.65 * inch]
    table = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2A7A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFF")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D6DCEA")),
        ("ALIGN", (1, 1), (-2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _source_table(report: ReportRecord, styles: dict[str, ParagraphStyle]) -> Table | Paragraph:
    sources = report.evidence_items[:30]
    if not sources:
        return Paragraph("No structured source snapshot is stored for this report.", styles["Body"])
    data: list[list[Any]] = [[
        Paragraph("Vendor", styles["SmallHeader"]),
        Paragraph("Source", styles["SmallHeader"]),
        Paragraph("Reach", styles["SmallHeader"]),
        Paragraph("URL", styles["SmallHeader"]),
    ]]
    for source in sources:
        ok = source.get("ok")
        reach = "fallback" if ok is None else "yes" if ok in {1, True} else "no"
        url = source.get("url") or ""
        final_url = source.get("final_url")
        if final_url and final_url != url:
            url = f"{url} -> {final_url}"
        data.append([
            Paragraph(_safe(source.get("vendor", "")), styles["Small"]),
            Paragraph(_safe(source.get("label", "")), styles["Small"]),
            Paragraph(_safe(reach), styles["Small"]),
            Paragraph(_safe(_truncate(url, 95)), styles["Small"]),
        ])
    table = Table(data, colWidths=[1.05 * inch, 1.0 * inch, 0.6 * inch, 4.0 * inch], hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2A7A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6DCEA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _finding_sections(report: ReportRecord, styles: dict[str, ParagraphStyle]) -> list[Any]:
    findings = report.evidence_findings
    if not findings:
        return [Paragraph("No extracted evidence findings are stored for this report.", styles["Body"])]

    output: list[Any] = []
    by_vendor: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        by_vendor.setdefault(str(finding.get("vendor", "Unknown")), []).append(finding)

    for vendor, vendor_findings in by_vendor.items():
        output.append(Paragraph(_safe(vendor), styles["Heading2"]))
        for finding in vendor_findings[:10]:
            label = finding.get("label", "Finding")
            confidence = finding.get("confidence", "")
            source_label = finding.get("source_label", "source")
            source_url = finding.get("source_url", "")
            snippet = finding.get("snippet", "")
            text = (
                f"<b>{_safe(label)}</b> - {_safe(confidence)} confidence<br/>"
                f"Source: {_safe(source_label)} - {_safe(_truncate(source_url, 90))}<br/>"
                f"Snippet: {_safe(_truncate(snippet, 260))}"
            )
            output.append(Paragraph(text, styles["Body"]))
            output.append(Spacer(1, 0.04 * inch))
        if len(vendor_findings) > 10:
            output.append(Paragraph(f"+{len(vendor_findings) - 10} more finding(s) stored in the report database.", styles["SmallMuted"]))
        output.append(Spacer(1, 0.1 * inch))
    return output


def _bullets(items: tuple[str, ...] | list[str], styles: dict[str, ParagraphStyle]) -> list[Any]:
    output: list[Any] = []
    for item in items:
        output.append(Paragraph(f"- {_safe(item)}", styles["Body"]))
    return output


def _numbered_list(items: tuple[str, ...] | list[str], styles: dict[str, ParagraphStyle]) -> list[Any]:
    output: list[Any] = []
    for idx, item in enumerate(items, start=1):
        output.append(Paragraph(f"{idx}. {_safe(item)}", styles["Body"]))
    return output


def _extract_due_diligence_email(text: str) -> str | None:
    match = re.search(r"Due-diligence email:\s*```text\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _safe(value: object) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "→": "->",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "✅": "",
        "🏆": "",
        "🧾": "",
        "💎": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Keep ReportLab built-in fonts happy by removing unsupported astral-plane emoji.
    text = "".join(ch for ch in text if ord(ch) <= 0xFFFF)
    return escape(text)


def _truncate(value: object, limit: int) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _page_footer(canvas, doc) -> None:  # pragma: no cover - visual layout callback
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(0.55 * inch, 0.35 * inch, "VendorVerdict - procurement guidance only")
    canvas.drawRightString(A4[0] - 0.55 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()
