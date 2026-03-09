// Normalize to always include /api/v1.
// NEXT_PUBLIC_API_URL can be the backend origin alone
// (https://backend.railway.app) or include the path (…/api/v1) — both work.
// Unset → relative '/api/v1' → goes through the Next.js rewrite proxy.
const _rawBase = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/+$/, '');
const API_BASE = _rawBase === ''
  ? '/api/v1'
  : _rawBase.endsWith('/api/v1')
    ? _rawBase
    : `${_rawBase}/api/v1`;

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
  current_rank: number;
  rank_velocity: number;
  review_growth: number;
  rating_velocity: number;
  trend_score: number;
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

export interface KeywordOpportunity {
  keyword: string;
  search_volume: number;
  difficulty: number;
  trend: number;
  opportunity_score: number;
  current_apps: number;
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

async function fetchApi<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    next: { revalidate: 60 },
  });
  
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  
  return res.json();
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return fetchApi<DashboardStats>('/dashboard/stats');
}

export async function getTrendingApps(limit: number = 10): Promise<TrendingApp[]> {
  return fetchApi<TrendingApp[]>(`/trending?limit=${limit}`);
}

export async function getOpportunityOfDay(): Promise<OpportunityOfDay> {
  return fetchApi<OpportunityOfDay>('/opportunity-of-day');
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

export async function getCategories(): Promise<Category[]> {
  return fetchApi<Category[]>('/categories');
}

export async function getKeywords(limit: number = 50): Promise<Keyword[]> {
  return fetchApi<Keyword[]>(`/keywords?limit=${limit}`);
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
