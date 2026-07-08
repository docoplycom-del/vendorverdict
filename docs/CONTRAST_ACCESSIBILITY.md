# Contrast and accessibility hardening

This release adds a final high-contrast CSS override for the public demo, pilot form, dashboard, lead inbox, and report actions.

## Fixed areas

- Primary action buttons such as `Request pilot`, `Start new vendor review`, and `View report`.
- Secondary dashboard buttons.
- Lead-capture inputs and textareas.
- Pilot page `Use case` and `Message` fields.
- Informational callouts such as `Best for`.
- Table headers, muted copy, metric labels, and dashboard helper text.

## Implementation

The CSS now uses a final override block at the end of `style.css` with high-specificity selectors under `html body`. Buttons use a dark high-contrast background with white text so they remain readable even if generic link styles partially override the colour. Forms use dark fields with light placeholder and typed text so text remains visible across Chrome, incognito windows, and cached sessions.

The base template uses a cache-busting stylesheet URL:

```html
/static/style.css?v=20260708-visual-contrast-final
```

After deployment, hard-refresh or open the pages in a new incognito window.
