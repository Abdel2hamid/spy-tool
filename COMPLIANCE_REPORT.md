# RankSpy SaaS Compliance Report

**Generated:** June 19, 2026
**Platform:** rankspy.app
**Payment Processor:** Stripe

---

## Pages Audit

| Page | URL | Status |
|------|-----|--------|
| Landing / Homepage | `/landing` | Updated — Apple disclaimer + Stripe badge in footer |
| About | `/about` | **NEW** — Mission, features, transparency, no-affiliation disclaimer |
| Contact | `/contact` | **NEW** — Contact form, email addresses (support/billing/privacy), response times |
| Data Sources & Methodology | `/data-sources` | **NEW** — Data collection methods, accuracy disclaimer, Apple trademark notice |
| Support Center | `/support` | Existing — contact cards, FAQ |
| Privacy Policy | `/privacy` | **ENHANCED** — Added: Stripe/Resend named explicitly, GDPR/CCPA rights with exercise instructions, international data transfers, children's privacy |
| Terms of Service | `/terms` | **ENHANCED** — Added: Stripe payment terms, billing disputes/chargebacks, indemnification, severability, entire agreement, assignment, force majeure |
| Refund Policy | `/refund` | **ENHANCED** — Added: chargeback policy, currency/tax handling |
| Cookie Policy | `/cookies` | **ENHANCED** — Added: Stripe cookie disclosure, Do Not Track compliance |
| Login | `/login` | Existing |
| Signup | `/signup` | Existing |

## SEO & Technical

| Item | Status |
|------|--------|
| `sitemap.xml` | **NEW** — Auto-generated, includes all public pages |
| `robots.txt` | **NEW** — Allows all public pages, blocks /api/, /payment/, /admin/ |
| OG Meta Tags | **NEW** — Title, description, type, site_name for social sharing |
| Twitter Card Meta | **NEW** — summary_large_image card type |
| Page Titles | All pages have `<title>` via Next.js metadata |
| Meta Description | Set in root layout, inherited by all pages |

## Footer Links (Landing Page)

| Section | Links |
|---------|-------|
| Product | Features, Pricing, Compare, FAQ |
| Company | About, Contact Us, Support Center, Data Sources |
| Legal | Privacy Policy, Terms of Service, Cookie Policy, Refund Policy |
| Bottom | Copyright, support email, Stripe badge, Apple disclaimer |

## Stripe Compliance

| Requirement | Status |
|-------------|--------|
| Stripe named in Privacy Policy | Done |
| Stripe terms linked in ToS | Done |
| Stripe cookie disclosure | Done |
| Clear pricing on signup | Done (plan selector + trial notice) |
| Auto-renewal disclosure | Done (ToS Section 4) |
| Cancellation instructions | Done (ToS Section 11, Refund Section 7) |
| Refund policy accessible | Done (footer link + ToS reference) |
| Billing dispute process | Done (ToS Section 4, Refund Section 6) |
| Chargeback policy | Done (Refund Section 6) |
| Contact information visible | Done (footer, contact page, all policy pages) |

## Legal Compliance

| Requirement | Status |
|-------------|--------|
| GDPR rights (access, rectify, erase, port, restrict, object) | Done |
| GDPR exercise instructions | Done (email privacy@rankspy.app, 30-day response) |
| CCPA/CPRA rights | Done (know, delete, opt-out, non-discrimination) |
| Children's privacy (COPPA) | Done (age 16+, deletion on discovery) |
| International data transfers | Done (standard contractual clauses) |
| Do Not Track signal | Done (Cookie Policy Section 5) |
| Apple trademark disclaimer | Done (Data Sources page + footer) |
| Indemnification clause | Done (ToS Section 14) |
| Severability clause | Done (ToS Section 16) |
| Entire agreement clause | Done (ToS Section 16) |
| Force majeure clause | Done (ToS Section 16) |
| Assignment clause | Done (ToS Section 16) |

## Contact Channels

| Purpose | Address |
|---------|---------|
| General Support | support@rankspy.app |
| Billing | billing@rankspy.app |
| Privacy / Data Requests | privacy@rankspy.app |
| Contact Form | /contact page |

## Remaining Recommendations

1. **Cookie Consent Banner** — Consider adding a cookie consent banner for EU visitors (currently only essential + functional cookies are used, which may not strictly require consent, but a banner improves compliance posture)
2. **DPA (Data Processing Agreement)** — Consider creating a downloadable DPA for enterprise customers who require one
3. **Social Media Links** — Footer has Twitter/GitHub/LinkedIn placeholders pointing to `#` — update with real URLs when accounts are created
4. **Email Forwarding** — Ensure `billing@rankspy.app` and `privacy@rankspy.app` are configured as working email addresses (or aliases to support@rankspy.app)
