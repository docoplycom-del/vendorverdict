# Contrast accessibility hardening

VendorVerdict uses a dark interface. The demo and pilot forms use light input fields, so form text, placeholder text, and button text must be explicitly declared rather than inherited from the dark page theme.

This update fixes two production issues:

- Primary button text inside cards was being overridden by the generic `.card a` rule.
- Lead capture inputs and textareas inherited light text from the dark page theme while using white field backgrounds.

The stylesheet now includes a final high-specificity contrast block for:

- primary buttons and visited button links,
- secondary buttons,
- form inputs,
- textareas,
- placeholder text,
- focus states,
- demo and dashboard lead capture forms.

The base template also uses a versioned stylesheet URL so browsers fetch the new CSS immediately after deployment.

## Manual checks

Open these pages after deployment:

- `/demo`
- `/pilot`
- `/dashboard`
- `/dashboard/leads`

Check that:

- primary button text is dark and readable on the turquoise/green gradient,
- secondary button text is white and readable,
- input text is dark on white backgrounds,
- placeholder text is dark grey on white backgrounds,
- focused form fields have a visible focus outline.
