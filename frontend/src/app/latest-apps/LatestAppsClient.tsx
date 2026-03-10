'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import { App, AppListResponse, getLatestApps } from '@/lib/api';
import { Star, Zap, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const SORT_OPTIONS = [
  { value: 'release_date', label: 'Release Date' },
  { value: 'rating', label: 'Rating' },
  { value: 'reviews', label: 'Reviews' },
  { value: 'name', label: 'Name' },
];

const PAGE_SIZE = 48;

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

function AppCard({ app }: { app: App }) {
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
    </Link>
  );
}

export default function LatestAppsClient() {
  const [apps, setApps] = useState<App[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [category, setCategory] = useState('');
  const [sortBy, setSortBy] = useState('release_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [offset, setOffset] = useState(0);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchApps = useCallback(
    async (cat: string, sb: string, so: 'asc' | 'desc', off: number, append = false) => {
      try {
        const data = await getLatestApps({ limit: PAGE_SIZE, offset: off, category: cat, sort_by: sb, sort_order: so });
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

  // Initial + filter-change fetch
  useEffect(() => {
    setLoading(true);
    setOffset(0);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      await fetchApps(category, sortBy, sortOrder, 0, false);
      setLoading(false);
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [category, sortBy, sortOrder, fetchApps]);

  const handleLoadMore = async () => {
    setLoadingMore(true);
    await fetchApps(category, sortBy, sortOrder, offset, true);
    setLoadingMore(false);
  };

  const toggleSortOrder = () => setSortOrder(o => (o === 'desc' ? 'asc' : 'desc'));

  return (
    <AppShell>
      <div className="mx-auto max-w-7xl space-y-6 p-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Zap className="h-6 w-6 text-indigo-500" />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Latest Apps</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Apps released or added in the last 60 days
          </p>
        </div>

        {/* Stats + filters */}
        <div className="flex flex-wrap items-center gap-3">
          {!loading && (
            <span className="rounded-full bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
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
        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : apps.length === 0 ? (
          <div className="rounded-xl border border-gray-100 bg-white p-12 text-center dark:border-gray-800 dark:bg-gray-900">
            <Zap className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
            <p className="text-gray-500 dark:text-gray-400">No apps found for the last 60 days.</p>
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
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading…
                    </>
                  ) : (
                    `Load More (${total - apps.length} remaining)`
                  )}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
