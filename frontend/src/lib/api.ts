// ---------------------------------------------------------------------------
// API base URL — resolved correctly for both server and client contexts.
//
// Priority order:
//   1. BACKEND_URL   (server-side Railway env var, origin only)
//   2. NEXT_PUBLIC_API_URL  (build-time var, can be origin or full path)
//   3. localhost:8000 fallback for local dev
//
// Relative paths (/api/v1) only work in browser context; Node fetch requires
// an absolute URL. Server components use BACKEND_URL to avoid this.
// ---------------------------------------------------------------------------
function _resolveApiBase(): string {
  const isServer = typeof window === 'undefined';

  if (isServer) {
    // Prefer the server-side Railway variable (full backend origin)
    const backendUrl = process.env.BACKEND_URL?.replace(/\/+$/, '');
    if (backendUrl) return `${backendUrl}/api/v1`;
  }

  // Normalise NEXT_PUBLIC_API_URL (may or may not include /api/v1)
  const raw = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/+$/, '');
  if (raw !== '') {
    return raw.endsWith('/api/v1') ? raw : `${raw}/api/v1`;
  }

  // No env vars set — relative for browser, localhost for server (dev)
  return isServer ? 'http://localhost:8000/api/v1' : '/api/v1';
}

export const API_BASE = _resolveApiBase();

/**
 * Read the JWT from localStorage and return an Authorization header.
 * Used by mutation endpoints (POST/PUT/DELETE) that require authentication.
 */
function _authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface DashboardStats {
  total_apps_tracked: number;
  total_keywords: number;
  trending_apps_count: number;
  opportunities_count: number;
}

export interface TrendingApp {
  id: number;
  app_id: string;
  name: string;
  developer: string | null;
  icon_url: string | null;
  current_rank: number | null;
  current_rating: number | null;
  current_reviews: number | null;
  trend_score: number;
  momentum_3d: number;
  momentum_7d: number;
  consistency_score: number;
  confidence_factor: number;
  absolute_rank_bonus: number;
  review_momentum: number;
  estimated_installs_min: number | null;
  estimated_installs_max: number | null;
  install_confidence: number | null;
  estimated_revenue_monthly_min: number | null;
  estimated_revenue_monthly_max: number | null;
}

export interface RelatedApp {
  id: number;
  name: string;
  rating: number | null;
  reviews: number | null;
  rank: number | null;
  icon_url: string | null;
  category: string | null;
}

export interface OpportunityOfDay {
  app_id: number;
  app_name: string;
  primary_keyword: string;
  competition_score: number;
  trend_score: number;
  success_probability: number;
  ai_integration_potential: number;
  rank_velocity: number;
  review_growth: number;
  rating_velocity: number;
  category_growth: number;
  category: string;
  recommendation: string;
  ai_summary?: string | null;
  related_apps?: RelatedApp[] | null;
}

export interface OpportunityOfDayWrapper {
  status: 'success' | 'insufficient_data' | 'empty';
  item: OpportunityOfDay | null;
  message: string | null;
  required_signals: string[] | null;
}

export interface WeeklyOpportunityItem {
  rank: number;
  week_start_date?: string | null;
  app_id: number;
  app_name: string;
  primary_keyword: string;
  competition_score: number;
  trend_score: number;
  success_probability: number;
  opportunity_score: number;
  attractiveness_score?: number | null;
  feasibility_score?: number | null;
  ai_integration_potential?: number | null;
  rank_velocity?: number | null;
  review_growth?: number | null;
  category: string;
  recommendation?: string | null;
  ai_summary?: string | null;
  related_apps?: RelatedApp[] | null;
}

export interface WeeklyOpportunitiesResponse {
  status: 'success' | 'insufficient_data' | 'empty';
  message?: string | null;
  week_start_date?: string | null;
  items: WeeklyOpportunityItem[];
}

export interface KeywordOpportunity {
  keyword: string;
  search_volume: number;
  difficulty: number;
  trend: number;
  opportunity_score: number;
  current_apps: number;
}

// ---------------------------------------------------------------------------
// Enhanced Keyword Intelligence types
// ---------------------------------------------------------------------------

export interface KeywordCompetitorItem {
  app_id: string;
  app_name: string;
  developer: string | null;
  icon_url: string | null;
  position: number;
  is_sponsored: boolean;
  reviews: number | null;
  rating: number | null;
  dominance_score: number;
}

export interface KeywordListItem {
  id: number;
  term: string;
  search_volume: number;
  difficulty: number;
  trend: number;
  opportunity_score: number;
  feasibility_score: number;
  classification: 'easy' | 'medium' | 'hard' | 'impossible';
  apps_count: number;
  ads_presence: number;
  feature_gap_count: number;
  last_updated: string | null;
  // External signal fields (from KeywordIntelligencePipeline)
  trend_score: number;        // Google Trends average interest (0-100)
  trend_growth: number;       // % growth last 4 weeks vs prior 4 weeks
  trend_velocity: number;     // momentum: last week vs recent average
  dominance_score: number;    // top-app market dominance (0-100)
  competition_score: number;  // DataForSEO competition index (0-100)
  cpc: number;                // cost per click (USD)
  last_enriched: string | null;
  // V2 scoring (multi-signal fusion)
  volume_score: number;         // multi-signal volume fusion (0-100)
  difficulty_v2: number;        // full top-10 difficulty (0-100)
  autocomplete_rank: number;    // Apple autocomplete position (1=top, 0=absent)
  incumbent_strength: number;   // top-10 review power (0-35)
  title_saturation: number;     // keyword in titles ratio (0-20)
  brand_dominance: number;      // big brand share (0-20)
  market_concentration: number; // HHI concentration (0-15)
  top_player: string | null;    // #1 app name
  brand_count: number;          // count of big-brand apps in top 10
}

export interface KeywordListResponse {
  keywords: KeywordListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface GoogleTrendWeekPoint {
  date: string;    // ISO date (Monday of week)
  interest: number; // 0-100 relative Google Trends interest
}

export interface KeywordDetail extends KeywordListItem {
  top_competitors: KeywordCompetitorItem[];
  related_keywords: string[];
  market_fragmentation: number;
  last_scanned: string | null;
  google_trend_points: GoogleTrendWeekPoint[];
}

export interface KeywordTrendPoint {
  date: string;
  apps_count: number;
  avg_position: number;
  sponsored_ratio: number;
}

export interface KeywordTrendResponse {
  term: string;
  trend_points: KeywordTrendPoint[];
}

export interface TrendingKeywordItem {
  id: number;
  term: string;
  trend_score: number;
  trend_growth: number;
  trend_velocity: number;
  opportunity_score: number;
  feasibility_score: number;
  search_volume: number;
  difficulty: number;
  dominance_score: number;
  apps_count: number;
  classification: 'easy' | 'medium' | 'hard' | 'impossible';
  // V2 scoring
  volume_score: number;
  difficulty_v2: number;
}

export interface TrendingKeywordsResponse {
  keywords: TrendingKeywordItem[];
  total: number;
}

export interface RankHistory {
  dates: string[];
  ranks: number[];
  chart_type: string | null;
  category_name: string | null;
  current_rank: number | null;
}

export interface App {
  app_id: string;
  name: string;
  subtitle: string | null;
  developer: string | null;
  developer_id: string | null;
  description: string | null;
  icon_url: string | null;
  screenshots: string[] | null;
  primary_category: string | null;
  secondary_category: string | null;
  price: number;
  currency: string;
  is_free: boolean;
  in_app_purchases: { name: string; price?: number }[] | null;
  current_version: string | null;
  minimum_ios_version: string | null;
  supported_languages: string[] | null;
  release_date: string | null;
  last_updated: string | null;
  content_rating: string | null;
  id: number;
  current_rating: number | null;
  current_reviews: number;
  current_rank: number | null;
  category_id: number | null;
  url: string | null;
  created_at: string;
  estimated_installs_min: number | null;
  estimated_installs_max: number | null;
  install_confidence: number | null;
  estimated_revenue_monthly_min: number | null;
  estimated_revenue_monthly_max: number | null;
}

// ---------------------------------------------------------------------------
// Keyword Search / Discover Apps
// ---------------------------------------------------------------------------

export interface KeywordSearchResultItem {
  id: number;
  app_id: string;
  name: string;
  developer: string | null;
  icon_url: string | null;
  current_rating: number | null;
  current_reviews: number | null;
  primary_category: string | null;
  price: number;
  is_free: boolean;
  url: string | null;
  is_new: boolean;
}

export interface KeywordSearchResponse {
  keyword: string;
  results: KeywordSearchResultItem[];
  total: number;
  new_apps_count: number;
}

export interface AppVersion {
  id: number;
  app_id: number;
  version: string;
  release_date: string | null;
  release_notes: string | null;
  is_latest: boolean;
  created_at: string;
}

export interface AppAnalytics {
  id: number;
  app_id: number;
  review_growth_30d: number;
  review_growth_90d: number;
  rating_change_30d: number;
  rating_change_90d: number;
  sentiment_score: number;
  sentiment_label: string;
  common_complaints: string[];
  common_features: string[];
  positive_themes: string[];
  bug_keywords: string[];
  churn_risk_score: number;
  update_cadence_score: number;
  quality_score: number;
  opportunity_score: number;
  computed_at: string;
}

export interface AppDetail extends App {
  versions: AppVersion[];
  analytics: AppAnalytics | null;
}

export interface Review {
  id: number;
  app_id: number;
  review_id: string | null;
  user_name: string | null;
  user_url: string | null;
  rating: number | null;
  title: string | null;
  content: string | null;
  date: string | null;
  app_version: string | null;
  storefront: string | null;
  is_updated: boolean;
  developer_reply_text: string | null;
  developer_reply_date: string | null;
  helpful_count: number;
  created_at: string;
}

export interface CountryStat {
  country: string;
  total_reviews: number;
  negative_reviews: number;
  average_rating: number;
  negative_ratio: number;
  computed_at: string | null;
}

export interface MarketWeakness {
  app_id: number;
  countries: CountryStat[];
  total_countries: number;
  has_data: boolean;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface Keyword {
  term: string;
  id: number;
  search_volume: number;
  difficulty: number;
  trend: number;
}

export interface Ranking {
  id: number;
  app_id: number;
  chart_type: string;
  rank: number;
  previous_rank: number | null;
  rank_velocity: number;
  recorded_at: string;
}

export interface Opportunity {
  app_id: number | null;
  opportunity_type: string;
  primary_keyword: string | null;
  competition_score: number;
  trend_score: number;
  success_probability: number;
  ai_integration_potential: number;
  recommendation: string | null;
  id: number;
  generated_at: string;
}

// ---------------------------------------------------------------------------
// Advanced filter types
// ---------------------------------------------------------------------------

export interface AppFilters {
  search?: string;
  category?: string;
  developer?: string;
  min_rating?: number | '';
  max_rating?: number | '';
  min_reviews?: number | '';
  max_reviews?: number | '';
  min_rank?: number | '';
  max_rank?: number | '';
  is_free?: boolean | '';
  has_in_app_purchases?: boolean | '';
  updated_after?: string;
  updated_before?: string;
  released_after?: string;
  released_before?: string;
  min_success_probability?: number | '';
  ai_only?: boolean;
  weak_market?: string;
  min_negative_ratio?: number | '';
  min_feature_gaps?: number | '';
  min_estimated_downloads?: number | '';
  max_estimated_downloads?: number | '';
  min_estimated_revenue?: number | '';
  max_estimated_revenue?: number | '';
  confidence_label?: 'low' | 'medium' | 'high' | '';
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  skip?: number;
  limit?: number;
}

export interface AppListItem {
  id: number;
  app_id: string;
  name: string;
  icon_url: string | null;
  developer: string | null;
  primary_category: string | null;
  current_rating: number | null;
  current_reviews: number;
  current_rank: number | null;
  is_free: boolean;
  price: number;
  estimated_installs_min: number | null;
  estimated_installs_max: number | null;
  estimated_revenue_monthly_min: number | null;
  install_confidence: number | null;
  release_date: string | null;
}

export interface AppListResponse {
  apps: AppListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface DeveloperAppsResponse {
  developer: string;
  developer_id: string | null;
  total_apps: number;
  apps: AppListItem[];
}

export async function getFilteredApps(filters: AppFilters = {}): Promise<AppListResponse> {
  const params = new URLSearchParams();
  const set = (k: string, v: unknown) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
  };

  set('search', filters.search);
  set('category', filters.category);
  set('developer', filters.developer);
  set('min_rating', filters.min_rating);
  set('max_rating', filters.max_rating);
  set('min_reviews', filters.min_reviews);
  set('max_reviews', filters.max_reviews);
  set('min_rank', filters.min_rank);
  set('max_rank', filters.max_rank);
  if (filters.is_free !== '' && filters.is_free !== undefined) set('is_free', filters.is_free);
  if (filters.has_in_app_purchases !== '' && filters.has_in_app_purchases !== undefined)
    set('has_in_app_purchases', filters.has_in_app_purchases);
  set('updated_after', filters.updated_after);
  set('updated_before', filters.updated_before);
  set('released_after', filters.released_after);
  set('released_before', filters.released_before);
  set('min_success_probability', filters.min_success_probability);
  if (filters.ai_only) params.set('ai_only', 'true');
  set('weak_market', filters.weak_market);
  set('min_negative_ratio', filters.min_negative_ratio);
  set('min_feature_gaps', filters.min_feature_gaps);
  set('min_estimated_downloads', filters.min_estimated_downloads);
  set('max_estimated_downloads', filters.max_estimated_downloads);
  set('min_estimated_revenue', filters.min_estimated_revenue);
  set('max_estimated_revenue', filters.max_estimated_revenue);
  set('confidence_label', filters.confidence_label);
  set('sort_by', filters.sort_by);
  set('sort_order', filters.sort_order || 'desc');
  params.set('skip', String(filters.skip ?? 0));
  params.set('limit', String(filters.limit ?? 50));

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}/apps?${params.toString()}`, {
      signal: controller.signal,
      headers: _authHeaders(),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

// ---------------------------------------------------------------------------
// Latest Apps (New Releases — last 30 days, release_date only)
// ---------------------------------------------------------------------------

export interface LatestAppsParams {
  mode?: 'new_releases' | 'released_today';
  limit?: number;
  offset?: number;
  category?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export async function getLatestApps(params: LatestAppsParams = {}): Promise<AppListResponse> {
  const p = new URLSearchParams();
  if (params.mode)       p.set('mode',       params.mode);
  if (params.limit)      p.set('limit',      String(params.limit));
  if (params.offset)     p.set('offset',     String(params.offset));
  if (params.category)   p.set('category',   params.category);
  if (params.sort_by)    p.set('sort_by',    params.sort_by);
  if (params.sort_order) p.set('sort_order', params.sort_order);
  const res = await fetch(`${API_BASE}/apps/latest?${p.toString()}`, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Fresh Risers
// ---------------------------------------------------------------------------

export interface FreshRiserItem {
  app_id: number;
  app_name: string;
  developer: string | null;
  release_date: string | null;
  current_rank: number | null;
  current_reviews: number;
  category: string | null;
  fresh_riser_score: number;
  freshness_score: number;
  review_traction_score: number;
  rank_quality_score: number;
  momentum_score: number;
  niche_viability_score: number;
  ranking_snapshots_count: number;
  age_days: number;
}

export interface FreshRisersResponse {
  status: string;
  message: string | null;
  required_signals: string[] | null;
  items: FreshRiserItem[];
}

export async function getFreshRisers(params: { limit?: number; mode?: string } = {}): Promise<FreshRisersResponse> {
  const p = new URLSearchParams();
  p.set('mode', params.mode ?? 'fresh_risers');
  if (params.limit) p.set('limit', String(params.limit));
  const res = await fetch(`${API_BASE}/fresh-risers?${p.toString()}`, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Upgrade event bus — allows non-React code to trigger the upgrade modal.
// The UpgradeModal component listens for these events.
// ---------------------------------------------------------------------------

export type UpgradeEventDetail =
  | { kind: 'premium_required'; plan: string; message: string; upgradeMessage: string }
  | { kind: 'limit_exceeded'; action: string; message: string; currentUsage: number; limit: number; plan: string; upgradeMessage: string };

export function emitUpgradeEvent(detail: UpgradeEventDetail): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('rankspy:upgrade', { detail }));
  }
}

/**
 * Check a fetch Response for 402/403 plan errors and emit upgrade event.
 * Returns true if a plan error was detected (caller should throw).
 */
async function _checkUpgrade(res: Response): Promise<boolean> {
  if (res.status !== 402 && res.status !== 403) return false;
  const body = await res.json().catch(() => ({}));
  _handlePlanError(res, body);
  return true;
}

function _handlePlanError(res: Response, body: Record<string, unknown>): void {
  const detail = body?.detail as Record<string, unknown> | undefined;
  if (!detail) return;

  if (res.status === 402 && detail.code === 'PLAN_LIMIT_EXCEEDED') {
    emitUpgradeEvent({
      kind: 'limit_exceeded',
      action: (detail.action as string) ?? '',
      message: (detail.message as string) ?? 'You have reached your plan limit.',
      currentUsage: (detail.current_usage as number) ?? 0,
      limit: (detail.limit as number) ?? 0,
      plan: (detail.plan as string) ?? 'free',
      upgradeMessage: (detail.upgrade_message as string) ?? 'Upgrade to Pro for higher limits.',
    });
  } else if (res.status === 403 && detail.code === 'SUBSCRIPTION_REQUIRED') {
    emitUpgradeEvent({
      kind: 'premium_required',
      plan: (detail.plan as string) ?? 'expired',
      message: (detail.message as string) ?? 'Your free trial has ended.',
      upgradeMessage: (detail.upgrade_message as string) ?? 'Subscribe to a paid plan to continue.',
    });
  } else if (res.status === 403 && detail.code === 'PREMIUM_REQUIRED') {
    emitUpgradeEvent({
      kind: 'premium_required',
      plan: (detail.plan as string) ?? 'free',
      message: (detail.message as string) ?? 'This feature requires a paid plan.',
      upgradeMessage: (detail.upgrade_message as string) ?? 'Upgrade to Pro to unlock this feature.',
    });
  }
}

// ---------------------------------------------------------------------------

/** Expired/invalid session: clear the token and send the user to /login. */
function _handleUnauthorized(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('auth_token');
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

async function fetchApi<T>(endpoint: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      signal: controller.signal,
      headers: _authHeaders(),
    });
    if (res.status === 401) {
      _handleUnauthorized();
      throw new Error('Session expired');
    }
    if (res.status === 402 || res.status === 403) {
      const body = await res.json().catch(() => ({}));
      _handlePlanError(res, body);
      throw new Error(body?.detail?.message ?? `API error: ${res.status}`);
    }
    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Like fetchApi but includes a Bearer token and throws PlanLimitExceeded on 402.
 * Accepts an optional RequestInit for mutations (POST/PATCH with body).
 */
async function fetchApiAuth<T>(
  endpoint: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const { headers: extraHeaders, ...restInit } = init ?? {};
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...restInit,
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(extraHeaders as Record<string, string> ?? {}),
      },
    });
    if (res.status === 401) {
      _handleUnauthorized();
      throw new Error('Session expired');
    }
    if (res.status === 402) {
      const body = await res.json().catch(() => ({}));
      _handlePlanError(res, body);
      const detail = body?.detail;
      if (detail?.code === 'PLAN_LIMIT_EXCEEDED') {
        throw new PlanLimitExceededError(detail as PlanLimitError);
      }
      throw new Error('Plan limit exceeded.');
    }
    if (res.status === 403) {
      const body = await res.json().catch(() => ({}));
      _handlePlanError(res, body);
      const detail = body?.detail;
      if (detail?.code === 'PREMIUM_REQUIRED') {
        throw new PremiumRequiredError(detail as PremiumRequiredDetail);
      }
      // Body already consumed — don't fall through to a second res.json()
      throw new Error(
        typeof detail === 'string' ? detail : detail?.message ?? 'Request failed (403)',
      );
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const msg =
        typeof body?.detail === 'string'
          ? body.detail
          : `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

export interface PremiumRequiredDetail {
  code: 'PREMIUM_REQUIRED';
  message: string;
  plan: string;
  upgrade_message: string;
}

export class PremiumRequiredError extends Error {
  readonly detail: PremiumRequiredDetail;
  constructor(detail: PremiumRequiredDetail) {
    super(detail.message);
    this.name = 'PremiumRequiredError';
    this.detail = detail;
  }
}

export class PlanLimitExceededError extends Error {
  readonly detail: PlanLimitError;
  constructor(detail: PlanLimitError) {
    super(detail.message);
    this.name = 'PlanLimitExceededError';
    this.detail = detail;
  }
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return fetchApi<DashboardStats>('/dashboard/stats');
}

export async function getTrendingApps(limit: number = 10): Promise<TrendingApp[]> {
  const response = await fetchApi<{ status: string; items: TrendingApp[] } | TrendingApp[]>(
    `/trending?limit=${limit}`
  );
  // The endpoint returns a wrapped { status, items } object. Guard against both
  // the new shape and any legacy path that might return a plain array.
  if (Array.isArray(response)) {
    return response;
  }
  return response?.items ?? [];
}

export async function getOpportunityOfDay(): Promise<OpportunityOfDayWrapper> {
  const response = await fetchApi<OpportunityOfDayWrapper | OpportunityOfDay>('/opportunity-of-day');
  // Backend returns { status, item, message, required_signals }.
  // Guard against a legacy bare-object response (no status field).
  if (response && 'status' in response) {
    return response as OpportunityOfDayWrapper;
  }
  // Bare object fallback: treat it as a successful item
  return {
    status: 'success',
    item: response as OpportunityOfDay,
    message: null,
    required_signals: null,
  };
}

export async function getWeeklyOpportunities(): Promise<WeeklyOpportunitiesResponse> {
  const response = await fetchApi<WeeklyOpportunitiesResponse>('/weekly-opportunities');
  if (response && 'status' in response) {
    return response;
  }
  return { status: 'insufficient_data', items: [] };
}

export async function getKeywordOpportunities(
  minDifficulty: number = 0,
  maxDifficulty: number = 60
): Promise<KeywordOpportunity[]> {
  return fetchApi<KeywordOpportunity[]>(
    `/keyword-opportunities?min_difficulty=${minDifficulty}&max_difficulty=${maxDifficulty}`
  );
}

// ---------------------------------------------------------------------------
// Dashboard keyword highlights — enriched keywords only, ordered by opportunity
// ---------------------------------------------------------------------------

export interface DashboardKeywordHighlight {
  term: string;
  search_volume: number;
  volume_score: number;
  difficulty_v2: number;
  trend_score: number;
  opportunity_score: number;
}

export async function getDashboardKeywordHighlights(
  limit: number = 10
): Promise<DashboardKeywordHighlight[]> {
  const res = await fetchApi<{ keywords: DashboardKeywordHighlight[]; total: number }>(
    `/dashboard/keyword-highlights?limit=${limit}`
  );
  return res?.keywords ?? [];
}

export async function getRankHistory(
  appId: number,
  days: number = 30
): Promise<RankHistory> {
  return fetchApi<RankHistory>(`/apps/${appId}/rank-history?days=${days}`);
}

export async function getApps(limit: number = 50): Promise<AppListItem[]> {
  const result = await fetchApi<AppListResponse>(`/apps?limit=${limit}`);
  return result.apps ?? [];
}

export async function getApp(appId: number): Promise<App> {
  return fetchApi<App>(`/apps/${appId}`);
}

export async function searchAppsByKeyword(
  keyword: string,
  limit: number = 50
): Promise<KeywordSearchResponse> {
  const params = new URLSearchParams({ keyword, limit: String(limit) });
  return fetchApi<KeywordSearchResponse>(`/search/apps?${params}`);
}

// ---------------------------------------------------------------------------
// On-Demand App Import
// ---------------------------------------------------------------------------

export interface AppImportSearchItem {
  id: number;
  app_id: string;
  name: string;
  developer: string | null;
  icon_url: string | null;
  current_rating: number | null;
  current_reviews: number | null;
  primary_category: string | null;
  price: number;
  is_free: boolean;
  url: string | null;
  is_new: boolean;
  source: string;
  match_score: number;
  match_type: string;
}

export interface AppImportSearchResponse {
  query: string;
  results: AppImportSearchItem[];
  total: number;
  from_cache: number;
  direct_lookup: boolean;          // True when query was a URL or trackId
  error_hint: string | null;       // Set when direct lookup was attempted but failed
}

export interface AppLookupResponse {
  id: number;
  app_id: string;
  name: string;
  subtitle: string | null;
  description: string | null;
  developer: string | null;
  developer_id: string | null;
  icon_url: string | null;
  screenshots: string[];
  primary_category: string | null;
  secondary_category: string | null;
  price: number;
  currency: string;
  is_free: boolean;
  in_app_purchases: { name: string; price: number }[] | null;
  current_version: string | null;
  minimum_ios_version: string | null;
  supported_languages: string[] | null;
  release_date: string | null;
  last_updated: string | null;
  content_rating: string | null;
  current_rating: number | null;
  current_reviews: number | null;
  url: string | null;
  is_new: boolean;
}

// ---------------------------------------------------------------------------
// RankSpy Search
// ---------------------------------------------------------------------------

export interface RankSpySearchItem {
  id: number;
  app_id: string;
  name: string;
  developer: string | null;
  icon_url: string | null;
  current_rating: number | null;
  current_reviews: number | null;
  primary_category: string | null;
  price: number;
  is_free: boolean;
  url: string | null;
  source: 'tracked' | 'discovered';
  match_score: number;
  match_type: string;
  enrichment_status: 'complete' | 'pending';
}

export interface RankSpySearchResponse {
  query: string;
  results: RankSpySearchItem[];
  total: number;
  tracked_count: number;
  discovered_count: number;
  has_appstore_results: boolean;
  error_hint: string | null;
}

export async function rankspySearch(
  query: string,
  limit: number = 50,
  offset: number = 0,
  forceLive: boolean = false,
  token?: string | null,
): Promise<RankSpySearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset),
  });
  if (forceLive) params.set('force_live', 'true');
  const endpoint = `/rankspy/search?${params}`;
  if (token) return fetchApiAuth<RankSpySearchResponse>(endpoint, token);
  return fetchApi<RankSpySearchResponse>(endpoint);
}

export async function searchAppsImport(
  query: string,
  limit: number = 10,
  token?: string | null,
): Promise<AppImportSearchResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const endpoint = `/apps/import?${params}`;
  if (token) return fetchApiAuth<AppImportSearchResponse>(endpoint, token);
  return fetchApi<AppImportSearchResponse>(endpoint);
}

export async function lookupApp(trackId: string, token?: string | null): Promise<AppLookupResponse> {
  const endpoint = `/apps/lookup/${trackId}`;
  if (token) return fetchApiAuth<AppLookupResponse>(endpoint, token);
  return fetchApi<AppLookupResponse>(endpoint);
}

export async function getCategories(): Promise<Category[]> {
  return fetchApi<Category[]>('/categories');
}

export async function getKeywords(limit: number = 50): Promise<Keyword[]> {
  return fetchApi<Keyword[]>(`/keywords?limit=${limit}`);
}

export async function getKeywordsEnhanced(params: {
  search?: string;
  classification?: string;
  sort_by?: string;
  sort_order?: string;
  skip?: number;
  limit?: number;
  min_volume?: number;
  max_difficulty?: number;
}): Promise<KeywordListResponse> {
  const q = new URLSearchParams();
  if (params.search) q.set('search', params.search);
  if (params.classification) q.set('classification', params.classification);
  if (params.sort_by) q.set('sort_by', params.sort_by);
  if (params.sort_order) q.set('sort_order', params.sort_order);
  if (params.skip != null) q.set('skip', String(params.skip));
  if (params.limit != null) q.set('limit', String(params.limit));
  if (params.min_volume != null) q.set('min_volume', String(params.min_volume));
  if (params.max_difficulty != null) q.set('max_difficulty', String(params.max_difficulty));
  const res = await fetch(`${API_BASE}/keywords/enhanced?${q}`, { headers: _authHeaders() });
  if (!res.ok) return { keywords: [], total: 0, skip: 0, limit: 50 };
  const data = await res.json();
  return {
    keywords: Array.isArray(data?.keywords) ? data.keywords : [],
    total: data?.total ?? 0,
    skip: data?.skip ?? 0,
    limit: data?.limit ?? 50,
  };
}

export async function getKeywordDetail(term: string): Promise<KeywordDetail | null> {
  const res = await fetch(`${API_BASE}/keywords/${encodeURIComponent(term)}/detail`, { headers: _authHeaders() });
  if (!res.ok) return null;
  return res.json();
}

export async function getKeywordTrend(term: string, days = 30): Promise<KeywordTrendResponse> {
  const res = await fetch(`${API_BASE}/keywords/${encodeURIComponent(term)}/trend?days=${days}`, { headers: _authHeaders() });
  if (!res.ok) return { term, trend_points: [] };
  const data = await res.json();
  return { term: data?.term ?? term, trend_points: Array.isArray(data?.trend_points) ? data.trend_points : [] };
}

export async function getTrendingKeywords(limit = 20): Promise<TrendingKeywordsResponse> {
  const res = await fetch(`${API_BASE}/keywords/trending?limit=${limit}`, { headers: _authHeaders() });
  if (!res.ok) return { keywords: [], total: 0 };
  const data = await res.json();
  return {
    keywords: Array.isArray(data?.keywords) ? data.keywords : [],
    total: data?.total ?? 0,
  };
}

export async function triggerKeywordPipeline(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/keywords/pipeline/run`, { method: 'POST', headers: _authHeaders() });
  if (!res.ok) return { status: 'error', message: 'Failed to trigger pipeline' };
  return res.json();
}

export async function getRankings(
  appId?: number,
  chartType?: string,
  limit: number = 100
): Promise<Ranking[]> {
  let url = `/rankings?limit=${limit}`;
  if (appId) url += `&app_id=${appId}`;
  if (chartType) url += `&chart_type=${chartType}`;
  return fetchApi<Ranking[]>(url);
}

export async function getOpportunities(
  minProbability?: number,
  limit: number = 50
): Promise<Opportunity[]> {
  let url = `/opportunities?limit=${limit}`;
  if (minProbability) url += `&min_probability=${minProbability}`;
  return fetchApi<Opportunity[]>(url);
}

export async function getAppDetail(appId: number): Promise<AppDetail> {
  return fetchApi<AppDetail>(`/apps/${appId}/detail`);
}

export async function refreshApp(appId: number): Promise<{ status: string; app_id: number; app_name?: string; message: string }> {
  const res = await fetch(`${API_BASE}/apps/${appId}/refresh`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to refresh app (${res.status})`);
  return res.json();
}

export async function getDeveloperApps(appId: number, limit: number = 20): Promise<DeveloperAppsResponse> {
  return fetchApi<DeveloperAppsResponse>(`/apps/${appId}/developer-apps?limit=${limit}`);
}

export async function getAppVersions(appId: number): Promise<AppVersion[]> {
  return fetchApi<AppVersion[]>(`/apps/${appId}/versions`);
}

// ASO Score

export interface ASOBreakdownItem {
  score: number;
  weight: number;
  label: string;
}

export interface ASOTip {
  category: string;
  text: string;
  impact: 'high' | 'medium' | 'low';
}

export interface ASOScoreResponse {
  overall_score: number;
  grade: string;
  breakdown: Record<string, ASOBreakdownItem>;
  tips: ASOTip[];
  app_id: number;
  app_name: string;
}

export async function getASOScore(appId: number): Promise<ASOScoreResponse> {
  return fetchApi<ASOScoreResponse>(`/apps/${appId}/aso-score`);
}

// Keyword Suggestions

export interface KeywordSuggestionItem {
  keyword: string;
  bucket: 'quick_win' | 'high_value_gap' | 'untapped' | 'long_tail' | 'defend';
  reason: string;
  app_rank: number | null;
  competitor_rank: number | null;
  keyword_gap: boolean;
  search_volume: number;
  difficulty: number;
  volume_score: number;
  difficulty_v2: number;
  trend_score: number;
  trend_direction: string;
  opportunity_score: number;
  source: string;
}

export interface KeywordSuggestionBucketCounts {
  quick_wins: number;
  high_value_gaps: number;
  untapped: number;
  long_tail: number;
  defend: number;
}

export interface KeywordSuggestionsResponse {
  app_id: number;
  app_name: string;
  suggestions: KeywordSuggestionItem[];
  total: number;
  bucket_counts: KeywordSuggestionBucketCounts;
}

export async function getKeywordSuggestions(appId: number): Promise<KeywordSuggestionsResponse> {
  return fetchApi<KeywordSuggestionsResponse>(`/apps/${appId}/keyword-suggestions`);
}

export async function getAppReviews(
  appId: number,
  rating?: number,
  limit: number = 50
): Promise<Review[]> {
  let url = `/apps/${appId}/reviews?limit=${limit}`;
  if (rating) url += `&rating=${rating}`;
  return fetchApi<Review[]>(url);
}

export async function getAppAnalytics(appId: number): Promise<AppAnalytics> {
  return fetchApi<AppAnalytics>(`/apps/${appId}/analytics`);
}

export async function getMarketWeakness(appId: number): Promise<MarketWeakness> {
  return fetchApi<MarketWeakness>(`/apps/${appId}/market-weakness`);
}

// ---------------------------------------------------------------------------
// Feature Gaps
// ---------------------------------------------------------------------------

export interface FeatureGapItem {
  feature: string;
  mentions: number;
  detected_at: string | null;
}

export interface FeatureGapResponse {
  app_id: number;
  feature_gaps: FeatureGapItem[];
  total_features: number;
  total_mentions: number;
  has_data: boolean;
}

export async function getFeatureGaps(appId: number): Promise<FeatureGapResponse> {
  return fetchApi<FeatureGapResponse>(`/apps/${appId}/feature-gaps`);
}

export async function analyzeFeatureGaps(appId: number): Promise<FeatureGapResponse> {
  const res = await fetch(`${API_BASE}/apps/${appId}/feature-gaps/analyze`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// App Ideas
// ---------------------------------------------------------------------------

export interface AppIdea {
  id: number;
  idea_title: string;
  idea_description: string | null;
  opportunity_score: number;
  pattern_type: 'feature_gap' | 'weak_market' | 'keyword_gap';
  related_app_ids: number[];
  reasoning: string[];
  signals: Record<string, unknown>;
  primary_keyword: string | null;
  category: string | null;
  generated_at: string;
}

export interface AppIdeaListResponse {
  ideas: AppIdea[];
  total: number;
  skip: number;
  limit: number;
  last_generated: string | null;
}

export async function getIdeas(params: {
  sort_by?: string;
  sort_order?: string;
  pattern_type?: string;
  category?: string;
  keyword?: string;
  skip?: number;
  limit?: number;
} = {}): Promise<AppIdeaListResponse> {
  const p = new URLSearchParams();
  if (params.sort_by) p.set('sort_by', params.sort_by);
  if (params.sort_order) p.set('sort_order', params.sort_order);
  if (params.pattern_type) p.set('pattern_type', params.pattern_type);
  if (params.category) p.set('category', params.category);
  if (params.keyword) p.set('keyword', params.keyword);
  p.set('skip', String(params.skip ?? 0));
  p.set('limit', String(params.limit ?? 20));
  const res = await fetch(`${API_BASE}/ideas?${p.toString()}`, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function generateIdeas(): Promise<AppIdeaListResponse> {
  const res = await fetch(`${API_BASE}/ideas/generate`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Keyword Intelligence
// ---------------------------------------------------------------------------

export interface OrganicKeyword {
  keyword: string;
  rank: number;
  search_volume: number;
  difficulty: number;
}

export interface AdsKeyword {
  keyword: string;
  position: number;
}

export interface KeywordIntelligence {
  app_id: string;
  app_name: string;
  primary_keyword: string | null;
  confidence: number;
  organic_keywords: OrganicKeyword[];
  ads_keywords: AdsKeyword[];
  traffic_mix: { organic: number; ads: number };
  total_snapshots: number;
  last_scanned: string | null;
}

export async function getKeywordIntelligence(appId: number): Promise<KeywordIntelligence> {
  const res = await fetch(`${API_BASE}/apps/${appId}/keyword-intelligence`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`API error: ${res.status}`); }
  return res.json();
}

export async function runKeywordSearch(keyword: string, country = 'us'): Promise<{ status: string; total_results: number }> {
  const res = await fetch(
    `${API_BASE}/keyword-tracker/search?keyword=${encodeURIComponent(keyword)}&country=${country}`,
    { method: 'POST', headers: _authHeaders() }
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Keyword Extraction Intelligence (metadata-based)
// ---------------------------------------------------------------------------

export interface ExtractedKeyword {
  keyword: string;
  source: 'title' | 'subtitle' | 'description';
  search_volume: number;   // 0-100 heuristic
  difficulty: number;      // 0-100 heuristic
  traffic_score: number;   // search_volume × CTR(rank)
  app_rank: number | null; // position in iTunes search; null if not ranked
  result_count: number;
  extracted_at: string | null;
}

export interface KeywordExtractionResponse {
  app_id: string;
  app_name: string;
  keywords: ExtractedKeyword[];
  extracting: boolean;
  total: number;
  last_extracted: string | null;
}

export async function getExtractedKeywords(
  appId: number,
  refresh = false,
): Promise<KeywordExtractionResponse> {
  const url = `${API_BASE}/apps/${appId}/keywords/intelligence${refresh ? '?refresh=true' : ''}`;
  const res = await fetch(url, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function triggerKeywordExtraction(appId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/apps/${appId}/keywords/intelligence/extract`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  // Without this check an HTTP error was treated as a successful trigger
  // and the UI polled forever for an extraction that never started.
  if (!res.ok) throw new Error(`Extraction trigger failed (${res.status})`);
}

// ---------------------------------------------------------------------------
// Keyword Discovery (autocomplete + affix expansion per app)
// ---------------------------------------------------------------------------

export interface DiscoveredKeyword {
  keyword: string;
  source: 'autocomplete' | 'prefix' | 'suffix' | 'alphabet' | 'competitor';
  source_keyword: string;
  search_volume: number;
  difficulty: number;
  traffic_score: number;
  app_rank: number | null;
  competitor_rank: number | null;
  keyword_gap: boolean;
  trend_score: number;
  trend_direction: 'rising' | 'stable' | 'declining';
  opportunity_score: number;
  created_at: string | null;
  // V2 per-app scoring
  chance_score: number;
  kei: number;
  estimated_installs: number;
  volume_score: number;
  difficulty_v2: number;
}

export interface DiscoveredKeywordsResponse {
  app_id: string;
  app_name: string;
  keywords: DiscoveredKeyword[];
  total: number;
  discovering: boolean;
  last_discovered: string | null;
}

export async function getDiscoveredKeywords(
  appId: number,
  limit = 200,
): Promise<DiscoveredKeywordsResponse> {
  const res = await fetch(`${API_BASE}/apps/${appId}/keywords/discovered?limit=${limit}`, {
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function triggerKeywordDiscovery(
  appId: number,
): Promise<DiscoveredKeywordsResponse> {
  const res = await fetch(`${API_BASE}/apps/${appId}/keywords/discover`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Phase-1 Keyword Opportunities (alphabet + competitor + gap + scoring)
// ---------------------------------------------------------------------------

export interface KeywordOpportunityItem {
  keyword: string;
  search_volume: number;
  difficulty: number;
  trend_score: number;
  trend_direction: 'rising' | 'stable' | 'declining';
  app_rank: number | null;
  competitor_rank: number | null;
  keyword_gap: boolean;
  opportunity_score: number;
  source: string;
  // V2 per-app scoring
  chance_score: number;
  kei: number;
  estimated_installs: number;
  volume_score: number;
  difficulty_v2: number;
}

export interface KeywordOpportunitiesResponse {
  app_id: string;
  app_name: string;
  opportunities: KeywordOpportunityItem[];
  total: number;
  discovering: boolean;
}

export async function getKeywordOpportunitiesForApp(
  appId: number,
  limit = 50,
): Promise<KeywordOpportunitiesResponse> {
  const res = await fetch(
    `${API_BASE}/apps/${appId}/keywords/opportunities?limit=${limit}`,
    { headers: _authHeaders() },
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function triggerPhase1Discovery(
  appId: number,
): Promise<KeywordOpportunitiesResponse> {
  const res = await fetch(`${API_BASE}/apps/${appId}/keywords/discover-phase1`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Install & Revenue Estimates
// ---------------------------------------------------------------------------

export interface InstallEstimate {
  app_id: number;
  estimated_installs_min: number;
  estimated_installs_max: number;
  install_confidence: number;
  methodology: string;
}

export interface RevenueEstimate {
  app_id: number;
  estimated_revenue_monthly_min: number;
  estimated_revenue_monthly_max: number;
  model: string;
  arpu: number;
  category: string;
}

export async function getInstallEstimate(appId: number): Promise<InstallEstimate> {
  const res = await fetch(`${API_BASE}/apps/${appId}/install-estimate`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`API error: ${res.status}`); }
  return res.json();
}

export async function getRevenueEstimate(appId: number): Promise<RevenueEstimate> {
  const res = await fetch(`${API_BASE}/apps/${appId}/revenue-estimate`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`API error: ${res.status}`); }
  return res.json();
}

export interface DownloadEstimate {
  app_id: number;
  estimated_downloads_daily: number;
  estimated_downloads_monthly: number;
  downloads_range_low: number;
  downloads_range_high: number;
  estimated_revenue_monthly: number | null;
  revenue_range_low: number | null;
  revenue_range_high: number | null;
  estimation_confidence: number;
  confidence_label: 'low' | 'medium' | 'high';
  monetization_model_hint: string | null;
  factor_breakdown: {
    rank_baseline: number | null;
    review_velocity_estimate: number | null;
    visibility_estimate: number | null;
    momentum_adjustment_pct: number | null;
    weights_used: Record<string, number> | null;
    confidence_factors: Record<string, number> | null;
  };
  estimation_notes: string;
}

export async function getDownloadEstimate(appId: number): Promise<DownloadEstimate> {
  const res = await fetch(`${API_BASE}/apps/${appId}/download-estimate`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`API error: ${res.status}`); }
  return res.json();
}

// ---------------------------------------------------------------------------
// Keyword History
// ---------------------------------------------------------------------------

export interface KeywordHistoryPoint {
  date: string;
  best_rank: number;
  is_sponsored: boolean;
}

export interface KeywordHistory {
  app_id: string;
  keyword: string;
  country: string;
  history: KeywordHistoryPoint[];
  current_rank: number | null;
  total_days: number;
}

export async function getKeywordHistory(
  appId: number,
  keyword: string,
  country = 'us',
  days = 90
): Promise<KeywordHistory> {
  const res = await fetch(
    `${API_BASE}/apps/${appId}/keyword-history?keyword=${encodeURIComponent(keyword)}&country=${country}&days=${days}`,
    { headers: _authHeaders() }
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAppKeywords(appId: number, country = 'us'): Promise<string[]> {
  const res = await fetch(
    `${API_BASE}/apps/${appId}/keyword-history/keywords?country=${country}`,
    { headers: _authHeaders() }
  );
  if (!res.ok) return [];
  const data = await res.json();
  return data.keywords ?? [];
}

// ---------------------------------------------------------------------------
// Niche Radar
// ---------------------------------------------------------------------------

export interface NicheRadarItem {
  niche_name: string;
  niche_score: number;
  signal_type: 'keyword_growth' | 'ranking_momentum' | 'feature_gap';
  description: string;
  keywords: string[];
  app_count: number;
  trend: number;
  search_volume: number;
  difficulty: number;
  detected_at: string;
}

export interface NicheRadarResponse {
  niches: NicheRadarItem[];
  total: number;
  scanned_at: string;
}

export async function getNicheRadar(limit = 20): Promise<NicheRadarResponse> {
  const res = await fetch(`${API_BASE}/niche-radar?limit=${limit}`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`API error: ${res.status}`); }
  return res.json();
}

// ---------------------------------------------------------------------------
// Review Intelligence
// ---------------------------------------------------------------------------

export interface ReviewIntelligence {
  app_id: number | null;
  app_name: string | null;
  feature_requests: string[];
  competitor_mentions: string[];
  pricing_complaints: string[];
  pain_points: string[];
  sentiment_summary: string;
  opportunity_score: number;
  reviews_analyzed: number;
}

export async function getReviewIntelligence(appId: number, force = false): Promise<ReviewIntelligence> {
  const res = await fetch(
    `${API_BASE}/apps/${appId}/review-intelligence?force=${force}`,
    { headers: _authHeaders() }
  );
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`API error: ${res.status}`); }
  return res.json();
}

// ---------------------------------------------------------------------------
// App Autopsy
// ---------------------------------------------------------------------------

export interface AppAutopsy {
  app_id: number;
  app_name: string;
  developer: string | null;
  category: string | null;
  current_rating: number | null;
  current_reviews: number | null;
  current_rank: number | null;
  price: number | null;
  is_free: boolean | null;
  has_iap: boolean;
  release_date: string | null;
  estimated_installs_min: number | null;
  estimated_installs_max: number | null;
  install_confidence: number | null;
  estimated_revenue_monthly_min: number | null;
  estimated_revenue_monthly_max: number | null;
  rating_momentum: number;
  review_growth_30d: number;
  rank_trajectory: {
    current_rank: number | null;
    rank_30d_ago: number | null;
    rank_delta: number;
    trend: string;
  };
  update_cadence: {
    avg_days_between_releases: number | null;
    versions_last_90d: number;
  };
  competitor_feature_gaps: Array<{
    feature: string;
    total_mentions: number;
    apps_missing: number;
  }>;
  strengths: string[];
  narrative: string | null;
}

export async function getAppAutopsy(appId: number, useLlm = true): Promise<AppAutopsy> {
  const res = await fetch(
    `${API_BASE}/apps/${appId}/autopsy?use_llm=${useLlm}`,
    { headers: _authHeaders() }
  );
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`API error: ${res.status}`); }
  return res.json();
}

// ---------------------------------------------------------------------------
// Apps Blowing Up
// ---------------------------------------------------------------------------

export interface BlowingUpApp {
  id: number;
  app_id: string;
  name: string;
  developer: string | null;
  icon_url: string | null;
  primary_category: string | null;
  current_rank: number | null;
  current_rating: number | null;
  current_reviews: number | null;
  // Composite score
  blowing_up_score: number;
  // Component scores (0-100)
  rank_velocity_score: number;
  rank_change_score: number;
  reviews_velocity_score: number;
  chart_presence_score: number;
  cross_market_score: number;
  consistency_score: number;
  confidence_score: number;
  // Raw signals
  rank_change: number;
  rank_velocity: number;
  reviews_velocity: number;
  chart_appearances: number;
  markets_count: number;
  // Labels
  badges: string[];
  why_flagged: string[];
  computed_at: string | null;
}

export interface BlowingUpResponse {
  status: 'success' | 'insufficient_data' | 'empty';
  message: string | null;
  required_signals: string[] | null;
  items: BlowingUpApp[];
  total: number;
  exploding_count: number | null;
  top_score: number | null;
  avg_rank_velocity: number | null;
}

export interface BlowingUpFilters {
  limit?: number;
  skip?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  min_confidence?: number;
  min_reviews_velocity?: number;
  category?: string;
  chart_type?: string;
  timeframe?: '24h' | '3d' | '7d';
}

export async function getBlowingUpApps(filters: BlowingUpFilters = {}): Promise<BlowingUpResponse> {
  const params = new URLSearchParams();
  if (filters.limit     !== undefined) params.set('limit',     String(filters.limit));
  if (filters.skip      !== undefined) params.set('skip',      String(filters.skip));
  if (filters.sort_by)                 params.set('sort_by',   filters.sort_by);
  if (filters.sort_order)              params.set('sort_order', filters.sort_order);
  if (filters.min_confidence !== undefined) params.set('min_confidence', String(filters.min_confidence));
  if (filters.min_reviews_velocity !== undefined) params.set('min_reviews_velocity', String(filters.min_reviews_velocity));
  if (filters.category)                params.set('category',  filters.category);
  if (filters.chart_type)              params.set('chart_type', filters.chart_type);
  if (filters.timeframe)               params.set('timeframe', filters.timeframe);

  const qs = params.toString();
  const url = `${API_BASE}/apps/blowing-up${qs ? `?${qs}` : ''}`;
  const res = await fetch(url, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ===========================================================================
// Growth Intelligence Types
// ===========================================================================

export interface MetricSnapshot {
  id: number;
  app_id: number;
  snapshot_at: string;
  estimated_downloads_min: number | null;
  estimated_downloads_max: number | null;
  install_confidence: number | null;
  estimated_revenue_monthly_min: number | null;
  estimated_revenue_monthly_max: number | null;
  revenue_confidence: number | null;
  monetization_model: string | null;
  has_ads_signal: boolean;
  campaign_confidence: number;
}

export interface MetricSnapshotHistory {
  app_id: number;
  snapshots: MetricSnapshot[];
  latest: MetricSnapshot | null;
  downloads_delta_7d: { delta_min: number; delta_max: number; change_pct: number } | null;
}

export interface AdCreative {
  id: number;
  app_id: number;
  network: string;
  external_creative_id: string | null;
  format: string | null;
  creative_url: string | null;
  preview_url: string | null;
  title: string | null;
  body: string | null;
  cta: string | null;
  landing_url: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  is_active: boolean;
}

export interface AdCampaign {
  id: number;
  app_id: number;
  network: string;
  campaign_key: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  active_creatives_count: number;
  countries: string[] | null;
  status: string;
  campaign_confidence: number;
}

export interface AppAdIntelligence {
  app_id: number;
  campaigns: AdCampaign[];
  creatives: AdCreative[];
  total_campaigns: number;
  active_campaigns: number;
  total_creatives: number;
  active_creatives: number;
  has_active_campaign: boolean;
  networks: string[];
}

export interface AdIntelligenceListItem {
  app_id: string;
  app_db_id: number;
  name: string;
  icon_url: string | null;
  primary_category: string | null;
  current_rank: number | null;
  networks: string[];
  active_campaigns: number;
  active_creatives: number;
  max_confidence: number;
  first_ad_seen: string | null;
  last_ad_seen: string | null;
}

export interface AdIntelligenceListResponse {
  status: string;
  items: AdIntelligenceListItem[];
  total: number;
  active_count: number;
}

export interface GrowthEvent {
  id: number;
  app_id: number;
  detected_at: string;
  event_type: string;
  confidence: number;
  explanation: string | null;
  signals: Record<string, unknown> | null;
  started_at_estimate: string | null;
  active_status: boolean;
}

export interface AppGrowthEvents {
  app_id: number;
  events: GrowthEvent[];
  latest_event: GrowthEvent | null;
  total: number;
}

export interface CampaignTrackingListItem {
  app_id: string;
  app_db_id: number;
  name: string;
  icon_url: string | null;
  primary_category: string | null;
  current_rank: number | null;
  event_type: string;
  confidence: number;
  explanation: string | null;
  detected_at: string;
  started_at_estimate: string | null;
  blowing_up_score: number | null;
}

export interface CampaignTrackingListResponse {
  status: string;
  items: CampaignTrackingListItem[];
  total: number;
  by_type: Record<string, number> | null;
}

// ===========================================================================
// Growth Intelligence API functions
// ===========================================================================

export async function getAppMetrics(appId: number, days = 30): Promise<MetricSnapshotHistory> {
  const res = await fetch(`${API_BASE}/apps/${appId}/metrics?days=${days}`, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.status}`);
  return res.json();
}

export async function getAppAdIntelligence(appId: number): Promise<AppAdIntelligence> {
  const res = await fetch(`${API_BASE}/apps/${appId}/ads`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`Failed to fetch ad intelligence: ${res.status}`); }
  return res.json();
}

export async function scanAppAds(appId: number): Promise<{ status: string; creatives_upserted: number; campaigns_upserted: number }> {
  const res = await fetch(`${API_BASE}/apps/${appId}/ads/scan`, { method: 'POST', headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`Ad scan failed: ${res.status}`); }
  return res.json();
}

export async function getAdIntelligenceList(params: {
  network?: string;
  active_only?: boolean;
  skip?: number;
  limit?: number;
}): Promise<AdIntelligenceListResponse> {
  const p = new URLSearchParams();
  if (params.network) p.set('network', params.network);
  if (params.active_only !== undefined) p.set('active_only', String(params.active_only));
  if (params.skip !== undefined) p.set('skip', String(params.skip));
  if (params.limit !== undefined) p.set('limit', String(params.limit));
  const res = await fetch(`${API_BASE}/ads?${p}`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`Failed to fetch ad intelligence list: ${res.status}`); }
  return res.json();
}

export async function getAppGrowthEvents(appId: number, activeOnly = false): Promise<AppGrowthEvents> {
  const res = await fetch(`${API_BASE}/apps/${appId}/growth-events?active_only=${activeOnly}`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`Failed to fetch growth events: ${res.status}`); }
  return res.json();
}

export async function getCampaignTrackingList(params: {
  event_type?: string;
  active_only?: boolean;
  min_confidence?: number;
  skip?: number;
  limit?: number;
}): Promise<CampaignTrackingListResponse> {
  const p = new URLSearchParams();
  if (params.event_type) p.set('event_type', params.event_type);
  if (params.active_only !== undefined) p.set('active_only', String(params.active_only));
  if (params.min_confidence !== undefined) p.set('min_confidence', String(params.min_confidence));
  if (params.skip !== undefined) p.set('skip', String(params.skip));
  if (params.limit !== undefined) p.set('limit', String(params.limit));
  const res = await fetch(`${API_BASE}/campaigns?${p}`, { headers: _authHeaders() });
  if (!res.ok) { await _checkUpgrade(res); throw new Error(`Failed to fetch campaigns: ${res.status}`); }
  return res.json();
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface SubscriptionInfo {
  plan_code: string;
  status: string;
  trial_ends_at: string | null;
  is_trialing: boolean;
  trial_days_left: number | null;
  trial_expired: boolean;
}

export interface WorkspaceInfo {
  id: number;
  name: string;
  slug: string;
  role: 'owner' | 'admin' | 'member';
  subscription: SubscriptionInfo | null;
}

export interface UserInfo {
  id: number;
  email: string;
  full_name: string | null;
  is_superadmin: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
  workspace: WorkspaceInfo;
  checkout_url?: string | null;
  requires_email_verification?: boolean;
}

export interface MeResponse {
  user: UserInfo;
  workspace: WorkspaceInfo;
}

export async function authRegister(
  email: string,
  password: string,
  fullName?: string,
  planCode: string = 'starter',
): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName ?? null, plan_code: planCode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Registration failed (${res.status})`);
  }
  return res.json();
}

export async function authVerifyEmail(token: string): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Verification failed (${res.status})`);
  }
  return res.json();
}

export async function authResendVerification(email: string): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/auth/resend-verification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Resend failed (${res.status})`);
  }
  return res.json();
}

export async function authCreateCheckoutAfterVerify(authToken: string): Promise<{ checkout_url: string | null }> {
  return fetchApiAuth<{ checkout_url: string | null }>('/auth/create-checkout-after-verify', authToken, {
    method: 'POST',
  });
}

export async function createStripeCheckout(token: string, planCode: string): Promise<{ checkout_url: string }> {
  return fetchApiAuth<{ checkout_url: string }>('/stripe/create-checkout', token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_code: planCode }),
  });
}

export async function createBillingPortal(token: string): Promise<{ portal_url: string }> {
  return fetchApiAuth<{ portal_url: string }>('/stripe/billing-portal', token, {
    method: 'POST',
  });
}

export async function authLogin(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Login failed (${res.status})`);
  }
  return res.json();
}

export async function authMe(token: string): Promise<MeResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      signal: controller.signal,
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      // Expose status so callers can tell "token rejected" (401/403 → log
      // out) apart from a transient backend/network failure (keep session).
      const err = new Error(`Unauthorized (${res.status})`) as Error & { status?: number };
      err.status = res.status;
      throw err;
    }
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

// ---------------------------------------------------------------------------
// Plan usage
// ---------------------------------------------------------------------------

export interface UsageCounts {
  app_imports: number;
  keyword_refreshes: number;
  ai_requests: number;
  exports: number;
}

export interface PlanLimits {
  app_imports: number | null;
  keyword_refreshes: number | null;
  ai_requests: number | null;
  exports: number | null;
}

export interface UsageSummary {
  plan: string;
  month: string;
  usage: UsageCounts;
  limits: PlanLimits;
}

export interface PlanLimitError {
  code: 'PLAN_LIMIT_EXCEEDED';
  action: string;
  message: string;
  current_usage: number;
  limit: number;
  plan: string;
  upgrade_message: string;
}

export async function getUsageSummary(token: string): Promise<UsageSummary> {
  const res = await fetch(`${API_BASE}/usage`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    return {
      plan: 'unknown',
      month: '',
      usage: { app_imports: 0, keyword_refreshes: 0, ai_requests: 0, exports: 0 },
      limits: { app_imports: null, keyword_refreshes: null, ai_requests: null, exports: null },
    };
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Settings — profile + password mutations
// ---------------------------------------------------------------------------

export interface ProfileUpdateData {
  full_name?: string;
  workspace_name?: string;
}

export async function updateProfile(
  token: string,
  data: ProfileUpdateData,
): Promise<MeResponse> {
  return fetchApiAuth<MeResponse>('/auth/profile', token, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function changePassword(
  token: string,
  data: { current_password: string; new_password: string },
): Promise<{ ok: boolean }> {
  return fetchApiAuth<{ ok: boolean }>('/auth/password', token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

/**
 * Parse a 402 fetch response into a PlanLimitError, or null if not a limit error.
 */
export async function parsePlanLimitError(res: Response): Promise<PlanLimitError | null> {
  if (res.status !== 402) return null;
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (detail?.code === 'PLAN_LIMIT_EXCEEDED') return detail as PlanLimitError;
  } catch {
    // ignore
  }
  return null;
}


// ---------------------------------------------------------------------------
// Favorites
// ---------------------------------------------------------------------------

export interface FavoriteAppItem {
  id: number;
  app_id: number;
  store_app_id: string;
  name: string;
  icon_url?: string | null;
  developer?: string | null;
  primary_category?: string | null;
  current_rating?: number | null;
  current_reviews?: number | null;
  current_rank?: number | null;
  price: number;
  is_free: boolean;
  favorited_at: string;
}

export interface FavoriteListResponse {
  favorites: FavoriteAppItem[];
  total: number;
  skip: number;
  limit: number;
}

export async function getFavorites(skip = 0, limit = 50): Promise<FavoriteListResponse> {
  const res = await fetch(`${API_BASE}/favorites?skip=${skip}&limit=${limit}`, {
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch favorites (${res.status})`);
  return res.json();
}

export async function getFavoriteIds(): Promise<number[]> {
  const res = await fetch(`${API_BASE}/favorites/ids`, {
    headers: _authHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.app_ids ?? [];
}

export async function addFavorite(appId: number): Promise<{ id: number; app_id: number }> {
  const res = await fetch(`${API_BASE}/favorites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify({ app_id: appId }),
  });
  if (!res.ok) throw new Error(`Failed to add favorite (${res.status})`);
  return res.json();
}

export async function removeFavorite(appId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/favorites/${appId}`, {
    method: 'DELETE',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to remove favorite (${res.status})`);
}


// ---------------------------------------------------------------------------
// My Apps — user's own apps
// ---------------------------------------------------------------------------

export interface MyAppItem {
  id: number;
  app_id: number;
  store_app_id: string;
  name: string;
  icon_url?: string | null;
  developer?: string | null;
  primary_category?: string | null;
  current_rating?: number | null;
  current_reviews?: number | null;
  current_rank?: number | null;
  price: number;
  is_free: boolean;
  added_at: string;
  aso_score?: number | null;
  aso_grade?: string | null;
}

export interface MyAppListResponse {
  apps: MyAppItem[];
  total: number;
}

export async function getMyApps(): Promise<MyAppListResponse> {
  const res = await fetch(`${API_BASE}/my-apps`, {
    headers: _authHeaders(),
  });
  if (!res.ok) return { apps: [], total: 0 };
  return res.json();
}

export async function getMyAppIds(): Promise<number[]> {
  const res = await fetch(`${API_BASE}/my-apps/ids`, {
    headers: _authHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.app_ids || [];
}

export async function addMyApp(appId: number): Promise<{ id: number; app_id: number }> {
  const res = await fetch(`${API_BASE}/my-apps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify({ app_id: appId }),
  });
  if (!res.ok) throw new Error(`Failed to add my app (${res.status})`);
  return res.json();
}

export async function removeMyApp(appId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/my-apps/${appId}`, {
    method: 'DELETE',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to remove my app (${res.status})`);
}

export async function refreshMyApp(appId: number): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/my-apps/${appId}/refresh`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to refresh app (${res.status})`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Admin Console
// ---------------------------------------------------------------------------

export interface AdminRevenueBreakdownItem {
  count: number;
  price: number;
  mrr: number;
}

export interface AdminDashboardStats {
  total_users: number;
  active_users: number;
  total_workspaces: number;
  total_apps: number;
  total_keywords: number;
  total_reviews: number;
  plans: Record<string, number>;
  usage_this_month: Record<string, number>;
  revenue: {
    mrr: number;
    arr: number;
    breakdown: Record<string, AdminRevenueBreakdownItem>;
    total_paying: number;
  };
  trial_funnel: {
    total_trials: number;
    active_trials: number;
    converted: number;
    expired: number;
    lifetime?: number;
    conversion_rate: number;
  };
  usage_leaderboard: {
    user_id: number;
    email: string;
    full_name: string | null;
    plan_code: string | null;
    app_imports: number;
    keyword_refreshes: number;
    ai_requests: number;
    exports: number;
    total: number;
  }[];
  billing_log: {
    id: number;
    admin_email: string | null;
    action: string;
    target_type: string | null;
    target_id: number | null;
    details: Record<string, unknown> | null;
    created_at: string | null;
  }[];
}

export interface AdminUserItem {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superadmin: boolean;
  created_at: string | null;
  workspace_id: number | null;
  workspace_name: string | null;
  workspace_slug: string | null;
  plan_code: string | null;
  plan_status: string | null;
  trial_ends_at: string | null;
  trial_days_left: number | null;
  role: string | null;
  usage: Record<string, number> | null;
}

export interface AdminWorkspaceItem {
  id: number;
  name: string;
  slug: string;
  created_at: string | null;
  owner_email: string | null;
  member_count: number;
  plan_code: string | null;
  plan_status: string | null;
  usage: Record<string, number>;
}

export interface AdminJobItem {
  job_id: string;
  next_run: string | null;
  trigger: string | null;
}

export interface AdminSystemHealth {
  db_size_mb: number;
  total_tables: number;
  app_count: number;
  keyword_count: number;
  review_count: number;
  pending_queue: number;
  uptime_info: string;
}

async function _adminFetch<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function adminGetDashboard(): Promise<AdminDashboardStats> {
  return _adminFetch<AdminDashboardStats>('/admin-console/dashboard');
}

export interface AdminUserDetail {
  user: {
    id: number;
    email: string;
    full_name: string | null;
    is_active: boolean;
    is_superadmin: boolean;
    created_at: string | null;
    last_active: string | null;
  };
  workspace: {
    id: number;
    name: string;
    slug: string;
    role: string | null;
    created_at: string | null;
  } | null;
  subscription: {
    plan_code: string;
    status: string;
    trial_ends_at: string | null;
    trial_days_left: number | null;
    current_period_end: string | null;
  } | null;
  usage: Record<string, number> | null;
  favorites: { app_id: number; name: string; icon_url: string | null; developer: string | null; added_at: string | null }[];
  favorite_count: number;
  my_apps: { app_id: number; name: string; icon_url: string | null; developer: string | null; added_at: string | null }[];
  my_app_count: number;
  activity: UserActivityItem[];
  activity_count: number;
  admin_log: { id: number; admin_email: string | null; action: string; details: Record<string, unknown> | null; created_at: string | null }[];
}

export async function adminGetUserDetail(userId: number): Promise<AdminUserDetail> {
  return _adminFetch(`/admin-console/users/${userId}/detail`);
}

export async function adminGetUsers(search?: string, skip = 0, limit = 50, filter?: string): Promise<{ users: AdminUserItem[]; total: number }> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (search) params.set('search', search);
  if (filter) params.set('filter', filter);
  return _adminFetch(`/admin-console/users?${params}`);
}

export async function adminCreateUser(body: { email: string; password: string; full_name?: string; plan_code?: string }): Promise<{ ok: boolean; user_id: number; email: string }> {
  const res = await fetch(`${API_BASE}/admin-console/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed (${res.status})`);
  }
  return res.json();
}

export async function adminUpdateUser(userId: number, body: Record<string, unknown>): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/users/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function adminDeleteUser(userId: number): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/users/${userId}`, {
    method: 'DELETE',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function adminGetWorkspaces(search?: string, skip = 0, limit = 50): Promise<{ workspaces: AdminWorkspaceItem[]; total: number }> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (search) params.set('search', search);
  return _adminFetch(`/admin-console/workspaces?${params}`);
}

export async function adminUpdateSubscription(workspaceId: number, body: Record<string, unknown>): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/subscriptions/${workspaceId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function adminGetJobs(): Promise<{ jobs: AdminJobItem[]; total: number }> {
  return _adminFetch('/admin-console/jobs');
}

export async function adminTriggerJob(jobId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/jobs/${jobId}/trigger`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function adminGetSystemHealth(): Promise<AdminSystemHealth> {
  return _adminFetch('/admin-console/system');
}

export async function adminBulkBackfill(batchSize = 1000): Promise<{ ok: boolean; message: string; total_incomplete: number }> {
  const res = await fetch(`${API_BASE}/admin-console/apps/bulk-backfill?batch_size=${batchSize}`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function adminResetPassword(userId: number, newPassword: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/users/${userId}/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify({ new_password: newPassword }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed (${res.status})`);
  }
  return res.json();
}

export async function adminImpersonateUser(userId: number): Promise<{ ok: boolean; token: string; email: string }> {
  const res = await fetch(`${API_BASE}/admin-console/users/${userId}/impersonate`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed (${res.status})`);
  }
  return res.json();
}

export async function adminBulkAction(body: { user_ids: number[]; action: string; plan_code?: string }): Promise<{ ok: boolean; affected: number }> {
  const res = await fetch(`${API_BASE}/admin-console/users/bulk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function adminExportUsersCSV(): Promise<Blob> {
  const res = await fetch(`${API_BASE}/admin-console/export/users`, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.blob();
}

export async function adminExportWorkspacesCSV(): Promise<Blob> {
  const res = await fetch(`${API_BASE}/admin-console/export/workspaces`, { headers: _authHeaders() });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.blob();
}

export interface AdminTrialItem {
  workspace_id: number;
  workspace_name: string;
  owner_email: string | null;
  plan_code: string;
  status: string;
  trial_ends_at: string | null;
  days_left: number | null;
}

export async function adminGetTrials(): Promise<{ trials: AdminTrialItem[]; total: number }> {
  return _adminFetch('/admin-console/trials');
}

export async function adminExtendTrial(workspaceId: number, days: number): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/trials/${workspaceId}/extend?days=${days}`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export interface AdminActivityItem {
  id: number;
  admin_email: string | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

export interface UserActivityItem {
  id: number;
  action: string;
  detail: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

export async function adminGetUserActivity(userId: number, skip = 0, limit = 50): Promise<{ user_id: number; email: string; full_name: string | null; activity: UserActivityItem[]; total: number }> {
  return _adminFetch(`/admin-console/users/${userId}/activity?skip=${skip}&limit=${limit}`);
}

export async function adminGetActivity(skip = 0, limit = 50): Promise<{ activity: AdminActivityItem[]; total: number }> {
  return _adminFetch(`/admin-console/activity?skip=${skip}&limit=${limit}`);
}

export async function adminGetJobMetrics(): Promise<{ metrics: Record<string, Record<string, unknown>>; total: number }> {
  return _adminFetch('/admin-console/job-metrics');
}

export async function adminRescrapeApp(appId: number): Promise<{ ok: boolean; name: string }> {
  const res = await fetch(`${API_BASE}/admin-console/apps/${appId}/rescrape`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export interface AdminAnnouncement {
  id: number;
  title: string;
  message: string;
  type: string;
  is_active: boolean;
  created_at: string | null;
}

export async function adminGetAnnouncements(): Promise<{ announcements: AdminAnnouncement[]; total: number }> {
  return _adminFetch('/admin-console/announcements');
}

export async function adminCreateAnnouncement(body: { title: string; message: string; type?: string }): Promise<{ ok: boolean; id: number }> {
  const res = await fetch(`${API_BASE}/admin-console/announcements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function adminUpdateAnnouncement(id: number, body: Record<string, unknown>): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/announcements/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function adminDeleteAnnouncement(id: number): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/admin-console/announcements/${id}`, {
    method: 'DELETE',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed (${res.status})`);
  return res.json();
}

export async function getActiveAnnouncements(): Promise<{ announcements: { id: number; title: string; message: string; type: string; created_at: string | null }[] }> {
  return fetchApi('/admin-console/announcements/active');
}


// ---------------------------------------------------------------------------
// Competitor Comparison
// ---------------------------------------------------------------------------

export interface CompetitorFeatureGap {
  feature: string;
  mentions: number;
  detected_at?: string | null;
}

export interface CompetitorAppSummary {
  app_id: number;
  store_app_id: string;
  name: string;
  icon_url?: string | null;
  developer?: string | null;
  primary_category?: string | null;
  current_rank?: number | null;
  current_rating?: number | null;
  current_reviews?: number | null;
  estimated_installs_min?: number | null;
  estimated_installs_max?: number | null;
  install_confidence?: number | null;
  estimated_revenue_monthly_min?: number | null;
  estimated_revenue_monthly_max?: number | null;
  is_free: boolean;
  price: number;
  review_velocity_30d: number;
  keyword_count: number;
  feature_gaps: CompetitorFeatureGap[];
}

export interface CompetitorKeywordOverlapApp {
  app_id: number;
  name: string;
  total: number;
  shared: number;
  unique: number;
  unique_samples: string[];
}

export interface CompetitorKeywordOverlap {
  shared_by_all: string[];
  shared_by_all_count: number;
  per_app: CompetitorKeywordOverlapApp[];
}

export interface CompetitorCompareResponse {
  apps: CompetitorAppSummary[];
  keyword_overlap: CompetitorKeywordOverlap;
  winners: Record<string, number | null>;
  compared_count: number;
  generated_at: string;
}

export async function compareCompetitors(appIds: number[]): Promise<CompetitorCompareResponse> {
  const params = new URLSearchParams();
  appIds.forEach((id) => params.append('app_ids', String(id)));
  return fetchApi<CompetitorCompareResponse>(`/competitors/compare?${params.toString()}`);
}

// Rank history overlay for competitor comparison

export interface CompetitorRankHistoryApp {
  id: number;
  name: string;
}

export interface CompetitorRankHistoryResponse {
  apps: CompetitorRankHistoryApp[];
  series: Record<string, unknown>[];
  days: number;
}

export async function getCompetitorRankHistory(
  appIds: number[],
  days = 30,
): Promise<CompetitorRankHistoryResponse> {
  const params = new URLSearchParams();
  appIds.forEach((id) => params.append('app_ids', String(id)));
  params.set('days', String(days));
  return fetchApi<CompetitorRankHistoryResponse>(`/competitors/rank-history?${params.toString()}`);
}

// Keyword Gap Analysis

export interface KeywordGapItem {
  keyword: string;
  gap_type: 'missing' | 'weak' | 'shared' | 'winning' | 'unique';
  target_rank: number | null;
  competitor_best_rank: number | null;
  competitor_ranks: Record<number, number | null>;
  volume_score: number;
  difficulty_v2: number;
  opportunity_priority: 'high' | 'medium' | 'low' | 'info';
}

export interface KeywordGapAppInfo {
  app_id: number;
  store_app_id: string;
  name: string;
  icon_url: string | null;
}

export interface KeywordGapSummary {
  total_keywords: number;
  missing: number;
  weak: number;
  shared: number;
  winning: number;
  unique: number;
  high_priority_gaps: number;
}

export interface KeywordGapReportResponse {
  target: KeywordGapAppInfo;
  competitors: KeywordGapAppInfo[];
  keywords: KeywordGapItem[];
  summary: KeywordGapSummary;
}

export async function getKeywordGaps(
  targetId: number,
  competitorIds: number[],
): Promise<KeywordGapReportResponse> {
  const params = new URLSearchParams();
  params.set('target_id', String(targetId));
  competitorIds.forEach((id) => params.append('competitor_ids', String(id)));
  return fetchApi<KeywordGapReportResponse>(`/competitors/keyword-gaps?${params.toString()}`);
}


// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export interface AlertItem {
  id: number;
  alert_type: string;
  name: string;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string | null;
  unread_count: number;
}

export interface AlertListResponse {
  alerts: AlertItem[];
  total: number;
}

export interface AlertEventItem {
  id: number;
  alert_id: number;
  alert_name: string | null;
  alert_type: string | null;
  title: string;
  message: string | null;
  data: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string | null;
}

export interface AlertEventListResponse {
  events: AlertEventItem[];
  total: number;
  unread_count: number;
}

export async function getAlerts(): Promise<AlertListResponse> {
  const res = await fetch(`${API_BASE}/alerts`, {
    headers: _authHeaders(),
  });
  if (!res.ok) return { alerts: [], total: 0 };
  return res.json();
}

export async function createAlert(body: {
  alert_type: string;
  name: string;
  config: Record<string, unknown>;
}): Promise<AlertItem> {
  const res = await fetch(`${API_BASE}/alerts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create alert (${res.status})`);
  }
  return res.json();
}

export async function updateAlert(
  alertId: number,
  body: { name?: string; config?: Record<string, unknown>; is_active?: boolean },
): Promise<AlertItem> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to update alert (${res.status})`);
  return res.json();
}

export async function deleteAlert(alertId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}`, {
    method: 'DELETE',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to delete alert (${res.status})`);
}

export async function getAlertEvents(
  limit = 50,
  offset = 0,
  unreadOnly = false,
): Promise<AlertEventListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (unreadOnly) params.set('unread_only', 'true');
  const res = await fetch(`${API_BASE}/alerts/events?${params}`, {
    headers: _authHeaders(),
  });
  if (!res.ok) return { events: [], total: 0, unread_count: 0 };
  return res.json();
}

export async function getAlertUnreadCount(): Promise<{ unread_count: number }> {
  const res = await fetch(`${API_BASE}/alerts/events/unread-count`, {
    headers: _authHeaders(),
  });
  if (!res.ok) return { unread_count: 0 };
  return res.json();
}

export async function markAlertEventRead(eventId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/events/${eventId}/read`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to mark event read (${res.status})`);
}

export async function markAllAlertEventsRead(): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/events/read-all`, {
    method: 'POST',
    headers: _authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to mark all read (${res.status})`);
}
