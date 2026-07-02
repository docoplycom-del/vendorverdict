# VendorVerdict Payment Protocol + Monetization

VendorVerdict keeps the core SaaS vendor-risk review free and monetizes a paid **Premium Vendor Dossier**.

## Product model

### Free review

The free review includes:

- multi-vendor comparison or single-vendor audit,
- live official-source checks,
- risk scorecard,
- recommendation,
- due-diligence email.

### Paid upgrade

The paid **Premium Vendor Dossier** includes:

- executive procurement memo,
- approval conditions,
- vendor risk register,
- rollout checklist,
- expanded due-diligence questionnaire,
- evidence appendix.

Demo price:

```text
0.05 FET
```

Production pricing ideas:

```text
£3–£10 per premium vendor dossier
£29/month for SME review bundles
pay-per-call API for other agents
```

## Agent flow

```text
User asks for a normal free review
  ↓
VendorVerdict returns the free analysis
  ↓
User says: “Upgrade to Premium Vendor Dossier”
  ↓
VendorVerdict sends RequestPayment through Fetch.ai Payment Protocol
  ↓
Buyer commits payment
  ↓
VendorVerdict verifies payment or accepts demo-mode payment
  ↓
VendorVerdict sends CompletePayment
  ↓
VendorVerdict returns the premium report in ASI:One
```

## Files

```text
src/vendorverdict/payment/
  pricing.py          # PaidProduct and Premium Vendor Dossier price
  premium_report.py   # premium report rendering and upgrade detection
  fet_verifier.py     # demo or real FET verification
  payment_proto.py    # seller-side Payment Protocol implementation
```

## Environment variables

```env
VENDORVERDICT_PAYMENT_ENABLED=1
VENDORVERDICT_PREMIUM_PRICE_FET=0.05
FET_USE_TESTNET=true
VENDORVERDICT_PAYMENT_DEMO_MODE=1
```

`VENDORVERDICT_PAYMENT_DEMO_MODE=1` is useful for hackathon judging because it lets the Payment Protocol flow be demonstrated without requiring real funds. Set it to `0` to use real FET transaction verification through `cosmpy`.

## Local demo

```bash
vendorverdict --premium-demo --no-live-evidence
```

## ASI:One demo prompt

First run a free review:

```text
@vendorverdict Compare Notion, Airtable, and Coda for storing client project data for a 10-person consulting startup in the UK. Rank them by privacy, security, pricing risk, lock-in, and SME suitability. Give me the safest recommendation and draft an email I can send to the chosen vendor.
```

Then request the paid upgrade:

```text
Upgrade this to Premium Vendor Dossier.
```

VendorVerdict should send a Payment Protocol request and, once the payment is committed and verified, return the premium report.
