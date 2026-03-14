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

const API_BASE = _resolveApiBase();

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
}

export interface OpportunityOfDayWrapper {
  status: 'success' | 'insufficient_data' | 'empty';
  item: OpportunityOfDay | null;
  message: string | null;
  required_signals: string[] | null;
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
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  skip?: number;
  limit?: number;
}

export interface AppListResponse {
  apps: App[];
  total: number;
  skip: number;
  limit: number;
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
  set('sort_by', filters.sort_by);
  set('sort_order', filters.sort_order || 'desc');
  params.set('skip', String(filters.skip ?? 0));
  params.set('limit', String(filters.limit ?? 50));

  const res = await fetch(`${API_BASE}/apps?${params.toString()}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Latest 60 Days
// ---------------------------------------------------------------------------

export interface LatestAppsParams {
  limit?: number;
  offset?: number;
  category?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export async function getLatestApps(params: LatestAppsParams = {}): Promise<AppListResponse> {
  const p = new URLSearchParams();
  if (params.limit)      p.set('limit',      String(params.limit));
  if (params.offset)     p.set('offset',     String(params.offset));
  if (params.category)   p.set('category',   params.category);
  if (params.sort_by)    p.set('sort_by',    params.sort_by);
  if (params.sort_order) p.set('sort_order', params.sort_order);
  const res = await fetch(`${API_BASE}/apps/latest-60-days?${p.toString()}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------

async function fetchApi<T>(endpoint: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }
    return res.json();
  } finally {
    clearTimeout(timeout);
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

export async function getKeywordOpportunities(
  minDifficulty: number = 0,
  maxDifficulty: number = 60
): Promise<KeywordOpportunity[]> {
  return fetchApi<KeywordOpportunity[]>(
    `/keyword-opportunities?min_difficulty=${minDifficulty}&max_difficulty=${maxDifficulty}`
  );
}

export async function getRankHistory(
  appId: number,
  days: number = 30
): Promise<RankHistory> {
  return fetchApi<RankHistory>(`/apps/${appId}/rank-history?days=${days}`);
}

export async function getApps(limit: number = 50): Promise<App[]> {
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

export async function searchAppsImport(
  query: string,
  limit: number = 10
): Promise<AppImportSearchResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return fetchApi<AppImportSearchResponse>(`/apps/import?${params}`);
}

export async function lookupApp(trackId: string): Promise<AppLookupResponse> {
  return fetchApi<AppLookupResponse>(`/apps/lookup/${trackId}`);
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
  const res = await fetch(`${API_BASE}/keywords/enhanced?${q}`, { cache: 'no-store' });
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
  const res = await fetch(`${API_BASE}/keywords/${encodeURIComponent(term)}/detail`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

export async function getKeywordTrend(term: string, days = 30): Promise<KeywordTrendResponse> {
  const res = await fetch(`${API_BASE}/keywords/${encodeURIComponent(term)}/trend?days=${days}`, { cache: 'no-store' });
  if (!res.ok) return { term, trend_points: [] };
  const data = await res.json();
  return { term: data?.term ?? term, trend_points: Array.isArray(data?.trend_points) ? data.trend_points : [] };
}

export async function getTrendingKeywords(limit = 20): Promise<TrendingKeywordsResponse> {
  const res = await fetch(`${API_BASE}/keywords/trending?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) return { keywords: [], total: 0 };
  const data = await res.json();
  return {
    keywords: Array.isArray(data?.keywords) ? data.keywords : [],
    total: data?.total ?? 0,
  };
}

export async function triggerKeywordPipeline(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/keywords/pipeline/run`, { method: 'POST', cache: 'no-store' });
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

export async function getAppVersions(appId: number): Promise<AppVersion[]> {
  return fetchApi<AppVersion[]>(`/apps/${appId}/versions`);
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
    cache: 'no-store',
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
  const res = await fetch(`${API_BASE}/ideas?${p.toString()}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function generateIdeas(): Promise<AppIdeaListResponse> {
  const res = await fetch(`${API_BASE}/ideas/generate`, {
    method: 'POST',
    cache: 'no-store',
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
  const res = await fetch(`${API_BASE}/apps/${appId}/keyword-intelligence`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function runKeywordSearch(keyword: string, country = 'us'): Promise<{ status: string; total_results: number }> {
  const res = await fetch(
    `${API_BASE}/keyword-tracker/search?keyword=${encodeURIComponent(keyword)}&country=${country}`,
    { method: 'POST', cache: 'no-store' }
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
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function triggerKeywordExtraction(appId: number): Promise<void> {
  await fetch(`${API_BASE}/apps/${appId}/keywords/intelligence/extract`, {
    method: 'POST',
    cache: 'no-store',
  });
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
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function triggerKeywordDiscovery(
  appId: number,
): Promise<DiscoveredKeywordsResponse> {
  const res = await fetch(`${API_BASE}/apps/${appId}/keywords/discover`, {
    method: 'POST',
    cache: 'no-store',
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
    { cache: 'no-store' },
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function triggerPhase1Discovery(
  appId: number,
): Promise<KeywordOpportunitiesResponse> {
  const res = await fetch(`${API_BASE}/apps/${appId}/keywords/discover-phase1`, {
    method: 'POST',
    cache: 'no-store',
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
  const res = await fetch(`${API_BASE}/apps/${appId}/install-estimate`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getRevenueEstimate(appId: number): Promise<RevenueEstimate> {
  const res = await fetch(`${API_BASE}/apps/${appId}/revenue-estimate`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
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
    { cache: 'no-store' }
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAppKeywords(appId: number, country = 'us'): Promise<string[]> {
  const res = await fetch(
    `${API_BASE}/apps/${appId}/keyword-history/keywords?country=${country}`,
    { cache: 'no-store' }
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
  const res = await fetch(`${API_BASE}/niche-radar?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
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
    { cache: 'no-store' }
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
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
    { cache: 'no-store' }
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
