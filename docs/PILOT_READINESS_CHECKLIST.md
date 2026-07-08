# Pilot readiness checklist

VendorVerdict now includes a protected pilot-readiness page at `/dashboard/readiness`.

Use it before outreach, before a customer demo, and after each production deploy. It checks that the customer-facing workflow is ready end to end:

1. Public product pages: home, demo, pricing, pilot request, trust, privacy, disclaimer.
2. Lead capture: a test pilot request has been saved.
3. Vendor review reports: at least one report has been generated and exports work.
4. Pilot workspace: at least one lead has been converted into a pilot workspace.
5. Commercial proposal workflow: at least one proposal exists and can export customer Markdown/PDF.
6. Customer share links: at least one report or proposal share link exists and can be tested in incognito.
7. Admin settings: public URL and default commercial settings are confirmed.

The readiness score is an operational checklist for the workflow. It is not legal advice, security certification, compliance certification, or a substitute for a customer-specific review.

## Recommended final smoke test

After deploying, run this manual journey:

1. Open `/`, `/demo`, `/pricing`, `/pilot`, `/trust`, `/privacy`, and `/disclaimer` in an incognito window.
2. Submit one test pilot request.
3. Log in and open `/dashboard/leads`.
4. Convert the lead into a pilot workspace.
5. Run one pilot vendor review and export PDF/Markdown.
6. Open the pilot outcome page.
7. Create a commercial proposal and download the customer PDF.
8. Create a share link and test the public customer link in incognito.
9. Run the VM status script:

```bash
sudo /opt/vendorverdict/scripts/status_vendorverdict.sh
```

## Deployment check

After deployment, open:

```text
https://vendorverdict.docoply.com/dashboard/readiness
```
