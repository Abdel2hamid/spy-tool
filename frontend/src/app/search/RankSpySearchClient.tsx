'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppShell } from '@/components';
import { rankspySearch, RankSpySearchItem, RankSpySearchResponse } from '@/lib/api';
import {
  Search, Globe, Star, Loader2, ExternalLink, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth';

const PAGE_SIZE = 50;

function formatNum(n: number | null | undefined): string {
  if (n == null) return '-';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function StarRating({ rating }: { rating: number | null }) {
  if (rating == null) return <span className="text-xs text-gray-400">-</span>;
  return (
    <span className="inline-flex items-center gap-0.5 text-xs">
      <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
      <span className="font-medium">{rating.toFixed(1)}</span>
    </span>
  );
}

function SourceBadge({ source, enrichment }: { source: string; enrichment: string }) {
  if (source === 'tracked') {
    return (
      <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
        Tracked
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
      {enrichment === 'pending' && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
      Discovered
    </span>
  );
}

function AppCard({ app }: { app: RankSpySearchItem }) {
  return (
    <Link
      href={`/apps/${app.id}`}
      className="group flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition-all hover:border-indigo-300 hover:shadow-md dark:border-gray-700 dark:bg-gray-800/60 dark:hover:border-indigo-600"
    >
      {/* Icon */}
      <div className="h-14 w-14 flex-shrink-0 overflow-hidden rounded-xl bg-gray-100 dark:bg-gray-700">
        {app.icon_url ? (
          <img src={app.icon_url} alt={app.name} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-400">
            <Globe className="h-6 w-6" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-gray-900 group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-400">
            {app.name}
          </h3>
          <SourceBadge source={app.source} enrichment={app.enrichment_status} />
        </div>
        <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
          {app.developer || 'Unknown Developer'}
        </p>
        <div className="mt-1 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
          <StarRating rating={app.current_rating} />
          <span>{formatNum(app.current_reviews)} reviews</span>
          {app.primary_category && (
            <span className="hidden sm:inline">{app.primary_category}</span>
          )}
          <span className={app.is_free ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-600 dark:text-gray-300'}>
            {app.is_free ? 'Free' : `$${app.price?.toFixed(2) ?? '?'}`}
          </span>
        </div>
      </div>

      <ExternalLink className="h-4 w-4 flex-shrink-0 text-gray-300 group-hover:text-indigo-500 dark:text-gray-600" />
    </Link>
  );
}

export default function RankSpySearchClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token } = useAuth();

  const initialQuery = searchParams.get('q') || '';
  const [query, setQuery] = useState(initialQuery);
  const [submitted, setSubmitted] = useState(initialQuery);
  const [forceLive, setForceLive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<RankSpySearchResponse | null>(null);
  const [page, setPage] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const doSearch = useCallback(async (q: string, pageNum: number, live: boolean) => {
    if (!q || q.length < 2) {
      setData(null);
      return;
    }
    setLoading(true);
    try {
      const result = await rankspySearch(q, PAGE_SIZE, pageNum * PAGE_SIZE, live, token);
      setData(result);
    } catch (err) {
      console.error('[RankSpy] search error', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Search on submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (q.length < 2) return;
    setSubmitted(q);
    setPage(0);
    // Update URL without full reload
    const params = new URLSearchParams();
    params.set('q', q);
    router.replace(`/search?${params.toString()}`, { scroll: false });
    doSearch(q, 0, forceLive);
  };

  // Re-search on page change
  useEffect(() => {
    if (submitted) doSearch(submitted, page, forceLive);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  // Initial search from URL
  useEffect(() => {
    if (initialQuery) doSearch(initialQuery, 0, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;
  const trackedResults = data?.results.filter(r => r.source === 'tracked') ?? [];
  const discoveredResults = data?.results.filter(r => r.source === 'discovered') ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            App Store Search
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Search across the entire App Store. Find any app — even ones not yet in your database.
          </p>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Search apps, developers, keywords..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500 dark:focus:border-indigo-400 dark:focus:ring-indigo-800"
            />
          </div>
          <label className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 text-xs text-gray-600 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={forceLive}
              onChange={e => setForceLive(e.target.checked)}
              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <Globe className="h-3.5 w-3.5" />
            Live
          </label>
          <button
            type="submit"
            disabled={loading || query.trim().length < 2}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 dark:bg-indigo-500 dark:hover:bg-indigo-600"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Search
          </button>
        </form>

        {/* Error hint */}
        {data?.error_hint && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
            {data.error_hint}
          </div>
        )}

        {/* Stats bar */}
        {data && !loading && (
          <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
            <span className="font-medium text-gray-700 dark:text-gray-200">
              {data.total.toLocaleString()} result{data.total !== 1 ? 's' : ''}
            </span>
            {data.tracked_count > 0 && (
              <span className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                {data.tracked_count} tracked
              </span>
            )}
            {data.discovered_count > 0 && (
              <span className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-blue-500" />
                {data.discovered_count} discovered
              </span>
            )}
            {data.has_appstore_results && (
              <span className="text-xs text-indigo-500 dark:text-indigo-400">
                Includes live App Store results
              </span>
            )}
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          </div>
        )}

        {/* Results */}
        {data && !loading && data.results.length > 0 && (
          <div className="space-y-6">
            {/* Tracked apps section */}
            {trackedResults.length > 0 && (
              <div className="space-y-2">
                {discoveredResults.length > 0 && (
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Tracked Apps
                  </h2>
                )}
                <div className="space-y-2">
                  {trackedResults.map(app => (
                    <AppCard key={`t-${app.app_id}`} app={app} />
                  ))}
                </div>
              </div>
            )}

            {/* Discovered apps section */}
            {discoveredResults.length > 0 && (
              <div className="space-y-2">
                {trackedResults.length > 0 && (
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Newly Discovered
                  </h2>
                )}
                <div className="space-y-2">
                  {discoveredResults.map(app => (
                    <AppCard key={`d-${app.app_id}`} app={app} />
                  ))}
                </div>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 pt-2">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  <ChevronLeft className="h-4 w-4" /> Prev
                </button>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  Next <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {data && !loading && data.results.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 py-16 dark:border-gray-600">
            <Search className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              No apps found for &ldquo;{data.query}&rdquo;
            </p>
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              Try a different keyword or enable &ldquo;Live&rdquo; for App Store results.
            </p>
          </div>
        )}

        {/* Initial state */}
        {!data && !loading && (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 py-20 dark:border-gray-600">
            <Globe className="mb-4 h-12 w-12 text-gray-300 dark:text-gray-600" />
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Search any keyword to find apps
            </p>
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              Results include both tracked apps and live App Store discoveries.
            </p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
