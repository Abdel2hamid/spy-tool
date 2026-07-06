'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { AppShell, CountrySelect } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import {
  getBlowingUpApps,
  BlowingUpApp,
  BlowingUpResponse,
  BlowingUpFilters,
} from '@/lib/api';
import {
  Flame,
  TrendingUp,
  Star,
  Filter,
  ChevronUp,
  ChevronDown,
  BarChart3,
  RefreshCw,
  Zap,
  Award,
  Globe,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIMEFRAMES = [
  { value: '24h', label: '24 h' },
  { value: '3d',  label: '3 d'  },
  { value: '7d',  label: '7 d'  },
] as const;

const CHART_TYPES = [
  { value: '',            label: 'All Charts' },
  { value: 'topfree',     label: 'Top Free'   },
  { value: 'toppaid',     label: 'Top Paid'   },
  { value: 'topgrossing', label: 'Top Gross.'  },
];

const SORT_OPTIONS = [
  { value: 'blowing_up_score', label: 'Blowing Up Score' },
  { value: 'rank_velocity',    label: 'Rank Velocity'    },
  { value: 'rank_change',      label: 'Rank Change'      },
  { value: 'reviews_velocity', label: 'Review Velocity'  },
  { value: 'confidence',       label: 'Confidence'       },
];

const BADGE_COLORS: Record<string, string> = {
  'New Entry':           'bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300',
  'Rapid Climb':         'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400',
  'Fast Reviews':        'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400',
  'Cross-Market':        'bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-400',
  'Consistent Momentum': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-400',
  'High Confidence':     'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ScorePill({ score, size = 'md' }: { score: number; size?: 'sm' | 'md' }) {
  const color =
    score >= 65 ? 'text-emerald-600 dark:text-emerald-400' :
    score >= 40 ? 'text-amber-600 dark:text-amber-400' :
                  'text-gray-500 dark:text-gray-400';
  const sz = size === 'sm' ? 'text-sm font-semibold' : 'text-base font-bold';
  return <span className={cn(sz, color)}>{score.toFixed(1)}</span>;
}

function RankChangeChip({ change }: { change: number }) {
  if (change === 0) return <span className="text-xs text-gray-400">—</span>;
  const positive = change > 0;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold',
        positive
          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
          : 'bg-red-50 text-red-600 dark:bg-red-950/60 dark:text-red-400',
      )}
    >
      {positive ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      {Math.abs(change)}
    </span>
  );
}

function Badge({ label }: { label: string }) {
  const cls = BADGE_COLORS[label] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  return (
    <span className={cn('pill text-[10px] leading-tight font-semibold px-1.5 py-0.5', cls)}>
      {label}
    </span>
  );
}

function AppIcon({ src, name }: { src: string | null; name: string }) {
  if (src) {
    return (
      <img
        src={src}
        alt={name}
        className="h-10 w-10 flex-shrink-0 rounded-xl object-cover shadow-sm"
        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
      />
    );
  }
  return (
    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-400 to-purple-500 text-white text-sm font-bold shadow-sm">
      {name.charAt(0).toUpperCase()}
    </div>
  );
}

function ScoreBar({ value, max = 100, color = 'bg-indigo-500' }: { value: number; max?: number; color?: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  accent: string;
}) {
  const accents: Record<string, string> = {
    flame:   'bg-orange-50 text-orange-600 dark:bg-orange-950/40 dark:text-orange-400',
    emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400',
    indigo:  'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400',
    amber:   'bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400',
  };
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className={cn('flex h-9 w-9 items-center justify-center rounded-lg flex-shrink-0', accents[accent])}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{label}</p>
        <p className="text-lg font-bold text-gray-900 dark:text-white leading-tight">{value}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score breakdown tooltip (popover on hover)
// ---------------------------------------------------------------------------

function ScoreBreakdown({ app }: { app: BlowingUpApp }) {
  const components = [
    { label: 'Rank Velocity',  score: app.rank_velocity_score,    color: 'bg-emerald-500', weight: '30%' },
    { label: 'Rank Change',    score: app.rank_change_score,      color: 'bg-indigo-500',  weight: '25%' },
    { label: 'Review Growth',  score: app.reviews_velocity_score, color: 'bg-amber-500',   weight: '20%' },
    { label: 'Chart Presence', score: app.chart_presence_score,   color: 'bg-cyan-500',    weight: '10%' },
    { label: 'Cross-Market',   score: app.cross_market_score,     color: 'bg-purple-500',  weight: '10%' },
    { label: 'Consistency',    score: app.consistency_score,      color: 'bg-rose-500',    weight:  '5%' },
  ];
  return (
    <div className="space-y-1.5">
      {components.map(({ label, score, color, weight }) => (
        <div key={label} className="grid grid-cols-[7rem_1fr_2rem] items-center gap-2 text-xs">
          <span className="text-gray-500 dark:text-gray-400 truncate">{label} <span className="text-gray-300 dark:text-gray-600">({weight})</span></span>
          <ScoreBar value={score} color={color} />
          <span className="text-right font-medium text-gray-700 dark:text-gray-300">{score.toFixed(0)}</span>
        </div>
      ))}
      <div className="mt-1 border-t border-gray-100 pt-1 dark:border-gray-800 text-xs text-gray-400">
        Confidence: {app.confidence_score.toFixed(0)}% · {app.chart_appearances} snapshots · {app.markets_count} markets
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main row component
// ---------------------------------------------------------------------------

function BlowingUpRow({ app, rank }: { app: BlowingUpApp; rank: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className="cursor-pointer border-b border-gray-100 hover:bg-indigo-50/40 dark:border-gray-800/60 dark:hover:bg-indigo-950/20 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* # */}
        <td className="py-3 pl-4 pr-2 text-center text-xs font-medium text-gray-400 dark:text-gray-600 w-8">
          {rank}
        </td>

        {/* App info */}
        <td className="py-3 pr-4">
          <div className="flex items-center gap-3">
            <AppIcon src={app.icon_url} name={app.name} />
            <div className="min-w-0">
              <Link
                href={`/apps/${app.id}`}
                className="block truncate text-sm font-semibold text-gray-900 hover:text-indigo-600 dark:text-white dark:hover:text-indigo-400"
                onClick={(e) => e.stopPropagation()}
              >
                {app.name}
              </Link>
              <p className="truncate text-xs text-gray-500 dark:text-gray-400">{app.developer ?? '—'}</p>
            </div>
          </div>
        </td>

        {/* Category */}
        <td className="hidden py-3 pr-4 text-xs text-gray-500 dark:text-gray-400 lg:table-cell">
          {app.primary_category ?? '—'}
        </td>

        {/* Rank */}
        <td className="py-3 pr-4 text-right">
          <div className="flex flex-col items-end gap-0.5">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              {app.current_rank ? `#${app.current_rank}` : '—'}
            </span>
            <RankChangeChip change={app.rank_change} />
          </div>
        </td>

        {/* Rank velocity */}
        <td className="hidden py-3 pr-4 text-right sm:table-cell">
          <span
            className={cn(
              'text-sm font-semibold',
              app.rank_velocity > 10
                ? 'text-emerald-600 dark:text-emerald-400'
                : app.rank_velocity > 0
                ? 'text-emerald-500/70 dark:text-emerald-500/70'
                : 'text-gray-400',
            )}
          >
            {app.rank_velocity > 0 ? `+${app.rank_velocity.toFixed(1)}` : app.rank_velocity.toFixed(1)}
          </span>
        </td>

        {/* Reviews velocity */}
        <td className="hidden py-3 pr-4 text-right md:table-cell">
          <span className="text-sm text-gray-700 dark:text-gray-300">
            {app.reviews_velocity >= 1
              ? `+${app.reviews_velocity.toFixed(1)}/d`
              : app.reviews_velocity > 0
              ? `+${app.reviews_velocity.toFixed(2)}/d`
              : '—'}
          </span>
        </td>

        {/* Blowing up score */}
        <td className="py-3 pr-4 text-right">
          <div className="flex flex-col items-end gap-1">
            <ScorePill score={app.blowing_up_score} />
            <div className="w-16">
              <ScoreBar
                value={app.blowing_up_score}
                color={
                  app.blowing_up_score >= 65 ? 'bg-emerald-500' :
                  app.blowing_up_score >= 40 ? 'bg-amber-500' : 'bg-gray-300'
                }
              />
            </div>
          </div>
        </td>

        {/* Badges */}
        <td className="hidden py-3 pr-4 xl:table-cell">
          <div className="flex flex-wrap gap-1">
            {app.badges.slice(0, 3).map((b) => <Badge key={b} label={b} />)}
          </div>
        </td>

        {/* Expand chevron */}
        <td className="py-3 pr-4 text-center w-8">
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-gray-400 mx-auto" />
            : <ChevronDown className="h-3.5 w-3.5 text-gray-400 mx-auto" />
          }
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && (
        <tr className="border-b border-gray-100 dark:border-gray-800/60 bg-indigo-50/20 dark:bg-indigo-950/10">
          <td colSpan={9} className="px-4 pb-4 pt-2">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {/* Score breakdown */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                  <BarChart3 className="h-3.5 w-3.5 text-indigo-500" />
                  Score Breakdown
                </p>
                <ScoreBreakdown app={app} />
              </div>

              {/* Why it's blowing up */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                  <Zap className="h-3.5 w-3.5 text-amber-500" />
                  Why It's Blowing Up
                </p>
                <ul className="space-y-1">
                  {app.why_flagged.map((reason, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                      <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>

              {/* All badges */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                  <Award className="h-3.5 w-3.5 text-purple-500" />
                  Badges & Signals
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {app.badges.length > 0
                    ? app.badges.map((b) => <Badge key={b} label={b} />)
                    : <span className="text-xs text-gray-400">No badges</span>
                  }
                </div>
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                  <span>Chart snapshots: <strong className="text-gray-800 dark:text-gray-200">{app.chart_appearances}</strong></span>
                  <span>Markets: <strong className="text-gray-800 dark:text-gray-200">{app.markets_count}</strong></span>
                  {app.current_rating && (
                    <span>Rating: <strong className="text-gray-800 dark:text-gray-200">★ {app.current_rating.toFixed(1)}</strong></span>
                  )}
                  {app.current_reviews !== null && app.current_reviews !== undefined && (
                    <span>Reviews: <strong className="text-gray-800 dark:text-gray-200">{app.current_reviews.toLocaleString()}</strong></span>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const DEFAULT_FILTERS: BlowingUpFilters = {
  limit:               50,
  skip:                0,
  sort_by:             'blowing_up_score',
  sort_order:          'desc',
  min_confidence:      0.3,
  min_reviews_velocity: 0,
  timeframe:           '7d',
  country:             'us',
};

export default function BlowingUpClient() {
  const [data, setData] = useState<BlowingUpResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filters, setFilters] = useState<BlowingUpFilters>(DEFAULT_FILTERS);

  const fetchData = useCallback(async (f: BlowingUpFilters, isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const result = await getBlowingUpApps(f);
      setData(result);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(filters); }, []);

  const applyFilter = <K extends keyof BlowingUpFilters>(key: K, value: BlowingUpFilters[K]) => {
    const next = { ...filters, [key]: value, skip: 0 };
    setFilters(next);
    fetchData(next);
  };

  const paginate = (dir: 1 | -1) => {
    const next = { ...filters, skip: Math.max(0, (filters.skip ?? 0) + dir * (filters.limit ?? 50)) };
    setFilters(next);
    fetchData(next);
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const skip  = filters.skip ?? 0;
  const limit = filters.limit ?? 50;

  return (
    <ErrorBoundary>
      <AppShell>
        <div className="space-y-6">

          {/* ── Header ─────────────────────────────────────────────────── */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
                <Flame className="h-6 w-6 text-orange-500" />
                Apps Blowing Up
              </h1>
              <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                Apps showing unusual momentum across rankings and reviews right now
              </p>
            </div>
            <div className="flex items-center gap-2 self-start">
              <CountrySelect
                value={filters.country ?? 'us'}
                onChange={(code) => applyFilter('country', code)}
              />
              <button
                onClick={() => fetchData(filters, true)}
                disabled={refreshing}
                className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
                {refreshing ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
          </div>

          {/* ── Summary stats ──────────────────────────────────────────── */}
          {data?.status === 'success' && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SummaryCard
                label="Exploding Apps"
                value={data.exploding_count ?? total}
                icon={Flame}
                accent="flame"
              />
              <SummaryCard
                label="Top Score"
                value={data.top_score ? data.top_score.toFixed(1) : '—'}
                icon={TrendingUp}
                accent="emerald"
              />
              <SummaryCard
                label="Avg Rank Velocity"
                value={data.avg_rank_velocity ? `+${data.avg_rank_velocity.toFixed(1)}` : '—'}
                icon={Zap}
                accent="amber"
              />
              <SummaryCard
                label="Showing"
                value={`${Math.min(skip + limit, total)} / ${total}`}
                icon={BarChart3}
                accent="indigo"
              />
            </div>
          )}

          {/* ── Filter bar ─────────────────────────────────────────────── */}
          <div className="card p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Filter className="h-4 w-4 flex-shrink-0 text-gray-400" />

              {/* Timeframe */}
              <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-0.5 dark:border-gray-700 dark:bg-gray-800">
                {TIMEFRAMES.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => applyFilter('timeframe', value)}
                    className={cn(
                      'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                      filters.timeframe === value
                        ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Chart type */}
              <select
                value={filters.chart_type ?? ''}
                onChange={(e) => applyFilter('chart_type', e.target.value || undefined)}
                className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-indigo-400 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                {CHART_TYPES.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>

              {/* Category */}
              <input
                type="text"
                placeholder="Category…"
                value={filters.category ?? ''}
                onChange={(e) => applyFilter('category', e.target.value || undefined)}
                className="w-32 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 placeholder-gray-400 focus:border-indigo-400 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
              />

              {/* Min confidence */}
              <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                Confidence ≥
                <select
                  value={String(filters.min_confidence ?? 0.3)}
                  onChange={(e) => applyFilter('min_confidence', Number(e.target.value))}
                  className="rounded border border-gray-200 bg-white px-1.5 py-1 text-xs text-gray-700 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                >
                  {[0.1, 0.2, 0.3, 0.5, 0.7].map((v) => (
                    <option key={v} value={String(v)}>{(v * 100).toFixed(0)}%</option>
                  ))}
                </select>
              </label>

              {/* Min review velocity */}
              <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                Reviews/day ≥
                <select
                  value={String(filters.min_reviews_velocity ?? 0)}
                  onChange={(e) => applyFilter('min_reviews_velocity', Number(e.target.value))}
                  className="rounded border border-gray-200 bg-white px-1.5 py-1 text-xs text-gray-700 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                >
                  {[0, 0.5, 1, 2, 5].map((v) => (
                    <option key={v} value={String(v)}>{v}</option>
                  ))}
                </select>
              </label>

              {/* Sort by */}
              <label className="ml-auto flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                Sort
                <select
                  value={filters.sort_by ?? 'blowing_up_score'}
                  onChange={(e) => applyFilter('sort_by', e.target.value)}
                  className="rounded border border-gray-200 bg-white px-1.5 py-1 text-xs text-gray-700 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                >
                  {SORT_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
                <button
                  onClick={() => applyFilter('sort_order', filters.sort_order === 'asc' ? 'desc' : 'asc')}
                  className="rounded border border-gray-200 bg-white p-1 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-700"
                  title={filters.sort_order === 'asc' ? 'Ascending' : 'Descending'}
                >
                  {filters.sort_order === 'asc'
                    ? <ChevronUp className="h-3.5 w-3.5 text-gray-500" />
                    : <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
                  }
                </button>
              </label>
            </div>
          </div>

          {/* ── Results ────────────────────────────────────────────────── */}
          {loading ? (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-16 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
              ))}
            </div>
          ) : !data || data.status === 'insufficient_data' ? (
            <div className="card p-12 text-center">
              <Flame className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-700" />
              <p className="font-medium text-gray-500 dark:text-gray-400">
                {data?.message ?? 'Momentum scores are still being computed.'}
              </p>
              <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                The scoring job runs every 15 minutes. Check back shortly.
              </p>
            </div>
          ) : data.status === 'empty' || items.length === 0 ? (
            <div className="card p-12 text-center">
              <TrendingUp className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-700" />
              <p className="font-medium text-gray-500 dark:text-gray-400">
                No apps match the current filters.
              </p>
              <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                Try relaxing confidence or velocity thresholds.
              </p>
            </div>
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px]">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-900/50">
                      <th className="py-3 pl-4 pr-2 text-center text-xs font-semibold text-gray-400 dark:text-gray-600 w-8">#</th>
                      <th className="py-3 pr-4 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">App</th>
                      <th className="hidden py-3 pr-4 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider lg:table-cell">Category</th>
                      <th className="py-3 pr-4 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Rank</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider sm:table-cell">Velocity</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider md:table-cell">Reviews/d</th>
                      <th className="py-3 pr-4 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        <span className="flex items-center justify-end gap-1">
                          <Flame className="h-3.5 w-3.5 text-orange-400" />
                          Score
                        </span>
                      </th>
                      <th className="hidden py-3 pr-4 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider xl:table-cell">Badges</th>
                      <th className="py-3 pr-4 w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((app, idx) => (
                      <BlowingUpRow
                        key={app.id}
                        app={app}
                        rank={skip + idx + 1}
                      />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {total > limit && (
                <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3 dark:border-gray-800">
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Showing {skip + 1}–{Math.min(skip + items.length, total)} of {total}
                  </p>
                  <div className="flex gap-2">
                    <button
                      disabled={skip === 0}
                      onClick={() => paginate(-1)}
                      className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                    >
                      Previous
                    </button>
                    <button
                      disabled={skip + limit >= total}
                      onClick={() => paginate(1)}
                      className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </AppShell>
    </ErrorBoundary>
  );
}
