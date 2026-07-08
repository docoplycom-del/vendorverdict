# Trust, privacy, and disclaimer pages

VendorVerdict includes lightweight public trust pages for pilot customers:

- `/trust` explains evidence-first reports, human approval, operational controls, and what not to submit.
- `/privacy` explains what the pilot instance collects and how it is used.
- `/disclaimer` clarifies that VendorVerdict is procurement decision support, not legal advice or a formal security audit.

The public navigation is intentionally focused on the customer journey:

- Home
- Demo
- Pilot package
- Request pilot
- Trust
- Login

Operational links such as API docs and health checks are still available to authenticated users and in the footer after login, but they are no longer promoted in the public nav.

## Why this matters

These pages make the product more credible before outreach. A pilot customer can understand:

- what VendorVerdict does and does not do;
- what data is stored;
- why human review is still required;
- why public demo users should not submit secrets or confidential documents;
- how the production instance is operated.

## Deployment

Use the safe VM deploy script:

```bash
cd /tmp/vendorverdict
sudo scripts/deploy_gcp_vm.sh
```

Then test:

```bash
curl -i https://vendorverdict.docoply.com/trust
curl -i https://vendorverdict.docoply.com/privacy
curl -i https://vendorverdict.docoply.com/disclaimer
```
