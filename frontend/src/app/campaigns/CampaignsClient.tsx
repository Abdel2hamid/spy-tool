'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import {
  getCampaignTrackingList,
  CampaignTrackingListItem,
  CampaignTrackingListResponse,
} from '@/lib/api';
import {
  Activity,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Zap,
  TrendingUp,
  Radio,
  Flame,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants & helpers
// ---------------------------------------------------------------------------

const EVENT_TYPE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  paid_push:        { label: 'Paid Push',        color: 'text-red-700 dark:text-red-400',     bg: 'bg-red-50 dark:bg-red-950/40'     },
  organic_breakout: { label: 'Organic Breakout', color: 'text-green-700 dark:text-green-400', bg: 'bg-green-50 dark:bg-green-950/40' },
  mixed:            { label: 'Mixed',             color: 'text-amber-700 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/40' },
  momentum_surge:   { label: 'Momentum Surge',   color: 'text-blue-700 dark:text-blue-400',   bg: 'bg-blue-50 dark:bg-blue-950/40'   },
  campaign_cooling: { label: 'Cooling',           color: 'text-gray-600 dark:text-gray-400',   bg: 'bg-gray-50 dark:bg-gray-800/40'   },
  unknown_unusual:  { label: 'Unusual',           color: 'text-purple-700 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-950/40' },
};

const EVENT_TYPES = ['all', 'paid_push', 'organic_breakout', 'mixed', 'momentum_surge', 'campaign_cooling', 'unknown_unusual'];

interface Filters {
  event_type: string;
  active_only: boolean;
  min_confidence: number;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EventBadge({ type }: { type: string }) {
  const meta = EVENT_TYPE_LABELS[type] ?? { label: type, color: 'text-gray-600', bg: 'bg-gray-100' };
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold', meta.bg, meta.color)}>
      {meta.label}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 70 ? 'bg-green-500' :
    pct >= 40 ? 'bg-amber-500' :
    'bg-gray-400';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 dark:text-gray-400">{pct}%</span>
    </div>
  );
}

function AppIcon({ src, name }: { src: string | null; name: string }) {
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
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
    indigo:  'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400',
    red:     'bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400',
    emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400',
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
// Campaign row (expandable)
// ---------------------------------------------------------------------------

function CampaignRow({ item, rank }: { item: CampaignTrackingListItem; rank: number }) {
  const [expanded, setExpanded] = useState(false);

  const detected = new Date(item.detected_at);
  const started = item.started_at_estimate ? new Date(item.started_at_estimate) : null;
  const daysSinceStart = started
    ? Math.floor((Date.now() - started.getTime()) / 86_400_000)
    : null;

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
            <AppIcon src={item.icon_url} name={item.name} />
            <div className="min-w-0">
              <Link
                href={`/apps/${item.app_db_id}`}
                className="block truncate text-sm font-semibold text-gray-900 hover:text-indigo-600 dark:text-white dark:hover:text-indigo-400"
                onClick={(e) => e.stopPropagation()}
              >
                {item.name}
              </Link>
              <p className="truncate text-xs text-gray-500 dark:text-gray-400">
                {item.primary_category ?? '—'}
              </p>
            </div>
          </div>
        </td>

        {/* Event type */}
        <td className="py-3 pr-4">
          <EventBadge type={item.event_type} />
        </td>

        {/* Rank */}
        <td className="hidden py-3 pr-4 text-right sm:table-cell">
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {item.current_rank ? `#${item.current_rank}` : '—'}
          </span>
        </td>

        {/* BU score */}
        <td className="hidden py-3 pr-4 text-right md:table-cell">
          {item.blowing_up_score != null ? (
            <span className={cn(
              'text-sm font-semibold',
              item.blowing_up_score >= 65 ? 'text-emerald-600 dark:text-emerald-400' :
              item.blowing_up_score >= 40 ? 'text-amber-600 dark:text-amber-400' :
              'text-gray-500 dark:text-gray-400',
            )}>
              {item.blowing_up_score.toFixed(0)}
            </span>
          ) : (
            <span className="text-sm text-gray-400">—</span>
          )}
        </td>

        {/* Confidence */}
        <td className="py-3 pr-4">
          <ConfidenceBar value={item.confidence} />
        </td>

        {/* Detected */}
        <td className="hidden py-3 pr-4 text-right text-xs text-gray-500 dark:text-gray-400 lg:table-cell">
          {detected.toLocaleDateString()}
        </td>

        {/* Expand */}
        <td className="py-3 pr-4 w-8 text-center">
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-gray-400 mx-auto" />
            : <ChevronDown className="h-3.5 w-3.5 text-gray-400 mx-auto" />
          }
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && (
        <tr className="border-b border-gray-100 dark:border-gray-800/60 bg-indigo-50/20 dark:bg-indigo-950/10">
          <td colSpan={8} className="px-4 pb-4 pt-2">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {/* Event details */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                  <BarChart3 className="h-3.5 w-3.5 text-indigo-500" />
                  Event Details
                </p>
                <dl className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <dt className="text-gray-500 dark:text-gray-400">Type</dt>
                    <dd><EventBadge type={item.event_type} /></dd>
                  </div>
                  <div className="flex justify-between text-xs">
                    <dt className="text-gray-500 dark:text-gray-400">Confidence</dt>
                    <dd className="font-medium text-gray-800 dark:text-gray-200">{Math.round(item.confidence * 100)}%</dd>
                  </div>
                  {item.blowing_up_score != null && (
                    <div className="flex justify-between text-xs">
                      <dt className="text-gray-500 dark:text-gray-400">BU Score</dt>
                      <dd className="font-medium text-gray-800 dark:text-gray-200">{item.blowing_up_score.toFixed(1)}</dd>
                    </div>
                  )}
                  {item.current_rank && (
                    <div className="flex justify-between text-xs">
                      <dt className="text-gray-500 dark:text-gray-400">Rank</dt>
                      <dd className="font-medium text-gray-800 dark:text-gray-200">#{item.current_rank}</dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Timeline */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                  <Zap className="h-3.5 w-3.5 text-amber-500" />
                  Timeline
                </p>
                <dl className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <dt className="text-gray-500 dark:text-gray-400">Detected</dt>
                    <dd className="font-medium text-gray-800 dark:text-gray-200">{detected.toLocaleDateString()}</dd>
                  </div>
                  {started && (
                    <div className="flex justify-between text-xs">
                      <dt className="text-gray-500 dark:text-gray-400">Est. start</dt>
                      <dd className="font-medium text-gray-800 dark:text-gray-200">{started.toLocaleDateString()}</dd>
                    </div>
                  )}
                  {daysSinceStart !== null && (
                    <div className="flex justify-between text-xs">
                      <dt className="text-gray-500 dark:text-gray-400">Duration</dt>
                      <dd className="font-medium text-gray-800 dark:text-gray-200">~{daysSinceStart}d</dd>
                    </div>
                  )}
                  <div className="flex justify-between text-xs">
                    <dt className="text-gray-500 dark:text-gray-400">Type</dt>
                    <dd className="font-medium text-gray-800 dark:text-gray-200 capitalize">
                      {item.event_type.replace(/_/g, ' ')}
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Explanation */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                  <TrendingUp className="h-3.5 w-3.5 text-purple-500" />
                  Signal Analysis
                </p>
                {item.explanation ? (
                  <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">{item.explanation}</p>
                ) : (
                  <p className="text-xs text-gray-400 dark:text-gray-500 italic">No explanation available.</p>
                )}
                <div className="mt-3">
                  <Link
                    href={`/apps/${item.app_db_id}`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
                    onClick={(e) => e.stopPropagation()}
                  >
                    View app detail →
                  </Link>
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

export default function CampaignsClient() {
  const [data, setData] = useState<CampaignTrackingListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    event_type: 'all',
    active_only: true,
    min_confidence: 0.3,
  });
  const [skip, setSkip] = useState(0);
  const limit = 50;

  const fetchData = useCallback(async (f: Filters, s: number, isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const res = await getCampaignTrackingList({
        event_type: f.event_type !== 'all' ? f.event_type : undefined,
        active_only: f.active_only,
        min_confidence: f.min_confidence,
        skip: s,
        limit,
      });
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(filters, skip); }, []);

  const applyFilter = (patch: Partial<Filters>) => {
    const next = { ...filters, ...patch };
    setFilters(next);
    setSkip(0);
    fetchData(next, 0);
  };

  const paginate = (dir: 1 | -1) => {
    const next = Math.max(0, skip + dir * limit);
    setSkip(next);
    fetchData(filters, next);
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  // Derive summary counts from by_type
  const byType = data?.by_type ?? {};
  const paidCount    = byType['paid_push'] ?? 0;
  const organicCount = byType['organic_breakout'] ?? 0;
  const surgeCount   = byType['momentum_surge'] ?? 0;

  return (
    <ErrorBoundary>
      <AppShell>
        <div className="space-y-6">

          {/* ── Header ─────────────────────────────────────────────────── */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
                <Radio className="h-6 w-6 text-indigo-500" />
                Campaign Tracking
              </h1>
              <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                Growth signal detection — paid pushes, organic breakouts, and momentum surges.
              </p>
            </div>
            <button
              onClick={() => fetchData(filters, skip, true)}
              disabled={refreshing}
              className="flex items-center gap-2 self-start rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          {/* ── Summary cards ───────────────────────────────────────────── */}
          {data && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SummaryCard label="Total Events"     value={total}        icon={Activity}   accent="indigo" />
              <SummaryCard label="Paid Pushes"      value={paidCount}    icon={Flame}      accent="red"    />
              <SummaryCard label="Organic Breakouts" value={organicCount} icon={TrendingUp} accent="emerald" />
              <SummaryCard label="Momentum Surges"  value={surgeCount}   icon={Zap}        accent="amber"  />
            </div>
          )}

          {/* ── Filter bar ─────────────────────────────────────────────── */}
          <div className="card p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Filter className="h-4 w-4 flex-shrink-0 text-gray-400" />

              {/* Event type segment control */}
              <div className="flex flex-wrap items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-0.5 dark:border-gray-700 dark:bg-gray-800">
                {EVENT_TYPES.map(t => (
                  <button
                    key={t}
                    onClick={() => applyFilter({ event_type: t })}
                    className={cn(
                      'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                      filters.event_type === t
                        ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
                    )}
                  >
                    {t === 'all' ? 'All' : (EVENT_TYPE_LABELS[t]?.label ?? t)}
                  </button>
                ))}
              </div>

              <div className="ml-auto flex items-center gap-3">
                {/* Active only */}
                <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={filters.active_only}
                    onChange={e => applyFilter({ active_only: e.target.checked })}
                    className="rounded border-gray-300 dark:border-gray-600"
                  />
                  Active only
                </label>

                {/* Min confidence */}
                <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                  Confidence ≥
                  <select
                    value={filters.min_confidence}
                    onChange={e => applyFilter({ min_confidence: Number(e.target.value) })}
                    className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                  >
                    <option value={0.0}>Any</option>
                    <option value={0.3}>30%</option>
                    <option value={0.5}>50%</option>
                    <option value={0.7}>70%</option>
                  </select>
                </label>
              </div>
            </div>
          </div>

          {/* ── Results ─────────────────────────────────────────────────── */}
          {loading ? (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-16 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
              ))}
            </div>
          ) : !data || items.length === 0 ? (
            <div className="card p-12 text-center">
              <Radio className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-700" />
              <p className="font-medium text-gray-500 dark:text-gray-400">No growth events detected yet</p>
              <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                The campaign detection job runs every 2 hours after the blowing-up scorer.
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
                      <th className="py-3 pr-4 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Event</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider sm:table-cell">Rank</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider md:table-cell">BU Score</th>
                      <th className="py-3 pr-4 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Confidence</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider lg:table-cell">Detected</th>
                      <th className="py-3 pr-4 w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, idx) => (
                      <CampaignRow
                        key={`${item.app_db_id}-${item.detected_at}`}
                        item={item}
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
