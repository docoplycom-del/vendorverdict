# Commercial proposal PDF export

VendorVerdict can export tracked commercial proposals as customer-ready PDFs.

## Protected URL

```text
/dashboard/proposals/{proposal_id}.pdf
```

The route is protected by the same dashboard authentication as the proposal editor, Markdown export, reports, pilots, and lead management pages.

## What the PDF includes

- VendorVerdict commercial proposal title page
- proposal metadata and status
- package and proposed price
- billing model
- proposed scope
- success criteria
- suggested next step
- customer contact and linked pilot ID
- copy/paste follow-up email draft
- internal notes when present
- disclaimer

## Why this matters

Markdown is useful for editing, but a PDF is easier to send after a pilot close-out call. It gives a prospect a clear next step and makes the pilot-to-paid-work transition feel more professional.

## Production workflow

1. Open a pilot outcome page.
2. Create or open the commercial proposal.
3. Edit package, price, scope, success criteria, and next step.
4. Save the proposal.
5. Download the PDF from the proposal detail page.
6. Send the PDF with the generated follow-up email.

## Files

- `src/vendorverdict/proposal_pdf.py`
- `src/vendorverdict/api.py`
- `src/vendorverdict/web/templates/proposal_detail.html`
- `src/vendorverdict/web/templates/proposals.html`
- `tests/test_commercial_proposals.py`
- `tests/test_dashboard.py`
- `tests/test_auth.py`
