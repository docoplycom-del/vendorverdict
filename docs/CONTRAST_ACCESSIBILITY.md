# Contrast and accessibility polish

This update fixes the visual contrast issue reported on the public demo and dashboard pages.

## What changed

- Primary buttons inside cards now keep dark text on the cyan/green gradient.
- Secondary buttons keep light text on dark backgrounds.
- Lead-capture form fields now use dark inputs with high-contrast text.
- Placeholder text is readable on demo and pilot forms.
- Focus states are visible for inputs, buttons, links, and textarea controls.
- Lead/dashboard tables have clearer headers, row text, and hover states.

## Pages checked

- `/demo`
- `/pilot`
- `/dashboard`
- `/dashboard/leads`
- `/reviews/new`

## Deploy

Use the safe deploy script:

```bash
cd /tmp/vendorverdict
git pull origin main
sudo scripts/deploy_gcp_vm.sh
```

Then check:

```bash
curl -i https://vendorverdict.docoply.com/demo
curl -i https://vendorverdict.docoply.com/pilot
curl -i https://vendorverdict.docoply.com/dashboard
```
