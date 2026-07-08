from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from vendorverdict.proposals import ProposalRecord, ProposalStore, build_proposal_email


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
    """Create a structured PDF from a proposal record."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.6 * inch,
        title=f"VendorVerdict Commercial Proposal {proposal.company}",
        author="VendorVerdict",
    )
    styles = _styles()
    story: list[Any] = []

    story.append(Paragraph("VendorVerdict", styles["TitleBrand"]))
    story.append(Paragraph("Commercial Proposal", styles["Subtitle"]))
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph(_safe(proposal.company), styles["Heading1"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(_summary_table(proposal, styles))
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph(_safe(PROPOSAL_DISCLAIMER), styles["SmallMuted"]))
    story.append(Spacer(1, 0.22 * inch))

    story.append(Paragraph("Proposed Scope", styles["Heading1"]))
    story.append(_paragraph_block(proposal.scope or "To be agreed.", styles))
    story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("Success Criteria", styles["Heading1"]))
    story.append(_paragraph_block(proposal.success_criteria or "To be agreed.", styles))
    story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("Suggested Next Step", styles["Heading1"]))
    story.append(_paragraph_block(proposal.next_step or "Book a commercial follow-up call.", styles))
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("Customer Contact", styles["Heading1"]))
    story.append(_two_col_table([
        ["Contact", proposal.contact_name or "-"],
        ["Email", proposal.contact_email or "-"],
        ["Company", proposal.company or "-"],
        ["Pilot ID", proposal.pilot_id or "-"],
    ], styles))
    story.append(Spacer(1, 0.18 * inch))

    email = build_proposal_email(proposal)
    story.append(Paragraph("Follow-Up Email Draft", styles["Heading1"]))
    story.append(Paragraph(_safe(f"Subject: {email.subject}"), styles["BodyBold"]))
    story.append(Paragraph(_safe(email.body).replace("\n", "<br/>"), styles["MonoBlock"]))
    story.append(Spacer(1, 0.18 * inch))

    if proposal.notes:
        story.append(Paragraph("Internal Notes", styles["Heading1"]))
        story.append(_paragraph_block(proposal.notes, styles))
        story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("Disclaimer", styles["Heading1"]))
    story.append(Paragraph(_safe(PROPOSAL_DISCLAIMER), styles["Body"]))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "TitleBrand": ParagraphStyle(
            "ProposalTitleBrand",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=30,
            textColor=colors.HexColor("#1F2A7A"),
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "Subtitle": ParagraphStyle(
            "ProposalSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#3B4A68"),
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "Heading1": ParagraphStyle(
            "ProposalHeading1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#18233F"),
            spaceBefore=4,
            spaceAfter=8,
        ),
        "Body": ParagraphStyle(
            "ProposalBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.2,
            textColor=colors.HexColor("#222222"),
            spaceAfter=4,
        ),
        "BodyBold": ParagraphStyle(
            "ProposalBodyBold",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.2,
            leading=12.2,
            textColor=colors.HexColor("#222222"),
            spaceAfter=6,
        ),
        "Small": ParagraphStyle(
            "ProposalSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.7,
            leading=9.6,
            textColor=colors.HexColor("#222222"),
        ),
        "SmallMuted": ParagraphStyle(
            "ProposalSmallMuted",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#5A657A"),
        ),
        "MonoBlock": ParagraphStyle(
            "ProposalMonoBlock",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=7.8,
            leading=9.7,
            backColor=colors.HexColor("#F4F6FB"),
            borderColor=colors.HexColor("#D8DEEF"),
            borderWidth=0.5,
            borderPadding=6,
            textColor=colors.HexColor("#1E2430"),
        ),
    }


def _summary_table(proposal: ProposalRecord, styles: dict[str, ParagraphStyle]) -> Table:
    return _two_col_table([
        ["Proposal ID", proposal.proposal_id],
        ["Created", proposal.created_at],
        ["Updated", proposal.updated_at],
        ["Status", proposal.status.replace("_", " ")],
        ["Package", proposal.package_label],
        ["Proposed price", proposal.proposed_price or "To be agreed"],
        ["Billing", proposal.billing or "To be agreed"],
    ], styles)


def _two_col_table(rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(_safe(k), styles["Small"]), Paragraph(_safe(v), styles["Small"])] for k, v in rows]
    table = Table(data, colWidths=[1.45 * inch, 4.95 * inch], hAlign="LEFT")
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


def _paragraph_block(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(_safe(text).replace("\n", "<br/>"), styles["Body"])


def _page_footer(canvas: Any, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(0.55 * inch, 0.35 * inch, "VendorVerdict commercial proposal")
    canvas.drawRightString(A4[0] - 0.55 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _safe(value: Any) -> str:
    return escape(str(value or ""))
