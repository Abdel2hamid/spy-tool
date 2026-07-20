# Airwallex Integration Plan (Phase 2b)

> Design for implementing `AirwallexBillingProvider` behind the existing
> `BillingProvider` interface. Grounded in Airwallex's live API docs (fetched
> 2026-07). Items marked **⚠️ confirm in sandbox** need verification once keys
> are available — do not treat them as final.
>
> Prereq already done (Phase 2a): the `BillingProvider` interface, the
> `provider` / `provider_customer_id` / `provider_subscription_id` columns, and
> the `get_billing_provider()` factory all exist. Adding Airwallex is: implement
> the class → register it → set `PAYMENT_PROVIDER=airwallex`.

---

## 1. What Airwallex gives us (verified from docs)

| Area | Detail |
|---|---|
| **Auth** | Bearer token. Authenticate with **Client ID + API key** to obtain an access token; send `Authorization: Bearer {token}`. Sandbox base URL: `https://api-demo.airwallex.com/api/v1` (prod: `https://api.airwallex.com/api/v1`). ⚠️ confirm token lifetime/refresh (commonly ~30 min). |
| **Customers** | `POST /billing_customers/create` |
| **Products / Prices** | `POST /billing/prices/create` (+ Products API) — price carries amount, currency, frequency |
| **Subscriptions** | `POST /subscriptions/create`, `POST /subscriptions/{id}/update`, `POST /subscriptions/{id}/cancel`, retrieve, list |
| **Subscription create fields** | `billing_customer_id`, `collection_method` (`AUTO_CHARGE` / `CHARGE_ON_CHECKOUT` / `OUT_OF_BAND`), `items.price_id`, `duration.period_unit` (`DAY/WEEK/MONTH/YEAR`), `linked_payment_account_id`, `legal_entity_id` |
| **Lifecycle / status** | `PENDING → IN_TRIAL → ACTIVE → (cancelled)`; free trial via `trial_ends_at`; upgrade/downgrade via update with proration `PRORATED/ALL/NONE` |
| **Checkout** | Hosted Payment Page (redirect), embedded Elements, API, mobile SDK. A **Hosted Billing Checkout** exists for the subscribe flow. ⚠️ confirm which we use (redirect HPP is the closest analog to today's Stripe Checkout). |
| **Webhooks** | Verify with `x-timestamp` + `x-signature` headers: `HMAC_SHA256(x-timestamp + raw_body, webhook_secret)` compared to `x-signature`, then check the timestamp is within tolerance. **Use the raw, unmodified body.** ⚠️ confirm the subscription event type names in sandbox. |

**Important:** Airwallex is a **payment gateway, not a Merchant of Record** — tax/VAT and dunning remain our responsibility (see launch plan).

---

## 2. Mapping onto the `BillingProvider` interface

| Interface method | Airwallex implementation |
|---|---|
| `is_configured()` | client_id + api_key + webhook_secret all present |
| `publishable_key()` | `''` for the hosted-redirect flow (no Stripe-style pk). For embedded Elements, return the client id. ⚠️ confirm |
| `create_checkout(...)` | get-or-create `billing_customer` → store `provider_customer_id`; create a subscription (or Hosted Billing Checkout) for the plan's `price_id`; return the **hosted checkout redirect URL**. ⚠️ confirm exact hosted-checkout creation + return-url params |
| `create_billing_portal(...)` | Airwallex has **no Stripe-style customer portal**. Plan: build a small in-app "manage plan" (cancel / change) that calls `/subscriptions/{id}/update|cancel`. ⚠️ confirm if any hosted management page exists |
| `cancel_subscription(provider_subscription_id)` | `POST /subscriptions/{id}/cancel` (used on account deletion → closes the "charged deleted user" gap) |
| `verify_webhook(payload, headers)` | HMAC-SHA256 over `x-timestamp + raw_body` with the webhook secret; constant-time compare to `x-signature`; reject if timestamp outside tolerance; return parsed event |
| `handle_webhook_event(event, db)` | map subscription events → local `plan_code` / `status`; look up the local `Subscription` by `provider_subscription_id` (fallback `provider_customer_id`) |

The webhook is the one place the interface signature already fits Airwallex better than Stripe: `verify_webhook(payload, headers)` receives the full headers, so `x-timestamp`/`x-signature` are available.

---

## 3. New components to build (Phase 2b)

```
backend/app/services/billing/
├── airwallex_client.py     # thin HTTP client: auth-token cache/refresh, POST helpers, base-url switch
└── airwallex_provider.py   # AirwallexBillingProvider(BillingProvider)
```
Plus:
- `billing/__init__.py`: register `"airwallex": AirwallexBillingProvider` in `_PROVIDERS`.
- `config.py`: `airwallex_client_id`, `airwallex_api_key`, `airwallex_webhook_secret`, `airwallex_base_url` (default prod), `airwallex_linked_payment_account_id`, `airwallex_legal_entity_id`, and a plan→price_id map (mirrors Stripe's `PLAN_TO_PRICE`).
- Data setup: create Products/Prices in Airwallex for each plan; record the `price_id`s.

**No changes** to `stripe_router` (now provider-agnostic), `plan_enforcement`, the models, or the frontend billing calls — they already go through the interface. The frontend "manage subscription" button may need to point at an in-app page instead of an external portal (small change) if Airwallex has no hosted portal.

---

## 4. Webhook verification (reference implementation)

```python
import hashlib, hmac, time

def verify(payload: bytes, headers, secret: str, tolerance_s: int = 300):
    ts  = headers.get("x-timestamp", "")
    sig = headers.get("x-signature", "")
    value_to_digest = ts.encode() + payload          # raw body, unmodified
    expected = hmac.new(secret.encode(), value_to_digest, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("bad signature")
    if abs(time.time() - int(ts)) > tolerance_s:      # ⚠️ confirm ts unit (s vs ms)
        raise ValueError("stale timestamp")
    return json.loads(payload)
```

---

## 5. Build & test sequence (when sandbox keys arrive)

```
1. Create sandbox account; get client_id / api_key / webhook secret.
2. Create Products + Prices for each plan; record price_ids.
3. Implement airwallex_client (token cache/refresh) + airwallex_provider.
4. Register provider; set PAYMENT_PROVIDER=airwallex + creds on staging.
5. Sandbox smoke:
     [ ] create-checkout → redirect → complete test payment
     [ ] webhook received → signature verifies → subscription flips to active
     [ ] plan gate enforces a limit (402)
     [ ] change plan (update) + proration
     [ ] cancel subscription (also verifies account-deletion path)
     [ ] failed-payment webhook → status past_due
6. Retire Stripe: remove stripe_provider from _PROVIDERS + stripe deps once live.
```

## 6. Open questions to resolve in sandbox (⚠️)
1. Exact hosted-checkout creation flow + success/cancel URL params (HPP vs Hosted Billing Checkout).
2. Subscription webhook **event type names** (created / activated / payment succeeded / failed / cancelled / trial-ending).
3. Access-token lifetime + refresh cadence.
4. `x-timestamp` unit (seconds vs milliseconds) for the tolerance check.
5. Whether a customer-facing hosted management page exists, or we build self-serve cancel/upgrade in-app.
6. `linked_payment_account_id` / `legal_entity_id` values for our account.

---

### Sources
- Subscriptions via API — https://www.airwallex.com/docs/billing/subscriptions/subscriptions-via-api
- Recurring / hosted payment page — https://www.airwallex.com/docs/online-payments__recurring-payments__hosted-payment-page-integration
- Webhooks (signature verification) — https://www.airwallex.com/docs/developer-tools/webhooks/listen-for-webhook-events
- API reference — https://www.airwallex.com/docs/api
