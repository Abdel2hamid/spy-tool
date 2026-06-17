'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
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
  ChevronLeft,
  ChevronRight,
  BarChart3,
  Zap,
  Shield,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Activity,
  Download,
  Target,
  Flame,
  Eye,
  Crown,
  Filter,
} from 'lucide-react';
import { toCSV, downloadCSV } from '@/lib/csv-export';
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
    ring: 'ring-emerald-500/20',
  },
  medium: {
    label: 'Medium',
    bg: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
    icon: Shield,
    dot: 'bg-amber-500',
    ring: 'ring-amber-500/20',
  },
  hard: {
    label: 'Hard',
    bg: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
    icon: AlertTriangle,
    dot: 'bg-red-500',
    ring: 'ring-red-500/20',
  },
  impossible: {
    label: 'Impossible',
    bg: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500',
    icon: XCircle,
    dot: 'bg-gray-400',
    ring: 'ring-gray-400/20',
  },
} as const;

type Classification = keyof typeof CLS_CONFIG;

// ---------------------------------------------------------------------------
// View presets — each combines a filter + sort for one-click access
// ---------------------------------------------------------------------------

type ViewKey = 'all' | 'quick_wins' | 'rising' | 'high_value' | 'low_competition';

interface ViewPreset {
  label: string;
  icon: typeof Zap;
  desc: string;
  classification: string;
  sortBy: SortKey;
  sortOrder: 'asc' | 'desc';
  /** Client-side filter applied on top of backend results */
  clientFilter?: (kw: KeywordListItem) => boolean;
}

const VIEW_PRESETS: Record<ViewKey, ViewPreset> = {
  all: {
    label: 'All Keywords',
    icon: BarChart3,
    desc: 'Complete keyword database',
    classification: '',
    sortBy: 'opportunity_score',
    sortOrder: 'desc',
  },
  quick_wins: {
    label: 'Quick Wins',
    icon: Zap,
    desc: 'Low difficulty, high opportunity',
    classification: 'easy',
    sortBy: 'opportunity_score',
    sortOrder: 'desc',
  },
  rising: {
    label: 'Rising',
    icon: Flame,
    desc: 'Trending up on Google Trends',
    classification: '',
    sortBy: 'trend_score',
    sortOrder: 'desc',
    clientFilter: (kw) => (kw.trend_score ?? 0) > 20 || kw.trend_growth > 10,
  },
  high_value: {
    label: 'High Value',
    icon: Crown,
    desc: 'High volume keywords worth targeting',
    classification: '',
    sortBy: 'volume_score',
    sortOrder: 'desc',
    clientFilter: (kw) => (kw.volume_score ?? 0) >= 40,
  },
  low_competition: {
    label: 'Low Competition',
    icon: Target,
    desc: 'Few brands, fragmented market',
    classification: '',
    sortBy: 'difficulty_v2',
    sortOrder: 'asc',
    clientFilter: (kw) => (kw.brand_count ?? 0) <= 2 && (kw.difficulty_v2 || kw.difficulty) <= 40,
  },
};

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

/** Estimate daily downloads range from volume_score using exponential curve. */
function estDownloadsRange(volumeScore: number): string {
  if (volumeScore <= 0) return '0';
  const dailySearches = 10 * Math.pow(1.055, volumeScore);
  const low = Math.round(dailySearches * 0.06 * 0.3);
  const high = Math.round(dailySearches * 0.35 * 0.3);
  if (high <= 0) return '0';
  const fmt = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n));
  return `${fmt(low)} – ${fmt(high)}`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** SVG donut ring — circular progress indicator. */
function DonutRing({
  value,
  max = 100,
  size = 40,
  invert = false,
}: {
  value: number;
  max?: number;
  size?: number;
  invert?: boolean;
}) {
  const pct = Math.min(Math.max(value / max, 0), 1);
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);

  const effective = invert ? 100 - value : value;
  const strokeColor =
    effective >= 60 ? '#22c55e' : effective >= 35 ? '#f59e0b' : '#ef4444';
  const textColor =
    effective >= 60 ? '#16a34a' : effective >= 35 ? '#d97706' : '#dc2626';

  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={3}
          className="text-gray-200 dark:text-gray-700"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={strokeColor}
          strokeWidth={3}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span
        className="absolute inset-0 flex items-center justify-center text-xs font-bold"
        style={{ color: textColor }}
      >
        {Math.round(value)}
      </span>
    </div>
  );
}

function ScoreRing({ score, size = 40 }: { score: number; size?: number }) {
  return <DonutRing value={score} size={size} />;
}

/** Horizontal score bar with color gradient */
function ScoreBar({ value, invert = false, label }: { value: number; invert?: boolean; label?: string }) {
  const effective = invert ? 100 - value : value;
  const color =
    effective >= 60
      ? 'bg-emerald-500'
      : effective >= 35
      ? 'bg-amber-500'
      : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
          <div
            className={cn('h-full rounded-full transition-all', color)}
            style={{ width: `${Math.min(value, 100)}%` }}
          />
        </div>
      </div>
      <span className="w-7 text-right text-xs font-semibold tabular-nums text-gray-700 dark:text-gray-300">
        {Math.round(value)}
      </span>
    </div>
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

function TrendBadge({ trend, trendScore }: { trend: number; trendScore?: number }) {
  const displayVal = trendScore != null && trendScore > 0 ? trendScore : Math.abs(trend);
  const isRising = trendScore != null ? trendScore > 30 : trend > 3;
  const isFalling = trendScore == null && trend < -3;

  if (isRising)
    return (
      <span className="flex items-center gap-0.5 text-sm font-medium text-emerald-600 dark:text-emerald-400">
        <TrendingUp className="h-3.5 w-3.5" />
        {Math.round(displayVal)}
      </span>
    );
  if (isFalling)
    return (
      <span className="flex items-center gap-0.5 text-sm font-medium text-red-500 dark:text-red-400">
        <TrendingDown className="h-3.5 w-3.5" />
        {Math.round(displayVal)}
      </span>
    );
  return (
    <span className="flex items-center gap-0.5 text-sm text-gray-400">
      <Minus className="h-3.5 w-3.5" />
      {Math.round(displayVal)}
    </span>
  );
}

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: 'green' | 'amber' | 'red';
}) {
  const accentCls =
    accent === 'green'
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
    return () => {
      alive = false;
    };
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
                  Opp {Math.round(detail.opportunity_score)} · Feas{' '}
                  {Math.round(detail.feasibility_score)}
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
          <button
            onClick={onClose}
            className="ml-2 flex-shrink-0 rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="h-14 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800"
                />
              ))}
            </div>
          ) : !detail ? (
            <div className="flex h-48 items-center justify-center text-gray-400">
              No data available for &ldquo;{term}&rdquo;
            </div>
          ) : (
            <>
              {/* Core metrics (V2 scores) */}
              <div className="grid grid-cols-3 gap-2">
                <StatCard
                  label="Volume Score"
                  value={`${Math.round(detail.volume_score || 0)}`}
                  sub={
                    detail.autocomplete_rank > 0
                      ? `AC rank #${detail.autocomplete_rank}`
                      : undefined
                  }
                  accent={detail.volume_score >= 50 ? 'green' : undefined}
                />
                <StatCard
                  label="Difficulty"
                  value={`${Math.round(detail.difficulty_v2 || detail.difficulty || 0)}`}
                  accent={
                    (detail.difficulty_v2 || detail.difficulty || 0) <= 40
                      ? 'green'
                      : (detail.difficulty_v2 || detail.difficulty || 0) >= 70
                      ? undefined
                      : 'amber'
                  }
                />
                <StatCard
                  label="Opp. Score"
                  value={String(Math.round(detail.opportunity_score))}
                  accent={
                    detail.opportunity_score >= 60
                      ? 'green'
                      : detail.opportunity_score >= 40
                      ? 'amber'
                      : undefined
                  }
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <StatCard
                  label="Feasibility"
                  value={String(Math.round(detail.feasibility_score))}
                  accent={detail.feasibility_score >= 60 ? 'green' : undefined}
                />
                <StatCard label="Tracked Apps" value={String(detail.apps_count)} />
                <StatCard
                  label="Brands in Top 10"
                  value={`${detail.brand_count || 0}`}
                  accent={(detail.brand_count || 0) <= 2 ? 'green' : undefined}
                />
              </div>

              {/* Difficulty V2 breakdown */}
              {(detail.difficulty_v2 || 0) > 0 && (
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800">
                  <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Difficulty Breakdown
                  </h3>
                  <div className="space-y-2">
                    {[
                      {
                        label: 'Incumbent Strength',
                        value: detail.incumbent_strength || 0,
                        max: 35,
                        desc: 'Review power of top 10 apps',
                      },
                      {
                        label: 'Title Saturation',
                        value: detail.title_saturation || 0,
                        max: 20,
                        desc: 'Keyword in competitor titles',
                      },
                      {
                        label: 'Brand Dominance',
                        value: detail.brand_dominance || 0,
                        max: 20,
                        desc: 'Big brands in top 10',
                      },
                      {
                        label: 'Market Concentration',
                        value: detail.market_concentration || 0,
                        max: 15,
                        desc: 'HHI concentration index',
                      },
                    ].map(({ label, value, max, desc }) => (
                      <div key={label}>
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-600 dark:text-gray-400" title={desc}>
                            {label}
                          </span>
                          <span className="font-medium text-gray-900 dark:text-white">
                            {Math.round(value)}/{max}
                          </span>
                        </div>
                        <div className="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                          <div
                            className="h-full rounded-full bg-indigo-500"
                            style={{ width: `${Math.min((value / max) * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  {detail.top_player && (
                    <p className="mt-2 text-xs text-gray-500">
                      #1 app:{' '}
                      <span className="font-medium text-gray-700 dark:text-gray-300">
                        {detail.top_player}
                      </span>
                    </p>
                  )}
                </div>
              )}

              {/* Google Trends signals panel */}
              {hasRealTrendData && (
                <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/20">
                  <div className="mb-3 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                    <h3 className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">
                      Google Trends Signals
                    </h3>
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
                      <p className="text-xs text-indigo-400">
                        {trendScoreLabel(detail.trend_score)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-indigo-500">90-day Growth</p>
                      <p className={cn('font-bold', trendGrowthColor(detail.trend_growth))}>
                        {detail.trend_growth > 0 ? '+' : ''}
                        {Math.round(detail.trend_growth)}%
                      </p>
                      <p className="text-xs text-indigo-400">vs prior period</p>
                    </div>
                    <div>
                      <p className="text-xs text-indigo-500">Momentum</p>
                      <p className={cn('font-bold', trendGrowthColor(detail.trend_velocity))}>
                        {detail.trend_velocity > 0 ? '+' : ''}
                        {Math.round(detail.trend_velocity)}%
                      </p>
                      <p className="text-xs text-indigo-400">last week vs avg</p>
                    </div>
                  </div>
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
                    <span
                      className={cn(
                        'text-xs font-bold',
                        detail.dominance_score >= 80
                          ? 'text-red-500'
                          : detail.dominance_score >= 50
                          ? 'text-amber-500'
                          : 'text-emerald-600',
                      )}
                    >
                      {Math.round(detail.dominance_score)}/100
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        detail.dominance_score >= 80
                          ? 'bg-red-500'
                          : detail.dominance_score >= 50
                          ? 'bg-amber-500'
                          : 'bg-emerald-500',
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
                      detail.market_fragmentation > 0.6
                        ? 'bg-emerald-500'
                        : detail.market_fragmentation > 0.3
                        ? 'bg-amber-500'
                        : 'bg-red-500',
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

              {/* DataForSEO signals */}
              {(detail.cpc > 0 || detail.competition_score > 0) && (
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
                  <p className="mb-2 text-xs font-semibold text-gray-600 dark:text-gray-400">
                    Search Ad Intelligence
                  </p>
                  <div className="flex gap-6">
                    {detail.cpc > 0 && (
                      <div>
                        <p className="text-xs text-gray-500">Avg CPC</p>
                        <p className="font-bold text-gray-900 dark:text-white">
                          ${detail.cpc.toFixed(2)}
                        </p>
                      </div>
                    )}
                    {detail.competition_score > 0 && (
                      <div>
                        <p className="text-xs text-gray-500">Ad Competition</p>
                        <p className="font-bold text-gray-900 dark:text-white">
                          {Math.round(detail.competition_score)}/100
                        </p>
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
                    <LineChart
                      data={trend!.trend_points}
                      margin={{ top: 4, right: 4, bottom: 4, left: -20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 9 }}
                        tickFormatter={(d) => d.slice(5)}
                      />
                      <YAxis reversed domain={[1, 20]} tick={{ fontSize: 9 }} />
                      <Tooltip
                        formatter={(v: number) => [`#${v.toFixed(1)}`, 'Avg Position']}
                        labelFormatter={(l) => l}
                      />
                      <Line
                        type="monotone"
                        dataKey="avg_position"
                        stroke="#6366f1"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="mt-1 text-center text-xs text-gray-400">
                    Lower = higher ranking
                  </p>
                </div>
              )}

              {/* Ad intensity chart */}
              {hasTrend && (
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Ad Intensity Over Time
                  </h3>
                  <ResponsiveContainer width="100%" height={80}>
                    <BarChart
                      data={trend!.trend_points}
                      margin={{ top: 4, right: 4, bottom: 4, left: -20 }}
                    >
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 9 }}
                        tickFormatter={(d) => d.slice(5)}
                      />
                      <YAxis
                        tick={{ fontSize: 9 }}
                        tickFormatter={(v) => `${Math.round(v * 100)}%`}
                      />
                      <Tooltip
                        formatter={(v: number) => [`${Math.round(v * 100)}%`, 'Sponsored']}
                      />
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
                          <img
                            src={comp.icon_url}
                            alt=""
                            className="h-8 w-8 flex-shrink-0 rounded-xl"
                          />
                        ) : (
                          <div className="h-8 w-8 flex-shrink-0 rounded-xl bg-gray-200 dark:bg-gray-700" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                            {comp.app_name}
                          </p>
                          <p className="truncate text-xs text-gray-500">
                            {comp.developer ?? '—'}
                          </p>
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
                            <span className="text-xs text-gray-400">
                              {fmtReviews(comp.reviews)}
                            </span>
                          )}
                          {comp.rating != null && (
                            <span className="text-xs text-amber-500">
                              ★{comp.rating.toFixed(1)}
                            </span>
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
                    <span className="font-semibold">{detail.feature_gap_count}</span> user
                    feature requests across competing apps — clear differentiation opportunity.
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
  | 'dominance_score'
  | 'volume_score'
  | 'difficulty_v2';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'opportunity_score', label: 'Opportunity' },
  { key: 'volume_score', label: 'Volume' },
  { key: 'difficulty_v2', label: 'Difficulty' },
  { key: 'feasibility_score', label: 'Feasibility' },
  { key: 'trend_score', label: 'Trending' },
  { key: 'trend_growth', label: 'Growth' },
  { key: 'apps_count', label: 'Competition' },
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function KeywordsClient() {
  const [data, setData] = useState<KeywordListResponse>({
    keywords: [],
    total: 0,
    skip: 0,
    limit: 50,
  });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [classification, setClassification] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortKey>('opportunity_score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);
  const [selectedTerm, setSelectedTerm] = useState<string | null>(null);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [activeView, setActiveView] = useState<ViewKey>('all');
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
    [],
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

  const handleViewChange = (view: ViewKey) => {
    setActiveView(view);
    const preset = VIEW_PRESETS[view];
    setClassification(preset.classification);
    setSortBy(preset.sortBy);
    setSortOrder(preset.sortOrder);
    setPage(0);
    fetchData({
      search,
      classification: preset.classification,
      sortBy: preset.sortBy,
      sortOrder: preset.sortOrder,
      page: 0,
    });
  };

  const handleRunPipeline = async () => {
    setRunningPipeline(true);
    try {
      await triggerKeywordPipeline();
      setTimeout(() => {
        fetchData({ search, classification, sortBy, sortOrder, page });
        setRunningPipeline(false);
      }, 3000);
    } catch {
      setRunningPipeline(false);
    }
  };

  // Apply client-side view filter on top of server results
  const rawKeywords = data.keywords ?? [];
  const viewPreset = VIEW_PRESETS[activeView];
  const keywords = viewPreset.clientFilter
    ? rawKeywords.filter(viewPreset.clientFilter)
    : rawKeywords;
  const totalPages = Math.ceil(data.total / limit);

  // Summary stats — computed from current page
  const stats = useMemo(() => {
    const kws = rawKeywords;
    const easy = kws.filter((k) => k.classification === 'easy').length;
    const medium = kws.filter((k) => k.classification === 'medium').length;
    const hard = kws.filter((k) => k.classification === 'hard').length;
    const rising = kws.filter((k) => (k.trend_score ?? 0) > 30 || k.trend > 3).length;
    const enriched = kws.filter((k) => (k.trend_score ?? 0) > 0).length;
    const avgOpp = kws.length
      ? Math.round(kws.reduce((s, k) => s + k.opportunity_score, 0) / kws.length)
      : 0;
    const avgDiff = kws.length
      ? Math.round(
          kws.reduce((s, k) => s + (k.difficulty_v2 || k.difficulty), 0) / kws.length,
        )
      : 0;
    const highValue = kws.filter((k) => (k.volume_score ?? 0) >= 40).length;
    return { easy, medium, hard, rising, enriched, avgOpp, avgDiff, highValue };
  }, [rawKeywords]);

  const handleExportCSV = () => {
    if (!keywords.length) return;
    const csv = toCSV(
      keywords.map((k) => ({
        keyword: k.term,
        classification: k.classification,
        volume_score: k.volume_score ?? k.search_volume,
        difficulty: k.difficulty_v2 ?? k.difficulty,
        opportunity_score: k.opportunity_score,
        feasibility_score: k.feasibility_score,
        trend_score: k.trend_score,
        trend_growth: k.trend_growth,
        search_volume: k.search_volume,
        top_player: k.top_player || '',
        brands: k.brand_count ?? '',
        apps_count: k.apps_count,
      })),
      [
        { key: 'keyword', label: 'Keyword' },
        { key: 'classification', label: 'Classification' },
        { key: 'volume_score', label: 'Volume Score' },
        { key: 'difficulty', label: 'Difficulty' },
        { key: 'opportunity_score', label: 'Opportunity Score' },
        { key: 'feasibility_score', label: 'Feasibility Score' },
        { key: 'trend_score', label: 'Google Trends Score' },
        { key: 'trend_growth', label: 'Trend Growth %' },
        { key: 'search_volume', label: 'Search Volume' },
        { key: 'top_player', label: 'Top Player' },
        { key: 'brands', label: 'Brands in Top 10' },
        { key: 'apps_count', label: 'Competing Apps' },
      ],
    );
    downloadCSV(csv, `keywords-${activeView}-${new Date().toISOString().slice(0, 10)}.csv`);
  };

  return (
    <ErrorBoundary>
      <AppShell>
        <div className="space-y-5">
          {/* ── Header ───────────────────────────────────────────── */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Keyword Intelligence
              </h1>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Discover, analyze, and track App Store keywords with multi-signal scoring
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                <Download className="h-4 w-4" />
                Export
              </button>
              <button
                onClick={handleRunPipeline}
                disabled={runningPipeline}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                  runningPipeline
                    ? 'cursor-not-allowed bg-indigo-100 text-indigo-400 dark:bg-indigo-950 dark:text-indigo-600'
                    : 'bg-indigo-600 text-white hover:bg-indigo-700',
                )}
              >
                <RefreshCw className={cn('h-4 w-4', runningPipeline && 'animate-spin')} />
                {runningPipeline ? 'Running...' : 'Refresh'}
              </button>
            </div>
          </div>

          {/* ── View Tabs ────────────────────────────────────────── */}
          <div className="flex gap-1 overflow-x-auto rounded-xl border border-gray-200 bg-gray-50 p-1 dark:border-gray-700 dark:bg-gray-800/50">
            {(Object.entries(VIEW_PRESETS) as [ViewKey, ViewPreset][]).map(([key, preset]) => {
              const Icon = preset.icon;
              const isActive = activeView === key;
              return (
                <button
                  key={key}
                  onClick={() => handleViewChange(key)}
                  className={cn(
                    'flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-all',
                    isActive
                      ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-900 dark:text-white'
                      : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {preset.label}
                </button>
              );
            })}
          </div>

          {/* ── Insight Cards ────────────────────────────────────── */}
          {!loading && rawKeywords.length > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
              <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
                    <BarChart3 className="h-4 w-4 text-gray-500" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Total</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{data.total}</p>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3 dark:border-emerald-800 dark:bg-emerald-950/20">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/40">
                    <Zap className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-xs text-emerald-600 dark:text-emerald-400">Easy Wins</p>
                    <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">
                      {stats.easy}
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-3 dark:border-indigo-800 dark:bg-indigo-950/20">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900/40">
                    <Flame className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div>
                    <p className="text-xs text-indigo-600 dark:text-indigo-400">Rising</p>
                    <p className="text-lg font-bold text-indigo-700 dark:text-indigo-300">
                      {stats.rising}
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-3 dark:border-violet-800 dark:bg-violet-950/20">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-900/40">
                    <Crown className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                  </div>
                  <div>
                    <p className="text-xs text-violet-600 dark:text-violet-400">High Value</p>
                    <p className="text-lg font-bold text-violet-700 dark:text-violet-300">
                      {stats.highValue}
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
                    <Target className="h-4 w-4 text-gray-500" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Avg Opp.</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">
                      {stats.avgOpp}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Search + Filters Toolbar ─────────────────────────── */}
          <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              {/* Search */}
              <div className="relative min-w-0 flex-1 lg:max-w-xs">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search keywords..."
                  value={search}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2 pl-10 pr-10 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:focus:bg-gray-800"
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

              {/* Classification pills */}
              <div className="flex items-center gap-1">
                <Filter className="mr-1 h-3.5 w-3.5 text-gray-400" />
                {(['', 'easy', 'medium', 'hard', 'impossible'] as const).map((cls) => {
                  const label =
                    cls === '' ? 'All' : CLS_CONFIG[cls as Classification].label;
                  const active = classification === cls;
                  const count =
                    cls === ''
                      ? null
                      : cls === 'easy'
                      ? stats.easy
                      : cls === 'medium'
                      ? stats.medium
                      : cls === 'hard'
                      ? stats.hard
                      : null;
                  return (
                    <button
                      key={cls}
                      onClick={() => {
                        handleClassification(cls);
                        setActiveView('all');
                      }}
                      className={cn(
                        'flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                        active
                          ? 'bg-indigo-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700',
                      )}
                    >
                      {label}
                      {count != null && count > 0 && (
                        <span
                          className={cn(
                            'ml-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none',
                            active
                              ? 'bg-indigo-500 text-white'
                              : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400',
                          )}
                        >
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Sort dropdown area */}
              <div className="flex flex-wrap items-center gap-1.5 lg:ml-auto">
                <span className="text-xs font-medium text-gray-400">Sort:</span>
                {SORT_OPTIONS.map((opt) => {
                  const active = sortBy === opt.key;
                  return (
                    <button
                      key={opt.key}
                      onClick={() => handleSort(opt.key)}
                      className={cn(
                        'flex items-center gap-0.5 rounded-md px-2 py-1 text-xs font-medium transition-colors',
                        active
                          ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                          : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white',
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
            </div>
          </div>

          {/* ── Table ────────────────────────────────────────────── */}
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50/80 dark:border-gray-700 dark:bg-gray-800/60">
                    <th className="sticky left-0 z-10 bg-gray-50/80 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:bg-gray-800/60 dark:text-gray-400">
                      Keyword
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Volume
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Difficulty
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Opportunity
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Trend
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Feasibility
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Top Player
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Brands
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {loading ? (
                    Array.from({ length: 12 }).map((_, i) => (
                      <tr key={i}>
                        <td colSpan={8} className="px-4 py-3.5">
                          <div className="h-5 w-full animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
                        </td>
                      </tr>
                    ))
                  ) : keywords.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-16 text-center text-gray-400">
                        <BarChart3 className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
                        <p className="text-sm font-medium text-gray-500">
                          {search || classification
                            ? 'No keywords match your filters'
                            : 'No keywords discovered yet'}
                        </p>
                        <p className="mt-1 text-xs text-gray-400">
                          {search || classification
                            ? 'Try adjusting your search or filters'
                            : 'Click "Refresh" to start discovering keywords'}
                        </p>
                      </td>
                    </tr>
                  ) : (
                    keywords.map((kw) => {
                      const diff = kw.difficulty_v2 || kw.difficulty || 0;
                      const vol = kw.volume_score || 0;
                      const cls = (kw.classification || 'medium') as Classification;
                      const cfg = CLS_CONFIG[cls] ?? CLS_CONFIG.medium;

                      return (
                        <tr
                          key={kw.id}
                          onClick={() => setSelectedTerm(kw.term)}
                          className={cn(
                            'group cursor-pointer transition-colors hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20',
                            selectedTerm === kw.term && 'bg-indigo-50 dark:bg-indigo-950/30',
                          )}
                        >
                          {/* Keyword */}
                          <td className="sticky left-0 z-10 bg-white px-4 py-3 group-hover:bg-indigo-50/40 dark:bg-gray-900 dark:group-hover:bg-indigo-950/20">
                            <div className="flex items-center gap-2.5">
                              <div
                                className={cn('h-2 w-2 flex-shrink-0 rounded-full', cfg.dot)}
                                title={cfg.label}
                              />
                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-medium text-gray-900 dark:text-white">
                                    {kw.term}
                                  </span>
                                  {kw.trend_growth > 20 && (
                                    <span className="rounded bg-emerald-100 px-1 py-0.5 text-[10px] font-semibold text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
                                      +{Math.round(kw.trend_growth)}%
                                    </span>
                                  )}
                                  {kw.trend_score > 50 && (
                                    <span title="High Google Trends interest">
                                      <Activity className="h-3 w-3 text-indigo-400" />
                                    </span>
                                  )}
                                </div>
                                <div className="mt-0.5 flex items-center gap-1.5">
                                  <ClassBadge cls={cls} />
                                  {kw.last_enriched && (
                                    <span className="text-[10px] text-gray-400">
                                      {(() => {
                                        const hrs = Math.round(
                                          (Date.now() -
                                            new Date(kw.last_enriched).getTime()) /
                                            3600000,
                                        );
                                        return hrs < 1
                                          ? 'just now'
                                          : hrs < 24
                                          ? `${hrs}h ago`
                                          : `${Math.round(hrs / 24)}d ago`;
                                      })()}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Volume */}
                          <td className="px-3 py-3">
                            <div className="flex justify-center">
                              <DonutRing value={vol} size={36} />
                            </div>
                          </td>

                          {/* Difficulty */}
                          <td className="px-3 py-3">
                            <div className="flex justify-center">
                              <DonutRing value={diff} size={36} invert />
                            </div>
                          </td>

                          {/* Opportunity */}
                          <td className="px-3 py-3">
                            <div className="flex justify-center">
                              <DonutRing value={kw.opportunity_score} size={36} />
                            </div>
                          </td>

                          {/* Trend */}
                          <td className="px-3 py-3">
                            <div className="flex justify-center">
                              <TrendBadge
                                trend={kw.trend}
                                trendScore={kw.trend_score}
                              />
                            </div>
                          </td>

                          {/* Feasibility */}
                          <td className="px-3 py-3">
                            <div className="flex justify-center">
                              <DonutRing value={kw.feasibility_score} size={36} />
                            </div>
                          </td>

                          {/* Top Player */}
                          <td className="max-w-[140px] px-3 py-3">
                            {kw.top_player ? (
                              <span
                                className="block truncate text-xs text-gray-600 dark:text-gray-400"
                                title={kw.top_player}
                              >
                                {kw.top_player}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-300 dark:text-gray-600">
                                —
                              </span>
                            )}
                          </td>

                          {/* Brands */}
                          <td className="px-3 py-3 text-center">
                            {(kw.brand_count || 0) > 0 ? (
                              <span
                                className={cn(
                                  'inline-flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold',
                                  kw.brand_count >= 4
                                    ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400'
                                    : kw.brand_count >= 2
                                    ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
                                    : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
                                )}
                              >
                                {kw.brand_count}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-300 dark:text-gray-600">
                                0
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data.total > limit && (
              <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3 dark:border-gray-700">
                <span className="text-xs text-gray-500">
                  Showing {data.skip + 1}–{Math.min(data.skip + limit, data.total)} of{' '}
                  {data.total.toLocaleString()} keywords
                </span>
                <div className="flex items-center gap-1">
                  <button
                    disabled={page === 0}
                    onClick={() => handlePage(-1)}
                    className="flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    Previous
                  </button>
                  <span className="px-2 text-xs text-gray-500">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages - 1}
                    onClick={() => handlePage(1)}
                    className="flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
                  >
                    Next
                    <ChevronRight className="h-3.5 w-3.5" />
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
