'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import {
  getAdIntelligenceList,
  AdIntelligenceListItem,
  AdIntelligenceListResponse,
} from '@/lib/api';
import {
  Megaphone,
  Radio,
  TrendingUp,
  BarChart3,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Calendar,
  Globe,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NETWORKS = ['all', 'apple_search_ads', 'meta', 'google_uac'] as const;

const NETWORK_META: Record<string, { label: string; color: string }> = {
  apple_search_ads: {
    label: 'Apple Search Ads',
    color: 'bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300',
  },
  meta: {
    label: 'Meta',
    color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300',
  },
  google_uac: {
    label: 'Google UAC',
    color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400',
  },
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function NetworkBadge({ network }: { network: string }) {
  const meta = NETWORK_META[network] ?? { label: network, color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' };
  return (
    <span className={cn('pill text-[10px] font-semibold px-1.5 py-0.5', meta.color)}>
      {meta.label}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 70 ? 'bg-emerald-500' :
    pct >= 40 ? 'bg-amber-500' :
    'bg-gray-400';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-gray-500 dark:text-gray-400">{pct}%</span>
    </div>
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
    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-400 to-indigo-500 text-white text-sm font-bold shadow-sm">
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
    blue:    'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400',
    indigo:  'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400',
    emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400',
    amber:   'bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400',
  };
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className={cn('flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg', accents[accent])}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{label}</p>
        <p className="text-lg font-bold leading-tight text-gray-900 dark:text-white">{value}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row component
// ---------------------------------------------------------------------------

function AdRow({ item, rank }: { item: AdIntelligenceListItem; rank: number }) {
  const [expanded, setExpanded] = useState(false);

  const firstSeen = item.first_ad_seen ? new Date(item.first_ad_seen) : null;
  const lastSeen  = item.last_ad_seen  ? new Date(item.last_ad_seen)  : null;
  const runDays   = firstSeen && lastSeen
    ? Math.floor((lastSeen.getTime() - firstSeen.getTime()) / 86_400_000)
    : null;

  return (
    <>
      <tr
        className="cursor-pointer border-b border-gray-100 hover:bg-indigo-50/40 dark:border-gray-800/60 dark:hover:bg-indigo-950/20 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* # */}
        <td className="w-8 py-3 pl-4 pr-2 text-center text-xs font-medium text-gray-400 dark:text-gray-600">
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
                {item.current_rank && (
                  <span className="ml-1.5 text-gray-400">#{item.current_rank}</span>
                )}
              </p>
            </div>
          </div>
        </td>

        {/* Networks */}
        <td className="hidden py-3 pr-4 lg:table-cell">
          <div className="flex flex-wrap gap-1">
            {item.networks.map((n) => <NetworkBadge key={n} network={n} />)}
          </div>
        </td>

        {/* Campaigns / Creatives */}
        <td className="hidden py-3 pr-4 text-right sm:table-cell">
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {item.active_campaigns}
          </span>
          <span className="ml-1 text-xs text-gray-400">camp.</span>
        </td>
        <td className="hidden py-3 pr-4 text-right md:table-cell">
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {item.active_creatives}
          </span>
          <span className="ml-1 text-xs text-gray-400">creat.</span>
        </td>

        {/* Last seen */}
        <td className="hidden py-3 pr-4 text-right lg:table-cell">
          {lastSeen ? (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {lastSeen.toLocaleDateString()}
            </span>
          ) : (
            <span className="text-xs text-gray-300 dark:text-gray-600">—</span>
          )}
        </td>

        {/* Confidence */}
        <td className="py-3 pr-4">
          <ConfidenceBar value={item.max_confidence} />
        </td>

        {/* Expand chevron */}
        <td className="w-8 py-3 pr-4 text-center">
          {expanded
            ? <ChevronUp className="mx-auto h-3.5 w-3.5 text-gray-400" />
            : <ChevronDown className="mx-auto h-3.5 w-3.5 text-gray-400" />}
        </td>
      </tr>

      {/* Expanded detail */}
      {expanded && (
        <tr className="border-b border-gray-100 dark:border-gray-800/60 bg-indigo-50/20 dark:bg-indigo-950/10">
          <td colSpan={8} className="px-4 pb-4 pt-2">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {/* Networks detail */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 flex items-center gap-1 text-xs font-semibold text-gray-700 dark:text-gray-300">
                  <Radio className="h-3.5 w-3.5 text-blue-500" />
                  Ad Networks
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {item.networks.length > 0
                    ? item.networks.map((n) => <NetworkBadge key={n} network={n} />)
                    : <span className="text-xs text-gray-400">None detected</span>}
                </div>
              </div>

              {/* Campaign stats */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 flex items-center gap-1 text-xs font-semibold text-gray-700 dark:text-gray-300">
                  <Zap className="h-3.5 w-3.5 text-amber-500" />
                  Campaign Stats
                </p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                  <span>Active campaigns: <strong className="text-gray-800 dark:text-gray-200">{item.active_campaigns}</strong></span>
                  <span>Active creatives: <strong className="text-gray-800 dark:text-gray-200">{item.active_creatives}</strong></span>
                  {runDays !== null && runDays > 0 && (
                    <span className="col-span-2">Running for: <strong className="text-gray-800 dark:text-gray-200">{runDays}d</strong></span>
                  )}
                  <span>Confidence: <strong className="text-gray-800 dark:text-gray-200">{Math.round(item.max_confidence * 100)}%</strong></span>
                </div>
              </div>

              {/* Timeline */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900/50">
                <p className="mb-2 flex items-center gap-1 text-xs font-semibold text-gray-700 dark:text-gray-300">
                  <Calendar className="h-3.5 w-3.5 text-indigo-500" />
                  Activity Timeline
                </p>
                <div className="space-y-1 text-xs text-gray-500 dark:text-gray-400">
                  {firstSeen && (
                    <div>First detected: <strong className="text-gray-800 dark:text-gray-200">{firstSeen.toLocaleDateString()}</strong></div>
                  )}
                  {lastSeen && (
                    <div>Last seen: <strong className="text-gray-800 dark:text-gray-200">{lastSeen.toLocaleDateString()}</strong></div>
                  )}
                  {!firstSeen && !lastSeen && (
                    <span className="text-gray-400">No timeline data</span>
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
// Main component
// ---------------------------------------------------------------------------

export default function AdsClient() {
  const [data, setData] = useState<AdIntelligenceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [network, setNetwork] = useState<string>('all');
  const [activeOnly, setActiveOnly] = useState(true);
  const [skip, setSkip] = useState(0);
  const limit = 50;

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const res = await getAdIntelligenceList({
        network: network !== 'all' ? network : undefined,
        active_only: activeOnly,
        skip,
        limit,
      });
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [network, activeOnly, skip]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const applyNetwork = (n: string) => {
    setNetwork(n);
    setSkip(0);
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <ErrorBoundary>
      <AppShell>
        <div className="space-y-6">

          {/* ── Header ─────────────────────────────────────────────────── */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
                <Megaphone className="h-6 w-6 text-blue-500" />
                Ad Intelligence
              </h1>
              <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                Apps with detected advertising activity — campaigns and creatives by network
              </p>
            </div>
            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="flex items-center gap-2 self-start rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          {/* ── Summary stats ──────────────────────────────────────────── */}
          {data && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SummaryCard
                label="Apps with Ads"
                value={data.active_count}
                icon={Megaphone}
                accent="blue"
              />
              <SummaryCard
                label="Total Found"
                value={total}
                icon={BarChart3}
                accent="indigo"
              />
              <SummaryCard
                label="Apple Search Ads"
                value={items.filter(i => i.networks.includes('apple_search_ads')).length}
                icon={TrendingUp}
                accent="emerald"
              />
              <SummaryCard
                label="Showing"
                value={`${Math.min(skip + limit, total)} / ${total}`}
                icon={Globe}
                accent="amber"
              />
            </div>
          )}

          {/* ── Filter bar ─────────────────────────────────────────────── */}
          <div className="card p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Filter className="h-4 w-4 flex-shrink-0 text-gray-400" />

              {/* Network filter pills */}
              <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-0.5 dark:border-gray-700 dark:bg-gray-800">
                {NETWORKS.map((n) => (
                  <button
                    key={n}
                    onClick={() => applyNetwork(n)}
                    className={cn(
                      'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                      network === n
                        ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
                    )}
                  >
                    {n === 'all' ? 'All Networks' : (NETWORK_META[n]?.label ?? n)}
                  </button>
                ))}
              </div>

              {/* Active only toggle */}
              <label className="ml-auto flex cursor-pointer items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={activeOnly}
                  onChange={(e) => { setActiveOnly(e.target.checked); setSkip(0); }}
                  className="rounded border-gray-300 accent-indigo-600"
                />
                Active only
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
          ) : !data || items.length === 0 ? (
            <div className="card p-12 text-center">
              <Megaphone className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-700" />
              <p className="font-medium text-gray-500 dark:text-gray-400">No ad intelligence data yet</p>
              <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                The ad intelligence job runs every 6 hours for candidate apps showing momentum.
              </p>
            </div>
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px]">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50/70 dark:border-gray-800 dark:bg-gray-900/50">
                      <th className="w-8 py-3 pl-4 pr-2 text-center text-xs font-semibold text-gray-400 dark:text-gray-600">#</th>
                      <th className="py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">App</th>
                      <th className="hidden py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 lg:table-cell">Networks</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 sm:table-cell">Campaigns</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 md:table-cell">Creatives</th>
                      <th className="hidden py-3 pr-4 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 lg:table-cell">Last Seen</th>
                      <th className="py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                        <span className="flex items-center gap-1">
                          <Zap className="h-3.5 w-3.5 text-amber-400" />
                          Confidence
                        </span>
                      </th>
                      <th className="w-8 py-3 pr-4" />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, idx) => (
                      <AdRow key={item.app_db_id} item={item} rank={skip + idx + 1} />
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
                      onClick={() => setSkip(Math.max(0, skip - limit))}
                      className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                    >
                      Previous
                    </button>
                    <button
                      disabled={skip + limit >= total}
                      onClick={() => setSkip(skip + limit)}
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
