'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import {
  AppListItem,
  AppListResponse,
  FreshRiserItem,
  FreshRisersResponse,
  getLatestApps,
  getFreshRisers,
} from '@/lib/api';
import { Star, Zap, Rocket, CalendarCheck, ChevronDown, ChevronUp, Loader2, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fmtNum, fmtRev } from '@/lib/estimate-format';

const SORT_OPTIONS = [
  { value: 'release_date', label: 'Release Date' },
  { value: 'rating',       label: 'Rating' },
  { value: 'reviews',      label: 'Reviews' },
  { value: 'name',         label: 'Name' },
];

const PAGE_SIZE = 48;

type Tab = 'new_releases' | 'fresh_risers' | 'released_today';

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 dark:border-gray-800 dark:bg-gray-900 animate-pulse">
      <div className="flex items-start gap-3">
        <div className="h-14 w-14 flex-shrink-0 rounded-2xl bg-gray-200 dark:bg-gray-700" />
        <div className="flex-1 min-w-0 space-y-2">
          <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-3 w-1/2 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-3 w-1/3 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <div className="h-5 w-16 rounded-full bg-gray-200 dark:bg-gray-700" />
        <div className="h-5 w-12 rounded-full bg-gray-200 dark:bg-gray-700" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// New Releases card
// ---------------------------------------------------------------------------

function AppCard({ app }: { app: AppListItem }) {
  const releaseDate = app.release_date
    ? new Date(app.release_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null;

  return (
    <Link
      href={`/apps/${app.id}`}
      className="group rounded-xl border border-gray-100 bg-white p-4 transition-all hover:border-indigo-200 hover:shadow-md dark:border-gray-800 dark:bg-gray-900 dark:hover:border-indigo-800"
    >
      <div className="flex items-start gap-3">
        {app.icon_url ? (
          <img
            src={app.icon_url}
            alt={app.name}
            className="h-14 w-14 flex-shrink-0 rounded-2xl object-cover shadow-sm"
          />
        ) : (
          <div className="h-14 w-14 flex-shrink-0 rounded-2xl bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center">
            <Zap className="h-6 w-6 text-white" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-gray-900 group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-400">
            {app.name}
          </p>
          {app.developer && (
            <p className="truncate text-xs text-gray-500 dark:text-gray-400">{app.developer}</p>
          )}
          {releaseDate && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Released {releaseDate}</p>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {app.primary_category && (
          <span className="inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
            {app.primary_category}
          </span>
        )}
        {app.current_rating != null && (
          <span className="inline-flex items-center gap-0.5 text-xs text-amber-500">
            <Star className="h-3 w-3 fill-amber-500" />
            {Number(app.current_rating).toFixed(1)}
          </span>
        )}
        {app.current_reviews > 0 && (
          <span className="text-xs text-gray-400">
            {app.current_reviews >= 1000
              ? `${(app.current_reviews / 1000).toFixed(1)}k reviews`
              : `${app.current_reviews} reviews`}
          </span>
        )}
      </div>
      {(app.estimated_installs_min != null || app.estimated_revenue_monthly_min != null) && (
        <div
          data-testid="estimate-row"
          className="mt-2 flex items-center gap-3 border-t border-gray-100 pt-2 dark:border-gray-800"
        >
          {app.estimated_installs_min != null && (
            <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
              {fmtNum(app.estimated_installs_min)}
              <span className="ml-0.5 font-normal text-gray-400"> DL/mo</span>
            </span>
          )}
          {app.estimated_revenue_monthly_min != null && (
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              {fmtRev(app.estimated_revenue_monthly_min)}
              <span className="ml-0.5 font-normal text-gray-400"> Rev/mo</span>
            </span>
          )}
        </div>
      )}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Fresh Risers card
// ---------------------------------------------------------------------------

function FreshRiserCard({ item }: { item: FreshRiserItem }) {
  const releaseDate = item.release_date
    ? new Date(item.release_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null;

  const score = Math.round(item.fresh_riser_score);

  const scoreColor =
    score >= 70 ? 'text-emerald-600 dark:text-emerald-400' :
    score >= 40 ? 'text-amber-600 dark:text-amber-400' :
    'text-gray-500 dark:text-gray-400';

  return (
    <Link
      href={`/apps/${item.app_id}`}
      className="group rounded-xl border border-gray-100 bg-white p-4 transition-all hover:border-emerald-200 hover:shadow-md dark:border-gray-800 dark:bg-gray-900 dark:hover:border-emerald-800"
    >
      <div className="flex items-start gap-3">
        <div className="h-14 w-14 flex-shrink-0 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
          <Rocket className="h-6 w-6 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-gray-900 group-hover:text-emerald-600 dark:text-white dark:group-hover:text-emerald-400">
            {item.app_name}
          </p>
          {item.developer && (
            <p className="truncate text-xs text-gray-500 dark:text-gray-400">{item.developer}</p>
          )}
          {releaseDate && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              Released {releaseDate} · {item.age_days}d ago
            </p>
          )}
        </div>
        {/* Score badge */}
        <div className="flex flex-col items-center">
          <span className={cn('text-lg font-bold tabular-nums', scoreColor)}>{score}</span>
          <span className="text-[9px] text-gray-400 uppercase tracking-wide">score</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {item.category && (
          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
            {item.category}
          </span>
        )}
        {item.current_rank != null && (
          <span className="inline-flex items-center gap-0.5 text-xs text-gray-500 dark:text-gray-400">
            <TrendingUp className="h-3 w-3" />
            #{item.current_rank}
          </span>
        )}
        {item.current_reviews > 0 && (
          <span className="text-xs text-gray-400">
            {item.current_reviews >= 1000
              ? `${(item.current_reviews / 1000).toFixed(1)}k reviews`
              : `${item.current_reviews} reviews`}
          </span>
        )}
        <span className="text-xs text-gray-400">{item.ranking_snapshots_count} snapshots</span>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function LatestAppsClient() {
  const [activeTab, setActiveTab] = useState<Tab>('new_releases');

  // New Releases state
  const [apps, setApps] = useState<AppListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingNR, setLoadingNR] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [category, setCategory] = useState('');
  const [sortBy, setSortBy] = useState('release_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [offset, setOffset] = useState(0);

  // Fresh Risers state
  const [freshRisers, setFreshRisers] = useState<FreshRiserItem[]>([]);
  const [freshStatus, setFreshStatus] = useState<string>('');
  const [freshMessage, setFreshMessage] = useState<string | null>(null);
  const [loadingFR, setLoadingFR] = useState(false);
  const freshFetchedRef = useRef(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ------------------------------------------------------------------
  // New Releases fetch
  // ------------------------------------------------------------------

  const fetchApps = useCallback(
    async (tab: Tab, cat: string, sb: string, so: 'asc' | 'desc', off: number, append = false) => {
      try {
        const mode = tab === 'released_today' ? 'released_today' : 'new_releases';
        const data = await getLatestApps({ mode, limit: PAGE_SIZE, offset: off, category: cat, sort_by: sb, sort_order: so });
        if (append) {
          setApps(prev => [...prev, ...data.apps]);
        } else {
          setApps(data.apps);
        }
        setTotal(data.total);
        setOffset(off + data.apps.length);
      } catch (err) {
        console.error('Failed to fetch latest apps:', err);
      }
    },
    []
  );

  // Re-fetch when tab (new_releases ↔ released_today), filters, or sort changes.
  // Fresh Risers has its own separate effect.
  useEffect(() => {
    if (activeTab === 'fresh_risers') return;
    setLoadingNR(true);
    setOffset(0);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      await fetchApps(activeTab, category, sortBy, sortOrder, 0, false);
      setLoadingNR(false);
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [activeTab, category, sortBy, sortOrder, fetchApps]);

  const handleLoadMore = async () => {
    setLoadingMore(true);
    await fetchApps(activeTab, category, sortBy, sortOrder, offset, true);
    setLoadingMore(false);
  };

  // ------------------------------------------------------------------
  // Fresh Risers fetch (lazy — only on first tab switch)
  // ------------------------------------------------------------------

  useEffect(() => {
    if (activeTab !== 'fresh_risers' || freshFetchedRef.current) return;
    freshFetchedRef.current = true;
    setLoadingFR(true);
    getFreshRisers({ limit: 50 })
      .then(data => {
        setFreshRisers(data.items);
        setFreshStatus(data.status);
        setFreshMessage(data.message ?? null);
      })
      .catch(err => {
        console.error('Failed to fetch fresh risers:', err);
        setFreshStatus('error');
      })
      .finally(() => setLoadingFR(false));
  }, [activeTab]);

  const toggleSortOrder = () => setSortOrder(o => (o === 'desc' ? 'asc' : 'desc'));

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <AppShell>
      <div className="mx-auto max-w-7xl space-y-6 p-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Zap className="h-6 w-6 text-indigo-500" />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">New Releases</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Discover newly released apps, the last 24 hours of launches, and new apps already gaining traction.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-xl border border-gray-200 bg-gray-50 p-1 w-fit dark:border-gray-700 dark:bg-gray-800/50">
          <button
            onClick={() => setActiveTab('new_releases')}
            className={cn(
              'flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-all',
              activeTab === 'new_releases'
                ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            )}
          >
            <Zap className="h-4 w-4" />
            New Releases
          </button>
          <button
            onClick={() => setActiveTab('fresh_risers')}
            className={cn(
              'flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-all',
              activeTab === 'fresh_risers'
                ? 'bg-white text-emerald-700 shadow-sm dark:bg-gray-700 dark:text-emerald-300'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            )}
          >
            <Rocket className="h-4 w-4" />
            Fresh Risers
          </button>
          <button
            onClick={() => setActiveTab('released_today')}
            className={cn(
              'flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-all',
              activeTab === 'released_today'
                ? 'bg-white text-violet-700 shadow-sm dark:bg-gray-700 dark:text-violet-300'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            )}
          >
            <CalendarCheck className="h-4 w-4" />
            Released Today
          </button>
        </div>

        {/* ── NEW RELEASES + RELEASED TODAY TABS ── */}
        {(activeTab === 'new_releases' || activeTab === 'released_today') && (
          <>
            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3">
              {!loadingNR && (
                <span className={cn(
                  'rounded-full px-3 py-1 text-sm font-medium',
                  activeTab === 'released_today'
                    ? 'bg-violet-50 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300'
                    : 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300',
                )}>
                  {total.toLocaleString()} apps
                </span>
              )}
              <input
                type="text"
                placeholder="Filter by category…"
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-400 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
              />
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                {SORT_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <button
                onClick={toggleSortOrder}
                title={sortOrder === 'desc' ? 'Descending' : 'Ascending'}
                className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                {sortOrder === 'desc' ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
              </button>
            </div>

            {/* Grid */}
            {loadingNR ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
              </div>
            ) : apps.length === 0 ? (
              <div className="rounded-xl border border-gray-100 bg-white p-12 text-center dark:border-gray-800 dark:bg-gray-900">
                <Zap className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
                <p className="text-gray-500 dark:text-gray-400">
                  {activeTab === 'released_today'
                    ? 'No apps released in the last 24 hours.'
                    : 'No apps released in the last 30 days.'}
                </p>
                {category && (
                  <button
                    onClick={() => setCategory('')}
                    className="mt-2 text-sm text-indigo-500 hover:underline"
                  >
                    Clear category filter
                  </button>
                )}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {apps.map(app => <AppCard key={app.id} app={app} />)}
                </div>
                {apps.length < total && (
                  <div className="flex justify-center pt-2">
                    <button
                      onClick={handleLoadMore}
                      disabled={loadingMore}
                      className={cn(
                        'flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-60',
                      )}
                    >
                      {loadingMore ? (
                        <><Loader2 className="h-4 w-4 animate-spin" />Loading…</>
                      ) : (
                        `Load More (${total - apps.length} remaining)`
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* ── FRESH RISERS TAB ── */}
        {activeTab === 'fresh_risers' && (
          <>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Apps released in the last 30 days already showing chart traction and review growth.
            </p>

            {loadingFR ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
              </div>
            ) : freshStatus !== 'success' ? (
              <div className="rounded-xl border border-gray-100 bg-white p-12 text-center dark:border-gray-800 dark:bg-gray-900">
                <Rocket className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
                <p className="text-gray-500 dark:text-gray-400">
                  {freshMessage ?? 'No fresh risers found yet. Check back after the next scoring run.'}
                </p>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                    {freshRisers.length} risers
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {freshRisers.map(item => <FreshRiserCard key={item.app_id} item={item} />)}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
