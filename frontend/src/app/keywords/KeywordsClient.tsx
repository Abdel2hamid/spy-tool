'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { AppShell } from '@/components/AppShell';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import {
  KeywordListItem,
  KeywordListResponse,
  KeywordDetail,
  KeywordTrendResponse,
  GoogleTrendWeekPoint,
  getKeywordsEnhanced,
  getKeywordDetail,
  getKeywordTrend,
  triggerKeywordPipeline,
} from '@/lib/api';
import {
  Search,
  TrendingUp,
  TrendingDown,
  Minus,
  X,
  ChevronUp,
  ChevronDown,
  BarChart3,
  Zap,
  Shield,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Activity,
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Area,
  AreaChart,
} from 'recharts';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Classification config
// ---------------------------------------------------------------------------

const CLS_CONFIG = {
  easy: {
    label: 'Easy',
    bg: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
    icon: Zap,
    dot: 'bg-emerald-500',
  },
  medium: {
    label: 'Medium',
    bg: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
    icon: Shield,
    dot: 'bg-amber-500',
  },
  hard: {
    label: 'Hard',
    bg: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
    icon: AlertTriangle,
    dot: 'bg-red-500',
  },
  impossible: {
    label: 'Impossible',
    bg: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500',
    icon: XCircle,
    dot: 'bg-gray-400',
  },
} as const;

type Classification = keyof typeof CLS_CONFIG;

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function fmtVolume(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function fmtReviews(n: number | null | undefined): string {
  if (n == null) return '—';
  return fmtVolume(n);
}

// Google Trends interest level label
function trendScoreLabel(score: number): string {
  if (score >= 70) return 'Viral';
  if (score >= 50) return 'Strong';
  if (score >= 30) return 'Moderate';
  if (score >= 10) return 'Low';
  return 'None';
}

function trendGrowthColor(growth: number): string {
  if (growth >= 50) return 'text-emerald-600 dark:text-emerald-400';
  if (growth >= 10) return 'text-emerald-500 dark:text-emerald-500';
  if (growth >= -10) return 'text-gray-400';
  return 'text-red-500 dark:text-red-400';
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ScoreRing({ score, size = 40 }: { score: number; size?: number }) {
  const color =
    score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : score >= 30 ? '#ef4444' : '#9ca3af';
  const ring =
    score >= 70
      ? 'border-emerald-500'
      : score >= 50
      ? 'border-amber-500'
      : score >= 30
      ? 'border-red-500'
      : 'border-gray-300 dark:border-gray-600';
  return (
    <div
      className={cn('flex flex-shrink-0 items-center justify-center rounded-full border-2', ring)}
      style={{ width: size, height: size }}
    >
      <span className="text-xs font-bold" style={{ color }}>
        {Math.round(score)}
      </span>
    </div>
  );
}

function DifficultyDots({ difficulty }: { difficulty: number }) {
  const filled = Math.round((difficulty / 100) * 4);
  const color =
    difficulty < 30 ? 'bg-emerald-500' : difficulty < 60 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className={cn('h-2 w-2 rounded-full', i < filled ? color : 'bg-gray-200 dark:bg-gray-700')}
        />
      ))}
    </div>
  );
}

function TrendBadge({ trend, trendScore }: { trend: number; trendScore?: number }) {
  // Prefer Google Trends score when available
  const displayVal = trendScore != null && trendScore > 0 ? trendScore : Math.abs(trend);
  const isRising = trendScore != null ? trendScore > 30 : trend > 3;
  const isFalling = trendScore == null && trend < -3;

  if (isRising)
    return (
      <span className="flex items-center gap-0.5 text-sm font-medium text-emerald-600 dark:text-emerald-400">
        <TrendingUp className="h-3 w-3" />
        {Math.round(displayVal)}
      </span>
    );
  if (isFalling)
    return (
      <span className="flex items-center gap-0.5 text-sm font-medium text-red-500 dark:text-red-400">
        <TrendingDown className="h-3 w-3" />
        {Math.round(displayVal)}
      </span>
    );
  return (
    <span className="flex items-center gap-0.5 text-sm text-gray-400">
      <Minus className="h-3 w-3" />
      {Math.round(displayVal)}
    </span>
  );
}

function ClassBadge({ cls }: { cls: Classification }) {
  const cfg = CLS_CONFIG[cls] ?? CLS_CONFIG.medium;
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', cfg.bg)}>
      {cfg.label}
    </span>
  );
}

function StatCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: 'green' | 'amber' | 'red' }) {
  const accentCls = accent === 'green'
    ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/20'
    : accent === 'amber'
    ? 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/20'
    : accent === 'red'
    ? 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/20'
    : 'border-gray-100 bg-gray-50 dark:border-gray-700 dark:bg-gray-800';
  return (
    <div className={cn('rounded-lg border p-3', accentCls)}>
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-gray-900 dark:text-white">{value}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

// Tiny sparkline for Google Trends interest
function GoogleTrendsSparkline({ points }: { points: GoogleTrendWeekPoint[] }) {
  if (!points || points.length < 2) return null;
  return (
    <ResponsiveContainer width="100%" height={60}>
      <AreaChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <defs>
          <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" hide />
        <YAxis domain={[0, 100]} hide />
        <Tooltip
          formatter={(v: number) => [`${v}`, 'Interest']}
          labelFormatter={(d) => d.slice(0, 10)}
        />
        <Area
          type="monotone"
          dataKey="interest"
          stroke="#6366f1"
          strokeWidth={1.5}
          fill="url(#trendGradient)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Keyword Detail Drawer
// ---------------------------------------------------------------------------

function KeywordDrawer({
  term,
  onClose,
  onSelectRelated,
}: {
  term: string;
  onClose: () => void;
  onSelectRelated: (t: string) => void;
}) {
  const [detail, setDetail] = useState<KeywordDetail | null>(null);
  const [trend, setTrend] = useState<KeywordTrendResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setDetail(null);
    setTrend(null);
    Promise.all([getKeywordDetail(term), getKeywordTrend(term, 30)])
      .then(([d, t]) => {
        if (!alive) return;
        setDetail(d);
        setTrend(t);
      })
      .catch(() => {})
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => { alive = false; };
  }, [term]);

  const cls = (detail?.classification ?? 'medium') as Classification;
  const hasTrend = (trend?.trend_points?.length ?? 0) > 1;
  const hasGoogleTrend = (detail?.google_trend_points?.length ?? 0) > 1;
  const hasRealTrendData = detail != null && (detail.trend_score > 0 || detail.trend_growth !== 0);

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-white shadow-2xl dark:bg-gray-900">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div className="min-w-0 flex-1 pr-4">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <ClassBadge cls={cls} />
              {detail && (
                <span className="text-xs text-gray-500">
                  Opp {Math.round(detail.opportunity_score)} · Feas {Math.round(detail.feasibility_score)}
                </span>
              )}
              {hasRealTrendData && (
                <span className="flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                  <Activity className="h-3 w-3" />
                  Google Trends
                </span>
              )}
            </div>
            <h2 className="truncate text-xl font-bold text-gray-900 dark:text-white">{term}</h2>
          </div>
          <button onClick={onClose} className="ml-2 flex-shrink-0 rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-gray-800">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-14 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
              ))}
            </div>
          ) : !detail ? (
            <div className="flex h-48 items-center justify-center text-gray-400">
              No data available for "{term}"
            </div>
          ) : (
            <>
              {/* Core metrics */}
              <div className="grid grid-cols-3 gap-2">
                <StatCard label="Search Volume" value={fmtVolume(detail.search_volume)} />
                <StatCard label="Difficulty" value={`${Math.round(detail.difficulty)}/100`} />
                <StatCard label="Opp. Score" value={String(Math.round(detail.opportunity_score))}
                  accent={detail.opportunity_score >= 60 ? 'green' : detail.opportunity_score >= 40 ? 'amber' : undefined} />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <StatCard label="Feasibility" value={String(Math.round(detail.feasibility_score))}
                  accent={detail.feasibility_score >= 60 ? 'green' : undefined} />
                <StatCard
                  label="Ads Presence"
                  value={`${Math.round(detail.ads_presence * 100)}%`}
                  sub={detail.ads_presence > 0.5 ? 'High ad density' : 'Low ad density'}
                />
                <StatCard label="Tracked Apps" value={String(detail.apps_count)} />
              </div>

              {/* Google Trends signals panel */}
              {hasRealTrendData && (
                <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/20">
                  <div className="mb-3 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                    <h3 className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">Google Trends Signals</h3>
                    {detail.last_enriched && (
                      <span className="ml-auto text-xs text-indigo-400">
                        Updated {new Date(detail.last_enriched).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <p className="text-xs text-indigo-500">Interest</p>
                      <p className="font-bold text-indigo-700 dark:text-indigo-200">
                        {Math.round(detail.trend_score)}/100
                      </p>
                      <p className="text-xs text-indigo-400">{trendScoreLabel(detail.trend_score)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-indigo-500">90-day Growth</p>
                      <p className={cn('font-bold', trendGrowthColor(detail.trend_growth))}>
                        {detail.trend_growth > 0 ? '+' : ''}{Math.round(detail.trend_growth)}%
                      </p>
                      <p className="text-xs text-indigo-400">vs prior period</p>
                    </div>
                    <div>
                      <p className="text-xs text-indigo-500">Momentum</p>
                      <p className={cn('font-bold', trendGrowthColor(detail.trend_velocity))}>
                        {detail.trend_velocity > 0 ? '+' : ''}{Math.round(detail.trend_velocity)}%
                      </p>
                      <p className="text-xs text-indigo-400">last week vs avg</p>
                    </div>
                  </div>
                  {/* Google Trends sparkline */}
                  {hasGoogleTrend && (
                    <div className="mt-3">
                      <p className="mb-1 text-xs text-indigo-500">Interest Over Time (12 weeks)</p>
                      <GoogleTrendsSparkline points={detail.google_trend_points} />
                    </div>
                  )}
                </div>
              )}

              {/* Market dominance */}
              {detail.dominance_score > 0 && (
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                      Market Dominance
                    </span>
                    <span className={cn(
                      'text-xs font-bold',
                      detail.dominance_score >= 80 ? 'text-red-500' :
                      detail.dominance_score >= 50 ? 'text-amber-500' : 'text-emerald-600'
                    )}>
                      {Math.round(detail.dominance_score)}/100
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        detail.dominance_score >= 80 ? 'bg-red-500' :
                        detail.dominance_score >= 50 ? 'bg-amber-500' : 'bg-emerald-500'
                      )}
                      style={{ width: `${detail.dominance_score}%` }}
                    />
                  </div>
                  <p className="mt-1 text-xs text-gray-400">
                    {detail.dominance_score >= 80
                      ? 'Giant player dominates — very hard to enter'
                      : detail.dominance_score >= 50
                      ? 'Established player — requires strong differentiation'
                      : 'No dominant player — good entry opportunity'}
                  </p>
                </div>
              )}

              {/* Market fragmentation */}
              <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                    Market Fragmentation
                  </span>
                  <span className="text-xs font-bold text-gray-900 dark:text-white">
                    {Math.round(detail.market_fragmentation * 100)}%
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                  <div
                    className={cn(
                      'h-full rounded-full',
                      detail.market_fragmentation > 0.6 ? 'bg-emerald-500' :
                      detail.market_fragmentation > 0.3 ? 'bg-amber-500' : 'bg-red-500'
                    )}
                    style={{ width: `${detail.market_fragmentation * 100}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-gray-400">
                  {detail.market_fragmentation > 0.6
                    ? 'Fragmented — no single dominant player'
                    : detail.market_fragmentation > 0.3
                    ? 'Moderate concentration'
                    : 'Concentrated — one app dominates'}
                </p>
              </div>

              {/* DataForSEO signals (when available) */}
              {(detail.cpc > 0 || detail.competition_score > 0) && (
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
                  <p className="mb-2 text-xs font-semibold text-gray-600 dark:text-gray-400">
                    Search Ad Intelligence
                  </p>
                  <div className="flex gap-6">
                    {detail.cpc > 0 && (
                      <div>
                        <p className="text-xs text-gray-500">Avg CPC</p>
                        <p className="font-bold text-gray-900 dark:text-white">${detail.cpc.toFixed(2)}</p>
                      </div>
                    )}
                    {detail.competition_score > 0 && (
                      <div>
                        <p className="text-xs text-gray-500">Ad Competition</p>
                        <p className="font-bold text-gray-900 dark:text-white">{Math.round(detail.competition_score)}/100</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* App Store position trend chart */}
              {hasTrend && (
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
                    App Store Ranking Position (30 days)
                  </h3>
                  <ResponsiveContainer width="100%" height={120}>
                    <LineChart data={trend!.trend_points} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(d) => d.slice(5)} />
                      <YAxis reversed domain={[1, 20]} tick={{ fontSize: 9 }} />
                      <Tooltip formatter={(v: number) => [`#${v.toFixed(1)}`, 'Avg Position']} labelFormatter={(l) => l} />
                      <Line type="monotone" dataKey="avg_position" stroke="#6366f1" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="mt-1 text-xs text-center text-gray-400">Lower = higher ranking</p>
                </div>
              )}

              {/* Ad intensity chart */}
              {hasTrend && (
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Ad Intensity Over Time
                  </h3>
                  <ResponsiveContainer width="100%" height={80}>
                    <BarChart data={trend!.trend_points} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                      <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(d) => d.slice(5)} />
                      <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                      <Tooltip formatter={(v: number) => [`${Math.round(v * 100)}%`, 'Sponsored']} />
                      <Bar dataKey="sponsored_ratio" fill="#f97316" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Top competing apps */}
              {detail.top_competitors.length > 0 && (
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Top Competing Apps
                  </h3>
                  <div className="space-y-2">
                    {detail.top_competitors.slice(0, 10).map((comp) => (
                      <div
                        key={`${comp.app_id}-${comp.position}`}
                        className="flex items-center gap-3 rounded-lg bg-gray-50 p-2.5 dark:bg-gray-800"
                      >
                        {comp.icon_url ? (
                          <img src={comp.icon_url} alt="" className="h-8 w-8 flex-shrink-0 rounded-xl" />
                        ) : (
                          <div className="h-8 w-8 flex-shrink-0 rounded-xl bg-gray-200 dark:bg-gray-700" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                            {comp.app_name}
                          </p>
                          <p className="truncate text-xs text-gray-500">{comp.developer ?? '—'}</p>
                        </div>
                        <div className="flex flex-shrink-0 items-center gap-2 text-right">
                          <span className="text-sm font-bold text-gray-700 dark:text-gray-300">
                            #{comp.position}
                          </span>
                          {comp.is_sponsored && (
                            <span className="rounded-full bg-orange-100 px-1.5 py-0.5 text-xs text-orange-600 dark:bg-orange-950 dark:text-orange-400">
                              Ad
                            </span>
                          )}
                          {comp.reviews != null && (
                            <span className="text-xs text-gray-400">{fmtReviews(comp.reviews)}</span>
                          )}
                          {comp.rating != null && (
                            <span className="text-xs text-amber-500">★{comp.rating.toFixed(1)}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Feature gaps */}
              {detail.feature_gap_count > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/20">
                  <p className="text-sm text-amber-700 dark:text-amber-400">
                    <span className="font-semibold">{detail.feature_gap_count}</span> user feature requests
                    across competing apps — clear differentiation opportunity.
                  </p>
                </div>
              )}

              {/* Related keywords */}
              {detail.related_keywords.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Related Keywords
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {detail.related_keywords.map((kw) => (
                      <button
                        key={kw}
                        onClick={() => onSelectRelated(kw)}
                        className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 transition-colors hover:bg-indigo-100 dark:bg-indigo-950 dark:text-indigo-300 dark:hover:bg-indigo-900"
                      >
                        {kw}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {detail.last_scanned && (
                <p className="text-xs text-gray-400">
                  Last App Store scan: {new Date(detail.last_scanned).toLocaleString()}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sort control
// ---------------------------------------------------------------------------

type SortKey =
  | 'opportunity_score'
  | 'feasibility_score'
  | 'search_volume'
  | 'difficulty'
  | 'trend'
  | 'trend_score'
  | 'trend_growth'
  | 'apps_count'
  | 'dominance_score';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'opportunity_score', label: 'Opportunity' },
  { key: 'feasibility_score', label: 'Feasibility' },
  { key: 'trend_score', label: 'Trending' },
  { key: 'trend_growth', label: 'Growth' },
  { key: 'search_volume', label: 'Volume' },
  { key: 'difficulty', label: 'Difficulty' },
  { key: 'apps_count', label: 'Competition' },
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function KeywordsClient() {
  const [data, setData] = useState<KeywordListResponse>({ keywords: [], total: 0, skip: 0, limit: 50 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [classification, setClassification] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortKey>('opportunity_score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);
  const [selectedTerm, setSelectedTerm] = useState<string | null>(null);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const limit = 50;

  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchData = useCallback(
    (opts: {
      search?: string;
      classification?: string;
      sortBy?: SortKey;
      sortOrder?: 'asc' | 'desc';
      page?: number;
    }) => {
      setLoading(true);
      const skip = (opts.page ?? 0) * limit;
      getKeywordsEnhanced({
        search: opts.search ?? '',
        classification: opts.classification ?? '',
        sort_by: opts.sortBy ?? 'opportunity_score',
        sort_order: opts.sortOrder ?? 'desc',
        skip,
        limit,
      })
        .then((r) => setData(r))
        .catch(() => setData({ keywords: [], total: 0, skip: 0, limit }))
        .finally(() => setLoading(false));
    },
    []
  );

  useEffect(() => {
    fetchData({ search, classification, sortBy, sortOrder, page });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearchChange = (val: string) => {
    setSearch(val);
    setPage(0);
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    searchDebounce.current = setTimeout(() => {
      fetchData({ search: val, classification, sortBy, sortOrder, page: 0 });
    }, 350);
  };

  const handleClassification = (cls: string) => {
    const next = cls === classification ? '' : cls;
    setClassification(next);
    setPage(0);
    fetchData({ search, classification: next, sortBy, sortOrder, page: 0 });
  };

  const handleSort = (key: SortKey) => {
    const nextOrder = sortBy === key && sortOrder === 'desc' ? 'asc' : 'desc';
    setSortBy(key);
    setSortOrder(nextOrder);
    setPage(0);
    fetchData({ search, classification, sortBy: key, sortOrder: nextOrder, page: 0 });
  };

  const handlePage = (delta: number) => {
    const next = page + delta;
    setPage(next);
    fetchData({ search, classification, sortBy, sortOrder, page: next });
  };

  const handleRunPipeline = async () => {
    setRunningPipeline(true);
    try {
      await triggerKeywordPipeline();
      // Refresh after a short delay to pick up early results
      setTimeout(() => {
        fetchData({ search, classification, sortBy, sortOrder, page });
        setRunningPipeline(false);
      }, 3000);
    } catch {
      setRunningPipeline(false);
    }
  };

  const keywords = data.keywords ?? [];
  const totalPages = Math.ceil(data.total / limit);

  const easyCount = keywords.filter((k) => k.classification === 'easy').length;
  const risingCount = keywords.filter((k) => (k.trend_score ?? 0) > 30 || k.trend > 3).length;
  const enrichedCount = keywords.filter((k) => (k.trend_score ?? 0) > 0).length;
  const avgDiff = keywords.length
    ? Math.round(keywords.reduce((s, k) => s + k.difficulty, 0) / keywords.length)
    : 0;

  return (
    <ErrorBoundary>
      <AppShell>
        <div className="space-y-5">
          {/* Header */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Keywords</h1>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Real keyword intelligence — Google Trends + App Store signals + unified scoring
              </p>
            </div>
            <button
              onClick={handleRunPipeline}
              disabled={runningPipeline}
              className={cn(
                'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                runningPipeline
                  ? 'bg-indigo-100 text-indigo-400 cursor-not-allowed dark:bg-indigo-950 dark:text-indigo-600'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700'
              )}
            >
              <RefreshCw className={cn('h-4 w-4', runningPipeline && 'animate-spin')} />
              {runningPipeline ? 'Running…' : 'Refresh Intelligence'}
            </button>
          </div>

          {/* Stats strip */}
          {!loading && keywords.length > 0 && (
            <div className="flex flex-wrap gap-3">
              <div className="rounded-lg border border-gray-200 bg-white px-4 py-2.5 dark:border-gray-700 dark:bg-gray-900">
                <p className="text-xs text-gray-500">Total Keywords</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">{data.total}</p>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 dark:border-emerald-800 dark:bg-emerald-950/30">
                <p className="text-xs text-emerald-600 dark:text-emerald-400">Easy Wins</p>
                <p className="text-xl font-bold text-emerald-700 dark:text-emerald-300">{easyCount}</p>
              </div>
              <div className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2.5 dark:border-indigo-800 dark:bg-indigo-950/30">
                <p className="text-xs text-indigo-600 dark:text-indigo-400">Rising Demand</p>
                <p className="text-xl font-bold text-indigo-700 dark:text-indigo-300">{risingCount}</p>
              </div>
              {enrichedCount > 0 && (
                <div className="rounded-lg border border-violet-200 bg-violet-50 px-4 py-2.5 dark:border-violet-800 dark:bg-violet-950/30">
                  <p className="text-xs text-violet-600 dark:text-violet-400">Google Trends Data</p>
                  <p className="text-xl font-bold text-violet-700 dark:text-violet-300">{enrichedCount}</p>
                </div>
              )}
              <div className="rounded-lg border border-gray-200 bg-white px-4 py-2.5 dark:border-gray-700 dark:bg-gray-900">
                <p className="text-xs text-gray-500">Avg Difficulty</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">{avgDiff}</p>
              </div>
            </div>
          )}

          {/* Search + classification filters */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative max-w-xs flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search keywords…"
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-10 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
              {search && (
                <button
                  onClick={() => handleSearchChange('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            <div className="flex flex-wrap gap-1.5">
              {(['', 'easy', 'medium', 'hard', 'impossible'] as const).map((cls) => {
                const label = cls === '' ? 'All' : CLS_CONFIG[cls as Classification].label;
                const active = classification === cls;
                return (
                  <button
                    key={cls}
                    onClick={() => handleClassification(cls)}
                    className={cn(
                      'rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                      active
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Sort controls */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Sort by:</span>
            {SORT_OPTIONS.map((opt) => {
              const active = sortBy === opt.key;
              return (
                <button
                  key={opt.key}
                  onClick={() => handleSort(opt.key)}
                  className={cn(
                    'flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                    active
                      ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                      : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
                  )}
                >
                  {opt.label}
                  {active &&
                    (sortOrder === 'desc' ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronUp className="h-3 w-3" />
                    ))}
                </button>
              );
            })}
          </div>

          {/* Table */}
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50 dark:border-gray-700 dark:bg-gray-800/50">
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Keyword
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Volume
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Difficulty
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Trend
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Opp.
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Feasibility
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Apps
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Class
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                  {loading ? (
                    Array.from({ length: 10 }).map((_, i) => (
                      <tr key={i}>
                        <td colSpan={8} className="px-4 py-3">
                          <div className="h-5 w-full animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
                        </td>
                      </tr>
                    ))
                  ) : keywords.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-gray-400">
                        <BarChart3 className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
                        <p>
                          {search || classification
                            ? 'No keywords match your filters.'
                            : 'No keywords yet — click "Refresh Intelligence" to discover keywords.'}
                        </p>
                      </td>
                    </tr>
                  ) : (
                    keywords.map((kw) => (
                      <tr
                        key={kw.id}
                        onClick={() => setSelectedTerm(kw.term)}
                        className={cn(
                          'cursor-pointer transition-colors hover:bg-indigo-50/50 dark:hover:bg-indigo-950/20',
                          selectedTerm === kw.term && 'bg-indigo-50 dark:bg-indigo-950/30'
                        )}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900 dark:text-white">{kw.term}</span>
                            {kw.trend_score > 50 && (
                              <span title="High Google Trends interest">
                                <Activity className="h-3 w-3 text-indigo-400" />
                              </span>
                            )}
                            {kw.trend_growth > 20 && (
                              <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
                                +{Math.round(kw.trend_growth)}%
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">
                          {fmtVolume(kw.search_volume)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex justify-center">
                            <DifficultyDots difficulty={kw.difficulty} />
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <TrendBadge
                            trend={kw.trend}
                            trendScore={kw.trend_score > 0 ? kw.trend_score : undefined}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex justify-center">
                            <ScoreRing score={kw.opportunity_score} size={36} />
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex justify-center">
                            <ScoreRing score={kw.feasibility_score} size={36} />
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">
                          {kw.apps_count}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex justify-center">
                            <ClassBadge cls={kw.classification as Classification} />
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data.total > limit && (
              <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3 dark:border-gray-700">
                <span className="text-xs text-gray-500">
                  {data.skip + 1}–{Math.min(data.skip + limit, data.total)} of {data.total}
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={page === 0}
                    onClick={() => handlePage(-1)}
                    className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
                  >
                    Previous
                  </button>
                  <button
                    disabled={page >= totalPages - 1}
                    onClick={() => handlePage(1)}
                    className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </AppShell>

      {/* Detail drawer */}
      {selectedTerm && (
        <KeywordDrawer
          term={selectedTerm}
          onClose={() => setSelectedTerm(null)}
          onSelectRelated={(t) => {
            setSelectedTerm(t);
            handleSearchChange(t);
          }}
        />
      )}
    </ErrorBoundary>
  );
}
