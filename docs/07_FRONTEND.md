# 07 — Frontend Architecture (RankSpy)

> Scope: `frontend/` — the Next.js 14 web client for RankSpy (AppStore Spy).
> Documented strictly from the code on the `audit-fixes` branch. Nothing here is aspirational —
> every claim maps to a file under `frontend/src/`.

Legend: ✅ implemented / country-aware · 🟡 partial or single-storefront · 🔴 missing / not country-aware / known defect.

---

## 1. Stack & Architecture

| Concern | Choice | Evidence |
|---|---|---|
| Framework | **Next.js 14.1.0** (App Router) | `frontend/package.json`, `frontend/src/app/` |
| Language | TypeScript 5.3 (`strict: true`), path alias `@/* → src/*` | `frontend/tsconfig.json` |
| UI runtime | React 18.2 | `package.json` |
| Styling | Tailwind CSS 3.4 + `clsx` + `tailwind-merge` (via `cn()` in `lib/utils.ts`) | `package.json`, `src/lib/utils.ts` |
| Charts | Recharts 2.10 | `components/Charts.tsx`, `components/RankHistoryChart.tsx` |
| Icons | `lucide-react` 0.312 | used throughout |
| Theming | `next-themes` (class strategy, default light, system-enabled) | `components/Providers.tsx` |
| Payments | `@stripe/stripe-js` + `@stripe/react-stripe-js` | checkout / billing portal in `lib/api.ts` |
| Data layer | **None** — no SWR / React Query / RSC data fetching | see §5 |

### Rendering model
- **Every page is a Client Component.** All route files carry `'use client'`; several flag `export const dynamic = 'force-dynamic'` (`rankings`, `alerts`, `settings`, `apps/[id]`, root `page.tsx`). There is essentially **no server-side data fetching** — the App Router is used mainly for file-based routing and layouts.
- **API proxy.** `frontend/next.config.js` rewrites `/api/:path*` → `${BACKEND_URL}/api/:path*`. In the browser the client calls the relative `/api/v1` origin, so there are **no CORS issues** and the JWT never crosses to a third origin. `lib/api.ts::_resolveApiBase()` resolves an absolute base for SSR/Node (`BACKEND_URL` / `NEXT_PUBLIC_API_URL`) and a relative `/api/v1` for the browser.
- **Security headers.** `next.config.js` also sets a strict CSP, HSTS, `X-Frame-Options: DENY`, `nosniff`, referrer-policy and a Stripe-scoped `script-src`/`frame-src`.

### Composition / providers
`app/layout.tsx` → `components/Providers.tsx` wraps the tree in:
```
<ThemeProvider> → <AuthProvider> → <UpgradeModalProvider> → {children}
```
Authenticated pages render inside `<AppShell>` (`components/AppShell.tsx`), which composes `<AuthGuard>` + `<Sidebar>`/`<MobileSidebar>` + `<Header>`.

### Auth model
- `lib/auth.tsx` (`AuthProvider` / `useAuth`) is the single source of truth. **JWT is stored in `localStorage` under `auth_token`.**
- On mount it restores the session by calling `authMe(token)`; a network blip does **not** log the user out — the token is only discarded on an explicit `401`/`403`.
- Exposes `isAuthenticated`, `isPendingPayment` (`subscription.status === 'pending_payment'`), and `isTrialExpired`.
- `components/AuthGuard.tsx` gates every `AppShell` page: spinner while loading → redirect to `/login` if anonymous → `SubscribeWall` (inline Stripe plan cards) if trial expired → force-redirect superadmins to `/admin`.
- **Centralized 401 handling (added on `audit-fixes`):** `lib/api.ts::_handleUnauthorized()` clears the token and hard-redirects to `/login` from inside the fetch wrappers (see §4).

---

## 2. Page Inventory

The router contains **46 `page.tsx` files across ~33 user-facing route groups** (product routes + auth/billing + legal/marketing + the admin console). Client logic for the heavier screens lives in co-located `*Client.tsx` files rendered by a thin `page.tsx`.

### 2a. Core product routes

| Route | File | Purpose | Key data fetched | Country-aware |
|---|---|---|---|---|
| `/` | `app/page.tsx` + `DashboardClient.tsx` | Auth-gated router: landing (anon) vs Dashboard (auth); redirects `pending_payment` → `/payment` | `getDashboardStats`, `getTrendingApps`, `getOpportunityOfDay`, `getBlowingUpApps`, `getTrendingKeywords`, `getIdeas`, `getDashboardKeywordHighlights` | 🔴 (dashboard is US-implicit) |
| `/rankings` | `app/rankings/page.tsx` | **Flagship per-country/per-genre Top Charts leaderboard** + rank-history explorer + all-tracked-apps table | `getCountryCharts(country, chartType, genre, 100)`, `getChartGenres`, `getApps`, `getRankHistory` | ✅ `CountrySelect` + genre + Free/Grossing toggle, race-guarded |
| `/trending` | `app/trending/TrendingClient.tsx` | Highest rank-velocity / growth apps per storefront | `getTrendingApps(20, country)` | ✅ `CountrySelect`, race-guarded |
| `/blowing-up` | `app/blowing-up/BlowingUpClient.tsx` | Momentum leaderboard (score breakdown, badges, timeframe/chart/confidence filters, pagination) | `getBlowingUpApps(filters)` incl. `country` | ✅ `CountrySelect` in filters |
| `/apps` | `app/apps/AppsClient.tsx` | Filterable/sortable app catalogue with URL-synced filters + inline App Store search | `getFilteredApps`, `getCategories` (inline `API_BASE` for search) | 🔴 not country-aware; **no request-race guard** |
| `/apps/[id]` | `app/apps/[id]/page.tsx` (**3,597 lines**) | App detail with 9 tabs: Overview, Versions, **Reviews (per-storefront)**, Rankings, Analytics, Market Weakness, Feature Gaps, Keywords, Autopsy | `getAppDetail`, `getAppReviews`, `getReviewCountries`, `getRankHistory`, `getMarketWeakness`, `getFeatureGaps`/`analyzeFeatureGaps`, `getKeywordIntelligence`, `getAppAutopsy`, `getDownloadEstimate`, `getASOScore`, `getDeveloperApps`, favorites/my-apps toggles, … | ✅ Reviews tab has per-storefront selector (`getReviewCountries` + race-guarded `changeCountry`); other tabs 🔴 |
| `/keywords` | `app/keywords/KeywordsClient.tsx` | Keyword intelligence table (volume, difficulty, trend, Google-Trends spark) + detail/trend drill-in | `getKeywordsEnhanced`, `getKeywordDetail`, `getKeywordTrend`, `triggerKeywordPipeline` | 🔴 not country-aware |
| `/competitors` | `app/competitors/CompetitorsClient.tsx` | Multi-app comparison, shared rank-history, keyword-gap report | `getFilteredApps`, `getAppDetail`, `compareCompetitors`, `getCompetitorRankHistory`, `getKeywordGaps` | 🔴 not country-aware |
| `/opportunities` | `app/opportunities/OpportunitiesClient.tsx` | Opportunities hub with tabs (opportunity-of-day, weekly, keyword ops, **ideas**, **niches**) — absorbs old `/ideas` & `/niche-radar` | `getOpportunityOfDay`, `getWeeklyOpportunities`, `getKeywordOpportunities`, `getIdeas`, `generateIdeas`, `getNicheRadar` | 🔴 not country-aware |
| `/search` | `app/search/RankSpySearchClient.tsx` | Unified App Store search engine (RankSpy Search), paginated | `rankspySearch` | 🟡 has a `Globe`/country param in the search call, not the shared `CountrySelect` |
| `/latest-apps` | `app/latest-apps/LatestAppsClient.tsx` | New releases + fresh risers | `getLatestApps`, `getFreshRisers` | 🔴 |
| `/favorites` | `app/favorites/FavoritesClient.tsx` | Saved apps list with client-side search | `getFavorites` | 🔴 |
| `/my-apps` | `app/my-apps/MyAppsClient.tsx` | User's own tracked apps + ASO score rings | `getMyApps` (+ `getASOScore`) | 🔴 |
| `/my-apps/[id]` | `app/my-apps/[id]/MyAppDetailClient.tsx` | Owned-app deep view (race-guarded fetches) | app detail + keyword/ASO endpoints | 🔴 |
| `/ads` | `app/ads/AdsClient.tsx` | Ad-intelligence list (creatives/campaigns) with filters | `getAdIntelligenceList` | 🔴 |
| `/campaigns` | `app/campaigns/CampaignsClient.tsx` | Campaign-tracking list | `getCampaignTrackingList` | 🔴 |
| `/alerts` | `app/alerts/page.tsx` | CRUD alert rules + alert-event feed with read/unread | `getAlerts`, `createAlert`, `updateAlert`, `deleteAlert`, `getAlertEvents`, `markAlertEventRead`, `markAllAlertEventsRead` | 🔴 |
| `/settings` | `app/settings/page.tsx` | Profile, password, usage meter, Stripe billing portal/checkout | `getUsageSummary`, `updateProfile`, `changePassword`, `createStripeCheckout`, `createBillingPortal` | n/a |

**Redirect-only routes** (kept for old bookmarks): `/discover` → `/apps`, `/ideas` → `/opportunities?tab=ideas`, `/niche-radar` → `/opportunities?tab=niches`.
Note: `app/ideas/IdeasClient.tsx` still exists but is **dead code** — the only route into it (`app/ideas/page.tsx`) is a `redirect()`, and nothing imports the client. See §5.

### 2b. Auth & billing routes

| Route | File | Purpose |
|---|---|---|
| `/login` | `app/login/page.tsx` | Email/password sign-in via `useAuth().login` |
| `/signup` | `app/signup/page.tsx` | Registration (plan preselect, may return checkout URL / verify-email) |
| `/verify-email` | `app/verify-email/page.tsx` | Email verification (`authVerifyEmail`, `authResendVerification`) |
| `/payment` | `app/payment/page.tsx` | Stripe checkout entry for `pending_payment` workspaces |
| `/payment/success` | `app/payment/success/page.tsx` | Post-checkout confirmation |
| `/impersonate` | `app/impersonate/page.tsx` | Consumes an admin impersonation token to assume a user session |

### 2c. Admin console (`/admin/*`)

Rendered inside `components/AdminShell.tsx`; superadmins are force-redirected here by `AuthGuard`.

| Route | File | Purpose |
|---|---|---|
| `/admin` | `app/admin/page.tsx` + `AdminClient.tsx` | Ops dashboard (`adminGetDashboard`) |
| `/admin/users`, `/admin/users/[id]` | users list + detail | `adminGetUsers`, `adminGetUserDetail`, update/delete/reset-password/impersonate |
| `/admin/workspaces` | workspaces + subscription editing | `adminGetWorkspaces`, `adminUpdateSubscription` |
| `/admin/trials` | trial management / extend | `adminGetTrials`, `adminExtendTrial` |
| `/admin/jobs` | scheduler jobs + trigger | `adminGetJobs`, `adminTriggerJob`, `adminGetJobMetrics` |
| `/admin/system` | system health / backfill | `adminGetSystemHealth`, `adminBulkBackfill` |
| `/admin/activity` | global activity feed | `adminGetActivity` |
| `/admin/announcements` | announcement CRUD | `adminGet/Create/Update/DeleteAnnouncement` |
| `/admin/settings` | admin settings | — |

### 2d. Marketing & legal (static)

`/landing` (hero/marketing), `/about`, `/contact`, `/support`, `/data-sources`, `/privacy`, `/terms`, `/cookies`, `/refund`. Plus SEO endpoints `app/robots.ts` and `app/sitemap.ts`.

---

## 3. Component Inventory (`frontend/src/components/`, 21 modules)

| Component | Purpose |
|---|---|
| **`CountrySelect`** ⭐ | **Shared storefront selector added on `audit-fixes`.** Loads `getCountries()` once, falls back to a single "United States" option while loading/on failure. Drives the country-aware views: **rankings, trending, blowing-up** (and mirrored, but not reused, by the app-detail Reviews tab). |
| `AppShell` | Authenticated layout = `AuthGuard` + `Sidebar`/`MobileSidebar` + `Header` + `<main>`. |
| `AuthGuard` | Route gate: loading spinner → `/login` redirect → trial-expired `SubscribeWall` → superadmin → `/admin`. |
| `AdminShell` | Layout wrapper for the admin console. |
| `Sidebar` / `MobileSidebar` | Desktop + slide-over nav, grouped DISCOVER / GROWTH INTELLIGENCE / INTELLIGENCE / TOOLS. |
| `Header` | Top bar (mobile menu button, search, theme toggle, account). |
| `Navbar` | Public/marketing navbar. |
| `Providers` | Composes ThemeProvider + AuthProvider + UpgradeModalProvider. |
| `ThemeToggle` | Light/dark toggle (mount-guarded to avoid hydration mismatch). |
| `ErrorBoundary` | Class-based boundary with retry; wraps `trending` & `blowing-up`. |
| `StatsCard` | KPI/metric tile. |
| `UsageMeter` | Plan-usage bars (used in settings). |
| `UpgradeModal` (`UpgradeModalProvider` / `useUpgradeModal`) | Listens for `rankspy:upgrade` window events (see §4) and shows the plan-limit / premium-required modal. |
| `Charts` (`SimpleChart`, `RankHistoryChart` re-export) | Recharts wrappers. |
| `RankHistoryChart` | Rank-over-time line chart (inverted axis). |
| `SearchDropdown` | Global type-ahead app search. |
| `SearchResultRow` | Row renderer for search results. |
| `SearchSection` | Section wrapper for grouped search results. |
| `TrendingAppCard` | Card for a trending app (used on `/trending` and dashboard). |
| `OpportunityOfDayCard` | Opportunity-of-the-day feature card. |
| `WeeklyOpportunitiesCard` | Weekly opportunities list card. |

All exports are barrelled through `components/index.ts` (except `AuthGuard`, `ErrorBoundary`, `UsageMeter`, `Navbar`-adjacent cards, which are imported directly).

---

## 4. API Client (`frontend/src/lib/api.ts`, ~3,045 lines)

A single hand-rolled module: type definitions + **~126 exported functions** wrapping **~82 raw `fetch` calls**. No generated client, no schema sharing with the backend.

### Base resolution
`_resolveApiBase()` picks the API origin: server → `BACKEND_URL/api/v1`; browser → `NEXT_PUBLIC_API_URL` or the relative `/api/v1` (proxied by Next). `_authHeaders()` reads the `auth_token` from `localStorage` and returns a `Bearer` header for authenticated calls.

### Two core wrappers
- **`fetchApi<T>(endpoint)`** — GET helper. Adds a **10 s `AbortController` timeout** and `_authHeaders()`. On `401` → `_handleUnauthorized()` (clear token + redirect to `/login`) then throw; on `402/403` → `_handlePlanError()` then throw; other non-2xx → throw `API error: {status}`.
- **`fetchApiAuth<T>(endpoint, token, init?)`** — token-bearing helper for mutations. Same 401 handling; on `402` throws `PlanLimitExceededError`, on `403 PREMIUM_REQUIRED` throws `PremiumRequiredError`, otherwise surfaces the backend `detail` message.

> Not all functions go through the wrappers — many endpoints (e.g. `getFreshRisers`, several list/estimate calls) issue a raw `fetch(${API_BASE}…, { headers: _authHeaders() })` and hand-roll `if (!res.ok) throw`. So 401/plan handling is **consistent only for calls that use the wrappers**, not universally.

### Plan-limit event bus
`emitUpgradeEvent()` dispatches a `rankspy:upgrade` `CustomEvent`; `_handlePlanError()` maps backend codes (`PLAN_LIMIT_EXCEEDED` / `SUBSCRIPTION_REQUIRED` / `PREMIUM_REQUIRED`) into that event. `UpgradeModalProvider` listens and renders the modal — this lets non-React code trigger the paywall UI. Typed errors `PlanLimitExceededError` / `PremiumRequiredError` and helper `parsePlanLimitError()` are exported for callers that need to branch.

### Exported functions grouped by domain
- **Dashboard / discovery:** `getDashboardStats`, `getTrendingApps`, `getBlowingUpApps`, `getFreshRisers`, `getLatestApps`, `getFilteredApps`, `getNicheRadar`, `getDashboardKeywordHighlights`.
- **Storefronts / charts:** `getCountries`, `getCountryCharts`, `getChartGenres`, `getRankings`, `getRankHistory`.
- **App detail:** `getApp`, `getAppDetail`, `refreshApp`, `getAppVersions`, `getAppAnalytics`, `getAppMetrics`, `getDeveloperApps`, `getMarketWeakness`, `getFeatureGaps`/`analyzeFeatureGaps`, `getAppAutopsy`, `getReviewIntelligence`.
- **Reviews:** `getAppReviews`, `getReviewCountries`.
- **Keywords / ASO:** `getKeywords`, `getKeywordsEnhanced`, `getKeywordDetail`, `getKeywordTrend`, `getTrendingKeywords`, `getKeywordIntelligence`, `getKeywordSuggestions`, `getExtractedKeywords`, `getDiscoveredKeywords`, `getKeywordOpportunitiesForApp`, `getKeywordHistory`, `getAppKeywords`, `getASOScore`, `triggerKeyword*` / `triggerPhase1Discovery` / `runKeywordSearch`.
- **Estimates:** `getInstallEstimate`, `getRevenueEstimate`, `getDownloadEstimate`.
- **Opportunities / ideas:** `getOpportunityOfDay`, `getWeeklyOpportunities`, `getKeywordOpportunities`, `getIdeas`, `generateIdeas`.
- **Search / import:** `rankspySearch`, `searchAppsByKeyword`, `searchAppsImport`, `lookupApp`, `getCategories`.
- **Competitors:** `compareCompetitors`, `getCompetitorRankHistory`, `getKeywordGaps`.
- **Ads / campaigns:** `getAppAdIntelligence`, `scanAppAds`, `getAdIntelligenceList`, `getAppGrowthEvents`, `getCampaignTrackingList`.
- **Favorites / my-apps:** `getFavorites`, `getFavoriteIds`, `addFavorite`, `removeFavorite`, `getMyApps`, `getMyAppIds`, `addMyApp`, `removeMyApp`, `refreshMyApp`.
- **Alerts:** `getAlerts`, `createAlert`, `updateAlert`, `deleteAlert`, `getAlertEvents`, `getAlertUnreadCount`, `markAlertEventRead`, `markAllAlertEventsRead`.
- **Auth / account / billing:** `authRegister`, `authLogin`, `authMe`, `authVerifyEmail`, `authResendVerification`, `authCreateCheckoutAfterVerify`, `createStripeCheckout`, `createBillingPortal`, `getUsageSummary`, `updateProfile`, `changePassword`, `getActiveAnnouncements`.
- **Admin (~30 fns):** `adminGetDashboard`, `adminGetUsers`/`adminGetUserDetail`/`adminCreate/Update/DeleteUser`, `adminGetWorkspaces`, `adminUpdateSubscription`, `adminGetJobs`/`adminTriggerJob`/`adminGetJobMetrics`, `adminGetSystemHealth`, `adminBulkBackfill`, `adminResetPassword`, `adminImpersonateUser`, `adminBulkAction`, `adminExportUsersCSV`/`adminExportWorkspacesCSV`, `adminGetTrials`/`adminExtendTrial`, `adminGetActivity`/`adminGetUserActivity`, `adminRescrapeApp`, `adminGet/Create/Update/DeleteAnnouncement`.

Pure formatting helpers live outside the client in `lib/estimate-format.ts` (`fmtNum`, `fmtRev`, `fmtRange`, `fmtRevRange`, `confidenceLabel`, `getDailyDownloads`, `CONFIDENCE_BADGE`) with a test file `estimate-format.test.mjs`.

---

## 5. Known Frontend Issues (from the code)

Because there is **no SWR / React-Query / RSC caching layer**, every page hand-fetches in `useEffect` and owns its own loading/error/staleness state. That single decision is the root of most items below.

| # | Issue | Severity | Detail / evidence |
|---|---|---|---|
| 1 | **Fetch races on filter/param change** | 🔴 High | Country/genre/filter changes fire overlapping requests. **Now race-guarded** via a monotonic `reqRef` counter: `rankings`, `trending`, `blowing-up`, `apps/[id]` (incl. Reviews `changeCountry`), `my-apps/[id]`. **Still unguarded:** `apps/AppsClient.tsx` (`fetchApps` has no request id — a slow first response can overwrite a newer filter), and most other list pages that refetch on state change. |
| 2 | **No shared data cache / dedup** | 🟡 Medium | Same endpoints (e.g. `getTrendingApps`, `getBlowingUpApps`, `getCountries`) are refetched independently by dashboard, list pages, and `CountrySelect`. No caching, no revalidation, no background refresh, no cross-page dedup. |
| 3 | **Errors rendered as empty/degraded states** | 🟡 Medium | Many `.catch(() => setX([]))` blocks (e.g. `FavoritesClient`, `CountrySelect`, several app-detail sub-fetches) swallow failures and render "no data" — indistinguishable from a genuinely empty result. Only `trending`/`blowing-up` (via `ErrorBoundary`) and the race-guarded pages show an explicit error state. |
| 4 | **Duplicated UI logic** | 🟡 Medium | Multiple independent score-ring/donut/`<circle strokeDasharray>` implementations across `apps/[id]`, `my-apps`, `my-apps/[id]`, `competitors`, `keywords`, `opportunities`, `ideas`, plus `Charts`/`RankHistoryChart`. Local `ScorePill`/`ScoreBar`/`AppIcon` helpers are re-declared per page. Number formatting is duplicated too (a local `formatNum` in `search` and `apps` vs the shared `fmtNum` in `lib/estimate-format.ts`). |
| 5 | **Dead code** | 🟡 Medium | `app/ideas/IdeasClient.tsx` is orphaned — its route (`app/ideas/page.tsx`) is a `redirect()` to `/opportunities?tab=ideas` and nothing imports the client. Same pattern risk for `/discover` and `/niche-radar` redirect stubs. |
| 6 | **`<img>` instead of `next/image`** | 🟡 Medium | ~19 files use raw `<img>` for app icons/screenshots; **zero** use `next/image`. No automatic resizing, lazy-loading guarantees, or CLS protection (some call sites add `loading="lazy"` / `onError` by hand). |
| 7 | **Monolithic app-detail with no code-splitting** | 🔴 High | `app/apps/[id]/page.tsx` is **3,597 lines** with all 9 tab components defined inline. No `dynamic()`/lazy tab loading — the entire bundle (autopsy, keyword discovery, feature gaps, analytics) ships even when the user only views Overview. |
| 8 | **Inconsistent number/date formatting** | 🟢 Low | A shared, tested formatter set exists (`lib/estimate-format.ts`) but is applied unevenly; several pages inline their own compact-number logic and `toLocaleString()`/`toFixed()` calls, so thresholds and separators diverge across screens. |
| 9 | **Token in `localStorage`** | 🟡 Medium | JWT lives in `localStorage` (`auth_token`), readable by any injected script — mitigated by the strict CSP in `next.config.js` but not equivalent to an `HttpOnly` cookie. |
| 10 | **Country-awareness is partial** | 🟡 Medium | The shared `CountrySelect` reaches only rankings/trending/blowing-up (+ a bespoke selector on app-detail Reviews). Dashboard, apps list, keywords, competitors, opportunities, favorites, my-apps, ads, campaigns remain **US-implicit** — storefront cannot be changed there. |

---

### Summary
The frontend is a cleanly-routed Next.js 14 App Router client, but it is a **thin, all-client, hand-fetched** SPA with no data-layer abstraction. The `audit-fixes` branch has meaningfully hardened the country-aware surfaces (shared `CountrySelect`, request-race guards on the flagship pages, centralized 401 + plan-limit handling). The remaining debt is concentrated in the un-guarded list pages, the 3.6k-line app-detail monolith, duplicated presentational logic, and inconsistent formatting/image handling.
