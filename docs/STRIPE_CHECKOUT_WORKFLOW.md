# Stripe Checkout workflow

This production step adds optional Stripe Checkout link creation to the protected proposal payment screen.

## What it adds

- A Stripe Checkout card on `/dashboard/proposals/{proposal_id}`.
- A protected POST route: `/dashboard/proposals/{proposal_id}/stripe-checkout`.
- Amount entry for the proposed payment.
- Checkout session creation through the Stripe API when configured.
- Automatic saving of the returned checkout URL as the proposal payment link.
- Automatic saving of the Stripe session ID as the proposal payment reference.
- Existing manual invoice/payment-link workflow remains available when Stripe is not configured.

## Environment variables

Keep Stripe secrets in `/etc/vendorverdict/vendorverdict.env`, not in git.

```env
VENDORVERDICT_STRIPE_CHECKOUT_ENABLED=1
VENDORVERDICT_STRIPE_SECRET_KEY=sk_live_or_test_key
VENDORVERDICT_STRIPE_CURRENCY=gbp
VENDORVERDICT_STRIPE_SUCCESS_URL=https://vendorverdict.docoply.com/dashboard/proposals/YOUR_PROPOSAL_ID?stripe=success
VENDORVERDICT_STRIPE_CANCEL_URL=https://vendorverdict.docoply.com/dashboard/proposals/YOUR_PROPOSAL_ID?stripe=cancelled
VENDORVERDICT_STRIPE_TIMEOUT_SECONDS=15
```

The dashboard can also generate default success and cancel URLs from the configured public URL when explicit Stripe URLs are not supplied.

## Workflow

1. Open a proposal.
2. Enter the checkout amount.
3. Click **Create Stripe Checkout link**.
4. VendorVerdict creates a Stripe Checkout session.
5. The returned checkout URL is saved as the payment link.
6. Send the payment request email or share the customer proposal page.
7. After payment, verify it in Stripe and click **Mark payment received**.

## Safety notes

- VendorVerdict does not store card details.
- The app stores only the checkout URL, session ID/reference, due date, and payment status.
- Payment is not automatically marked as paid without Stripe webhook reconciliation. Until webhooks are added, verify payment in Stripe before marking it received.
