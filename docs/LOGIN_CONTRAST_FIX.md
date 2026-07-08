# Login contrast fix

This update hardens visual contrast on the protected login form.

## What changed

- Admin username and password fields now use a dark high-contrast input background.
- Placeholder, typed text, password bullets, caret colour, and browser autofill text are forced to readable colours.
- Primary button text is forced to white with a dark button background.
- The stylesheet URL is versioned as `style.css?v=20260708-login-contrast-final` to break browser caching.

## Verification

Open `/login` in a new incognito window or hard-refresh with Ctrl+F5. The username, password dots, and button text should be clearly visible.
