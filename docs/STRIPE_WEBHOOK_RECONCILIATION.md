# Stripe webhook reconciliation

This step adds optional Stripe webhook reconciliation for proposal payments.

## What it does

When Stripe Checkout is configured, VendorVerdict can now receive Stripe webhook events and automatically update proposal payment status.

Supported events:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `payment_intent.succeeded`
- `checkout.session.expired`
- `payment_intent.payment_failed`

Successful payment events mark the matching proposal as `paid` and store the Stripe event in the proposal payment-event log.

## Public webhook endpoint

```text
POST /webhooks/stripe
```

This endpoint is public so Stripe can call it, but it verifies the `Stripe-Signature` header before processing the event.

## Environment variables

Add these only when you are ready to use Stripe webhooks:

```env
VENDORVERDICT_STRIPE_WEBHOOK_ENABLED=1
VENDORVERDICT_STRIPE_WEBHOOK_SECRET=whsec_your_webhook_signing_secret
VENDORVERDICT_STRIPE_WEBHOOK_TOLERANCE_SECONDS=300
```

Keep the webhook signing secret in `/etc/vendorverdict/vendorverdict.env`. Do not put it in the dashboard settings page or commit it to Git.

## Stripe setup

In Stripe, create a webhook endpoint pointing to:

```text
https://vendorverdict.docoply.com/webhooks/stripe
```

Send at least these events:

```text
checkout.session.completed
checkout.session.async_payment_succeeded
payment_intent.succeeded
checkout.session.expired
payment_intent.payment_failed
```

## How proposals are matched

VendorVerdict matches Stripe events to proposals using either:

- `metadata.proposal_id`
- `client_reference_id`

The Stripe Checkout creation workflow already sends both values.

## Dashboard impact

On each proposal page, the payment section now shows whether Stripe webhook reconciliation is configured. It also shows recent Stripe payment events recorded against that proposal.

## Manual fallback

If Stripe webhooks are not configured, the existing manual flow still works:

1. Create a Stripe Checkout link or paste a payment link.
2. Send the payment request email.
3. Confirm payment in Stripe.
4. Click **Mark payment received**.
