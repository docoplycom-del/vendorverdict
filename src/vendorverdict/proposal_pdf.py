from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from vendorverdict.proposals import ProposalRecord, ProposalStore, customer_next_step, customer_success_criteria


PROPOSAL_DISCLAIMER = (
    "This VendorVerdict proposal is a commercial discussion document. It is not legal advice, "
    "financial advice, a formal security audit, or a binding contract unless separately agreed in writing."
)


def export_proposal_pdf(
    proposal_id: str,
    output_dir: str | Path = "reports",
    store: ProposalStore | None = None,
) -> Path:
    """Export a stored commercial proposal as a customer-ready PDF."""
    proposal_store = store or ProposalStore()
    proposal = proposal_store.get_proposal(proposal_id)
    if proposal is None:
        raise KeyError(f"Proposal not found: {proposal_id}")

    output_path = Path(output_dir) / f"vendorverdict-commercial-proposal-{proposal_id}.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_proposal_pdf(proposal, output_path)
    return output_path


def build_proposal_pdf(proposal: ProposalRecord, output_path: str | Path) -> Path:
    """Create a customer-facing proposal PDF from a proposal record.

    The PDF intentionally excludes internal pipeline status, internal notes, raw timestamps,
    follow-up email drafts, and pilot IDs. Those remain available on the protected dashboard.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.6 * inch,
        title=f"VendorVerdict Proposal {proposal.company}",
        author="VendorVerdict",
    )
    styles = _styles()
    story: list[Any] = []

    story.append(Paragraph("VendorVerdict", styles["TitleBrand"]))
    story.append(Paragraph("Customer proposal", styles["Subtitle"]))
    story.append(Spacer(1, 0.14 * inch))

    story.append(_hero_box(proposal, styles))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Proposed scope", styles["Heading1"]))
    story.append(_paragraph_block(proposal.scope or "To be agreed.", styles))
    story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("Success criteria", styles["Heading1"]))
    story.append(_paragraph_block(customer_success_criteria(proposal.success_criteria) or "To be agreed.", styles))
    story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("Suggested next step", styles["Heading1"]))
    story.append(_cta_box(customer_next_step(proposal.next_step), styles))
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("Contact", styles["Heading1"]))
    story.append(_two_col_table([
        ["Contact", proposal.contact_name or "-"],
        ["Email", proposal.contact_email or "-"],
        ["Company", proposal.company or "-"],
    ], styles))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Important note", styles["Heading1"]))
    story.append(Paragraph(_safe(PROPOSAL_DISCLAIMER), styles["SmallMuted"]))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "TitleBrand": ParagraphStyle(
            "ProposalTitleBrand",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=27,
            leading=31,
            textColor=colors.HexColor("#1F2A7A"),
            alignment=TA_CENTER,
            spaceAfter=5,
        ),
        "Subtitle": ParagraphStyle(
            "ProposalSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#3B4A68"),
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "HeroCompany": ParagraphStyle(
            "ProposalHeroCompany",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=6,
        ),
        "HeroMuted": ParagraphStyle(
            "ProposalHeroMuted",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.2,
            textColor=colors.HexColor("#475569"),
            spaceAfter=5,
        ),
        "Heading1": ParagraphStyle(
            "ProposalHeading1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14.5,
            leading=18.5,
            textColor=colors.HexColor("#18233F"),
            spaceBefore=3,
            spaceAfter=8,
        ),
        "Body": ParagraphStyle(
            "ProposalBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=12.4,
            textColor=colors.HexColor("#222222"),
            spaceAfter=4,
        ),
        "Small": ParagraphStyle(
            "ProposalSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=9.7,
            textColor=colors.HexColor("#222222"),
        ),
        "SmallBold": ParagraphStyle(
            "ProposalSmallBold",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.8,
            leading=9.7,
            textColor=colors.HexColor("#111827"),
        ),
        "SmallMuted": ParagraphStyle(
            "ProposalSmallMuted",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#5A657A"),
        ),
        "Cta": ParagraphStyle(
            "ProposalCta",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.2,
            leading=12.4,
            textColor=colors.HexColor("#0F172A"),
        ),
    }


def _hero_box(proposal: ProposalRecord, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [Paragraph(_safe(proposal.company), styles["HeroCompany"])],
        [Paragraph(_safe(f"Prepared {format_proposal_date(proposal.updated_at or proposal.created_at)}"), styles["HeroMuted"])],
        [_summary_table(proposal, styles)],
    ]
    table = Table(rows, colWidths=[6.35 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E0EE")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
    ]))
    return table


def _summary_table(proposal: ProposalRecord, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ["Proposal reference", _short_reference(proposal.proposal_id)],
        ["Package", proposal.package_label],
        ["Proposed price", proposal.proposed_price or "To be agreed"],
        ["Billing", proposal.billing or "To be agreed"],
    ]
    if proposal.invoice_reference:
        rows.append(["Invoice reference", proposal.invoice_reference])
    if proposal.payment_due:
        rows.append(["Payment due", proposal.payment_due])
    if proposal.payment_url:
        rows.append(["Payment link", proposal.payment_url])
    return _two_col_table(rows, styles)


def _two_col_table(rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(_safe(k), styles["SmallBold"]), Paragraph(_safe(v), styles["Small"])] for k, v in rows]
    table = Table(data, colWidths=[1.5 * inch, 4.55 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FF")),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D6DCEA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _cta_box(text: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table([[Paragraph(_safe(text), styles["Cta"])]], colWidths=[6.35 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E6FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#22D3EE")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


def _paragraph_block(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(_safe(text).replace("\n", "<br/>"), styles["Body"])


def format_proposal_date(value: str) -> str:
    if not value:
        return ""
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.strftime("%d %B %Y").lstrip("0")
    except ValueError:
        return value[:10] if len(value) >= 10 else value


def _short_reference(value: str) -> str:
    return (value or "").split("-")[0] or "-"


def _page_footer(canvas: Any, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(0.62 * inch, 0.35 * inch, "VendorVerdict customer proposal")
    canvas.drawRightString(A4[0] - 0.62 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _safe(value: Any) -> str:
    return escape(str(value or ""))
