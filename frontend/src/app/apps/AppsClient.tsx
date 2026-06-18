'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppShell } from '@/components';
import { AppListItem, Category, AppFilters, getFilteredApps, getCategories, searchAppsImport, lookupApp, AppImportSearchItem } from '@/lib/api';
import {
  Search, AppWindow, Star, SlidersHorizontal, X,
  RotateCcw, ChevronUp, ChevronDown, Loader2, Plus, Globe,
  MessageCircle, Download,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fmtNum, fmtRev, confidenceLabel, CONFIDENCE_BADGE, getDailyDownloads } from '@/lib/estimate-format';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

const SORT_OPTIONS = [
  { value: '', label: 'Default' },
  { value: 'name', label: 'Name' },
  { value: 'rating', label: 'Rating' },
  { value: 'reviews', label: 'Reviews' },
  { value: 'rank', label: 'Rank' },
  { value: 'release_date', label: 'Release Date' },
  { value: 'last_updated', label: 'Last Updated' },
  { value: 'created_at', label: 'Date Added' },
  { value: 'estimated_downloads', label: 'Est. Downloads' },
  { value: 'estimated_revenue', label: 'Est. Revenue' },
  { value: 'install_confidence', label: 'Confidence' },
];


const DEFAULT_FILTERS: AppFilters = {
  search: '',
  category: '',
  developer: '',
  min_rating: '',
  max_rating: '',
  min_reviews: '',
  max_reviews: '',
  min_rank: '',
  max_rank: '',
  is_free: '',
  has_in_app_purchases: '',
  updated_after: '',
  updated_before: '',
  released_after: '',
  released_before: '',
  min_success_probability: '',
  min_feature_gaps: '',
  min_estimated_downloads: '',
  max_estimated_downloads: '',
  min_estimated_revenue: '',
  max_estimated_revenue: '',
  confidence_label: '',
  ai_only: false,
  sort_by: '',
  sort_order: 'desc',
  limit: 50,
  skip: 0,
};

interface FilterChip {
  key: keyof AppFilters;
  label: string;
  value: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildChips(filters: AppFilters): FilterChip[] {
  const chips: FilterChip[] = [];
  const add = (key: keyof AppFilters, label: string, fmt?: (v: unknown) => string) => {
    const val = filters[key];
    if (val === '' || val === undefined || val === null || val === false) return;
    chips.push({ key, label, value: fmt ? fmt(val) : String(val) });
  };

  add('search', 'Search', v => `"${v}"`);
  add('category', 'Category');
  add('developer', 'Developer');
  add('min_rating', 'Min Rating', v => `≥ ${v}★`);
  add('max_rating', 'Max Rating', v => `≤ ${v}★`);
  add('min_reviews', 'Min Reviews', v => `≥ ${Number(v).toLocaleString()}`);
  add('max_reviews', 'Max Reviews', v => `≤ ${Number(v).toLocaleString()}`);
  add('min_rank', 'Min Rank', v => `≥ #${v}`);
  add('max_rank', 'Max Rank', v => `≤ #${v}`);
  if (filters.is_free === true) chips.push({ key: 'is_free', label: 'Pricing', value: 'Free only' });
  if (filters.is_free === false) chips.push({ key: 'is_free', label: 'Pricing', value: 'Paid only' });
  if (filters.has_in_app_purchases === true) chips.push({ key: 'has_in_app_purchases', label: 'IAP', value: 'Has IAP' });
  if (filters.has_in_app_purchases === false) chips.push({ key: 'has_in_app_purchases', label: 'IAP', value: 'No IAP' });
  add('updated_after', 'Updated after');
  add('updated_before', 'Updated before');
  add('released_after', 'Released after');
  add('released_before', 'Released before');
  add('min_success_probability', 'Success prob.', v => `≥ ${v}%`);
  add('min_feature_gaps', 'Feature gaps', v => `≥ ${v} gaps`);
  add('min_estimated_downloads', 'Min DL/mo', v => `≥ ${fmtNum(Number(v))}`);
  add('max_estimated_downloads', 'Max DL/mo', v => `≤ ${fmtNum(Number(v))}`);
  add('min_estimated_revenue', 'Min Rev/mo', v => `≥ ${fmtRev(Number(v))}`);
  add('max_estimated_revenue', 'Max Rev/mo', v => `≤ ${fmtRev(Number(v))}`);
  add('confidence_label', 'Confidence');
  add('ai_only', 'AI', () => 'AI apps only');
  add('sort_by', 'Sort', v => `${SORT_OPTIONS.find(o => o.value === v)?.label ?? v} ${filters.sort_order === 'asc' ? '↑' : '↓'}`);
  return chips;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RangeInput({
  minKey, maxKey, label, draft, setDraft, min, max, step = 1,
}: {
  minKey: keyof AppFilters;
  maxKey: keyof AppFilters;
  label: string;
  draft: AppFilters;
  setDraft: (f: AppFilters) => void;
  min?: number; max?: number; step?: number;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          placeholder="Min"
          value={draft[minKey] as string}
          min={min} max={max} step={step}
          onChange={e => setDraft({ ...draft, [minKey]: e.target.value === '' ? '' : Number(e.target.value) })}
          className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <span className="text-gray-400 text-sm flex-shrink-0">–</span>
        <input
          type="number"
          placeholder="Max"
          value={draft[maxKey] as string}
          min={min} max={max} step={step}
          onChange={e => setDraft({ ...draft, [maxKey]: e.target.value === '' ? '' : Number(e.target.value) })}
          className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>
    </div>
  );
}

function TriToggle({
  label, value, onChange,
}: { label: string; value: boolean | ''; onChange: (v: boolean | '') => void }) {
  const btn = (v: boolean | '', text: string) => (
    <button
      type="button"
      onClick={() => onChange(v)}
      className={cn(
        'flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
        value === v
          ? 'bg-indigo-600 text-white'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600',
      )}
    >
      {text}
    </button>
  );
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {label}
      </label>
      <div className="flex gap-1">{btn('', 'Any')}{btn(true, 'Yes')}{btn(false, 'No')}</div>
    </div>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
        {title}
      </p>
      {children}
      <div className="border-t border-gray-100 dark:border-gray-800 pt-1" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract App Store numeric ID from URLs like https://apps.apple.com/.../id1234567890 */
function parseAppStoreInput(input: string): string | null {
  const trimmed = input.trim();
  // URL pattern: id followed by 6+ digits
  const urlMatch = trimmed.match(/[?/]id(\d{6,})/);
  if (urlMatch) return urlMatch[1];
  // Pure numeric ID (at least 6 digits)
  if (/^\d{6,}$/.test(trimmed)) return trimmed;
  return null;
}

// ---------------------------------------------------------------------------
// URL ↔ AppFilters serialization
// ---------------------------------------------------------------------------

function filtersToSearchParams(filters: AppFilters): URLSearchParams {
  const p = new URLSearchParams();
  const s = (key: keyof AppFilters) => {
    const v = filters[key];
    if (v !== undefined && v !== null && v !== '') p.set(key, String(v));
  };
  s('search'); s('category'); s('developer'); s('sort_by');
  if (filters.sort_order && filters.sort_order !== 'desc') p.set('sort_order', filters.sort_order);
  s('updated_after'); s('updated_before'); s('released_after'); s('released_before');
  s('confidence_label');
  s('min_rating'); s('max_rating');
  s('min_reviews'); s('max_reviews');
  s('min_rank'); s('max_rank');
  s('min_success_probability'); s('min_feature_gaps');
  s('min_estimated_downloads'); s('max_estimated_downloads');
  s('min_estimated_revenue'); s('max_estimated_revenue');
  if (filters.is_free === true)  p.set('is_free', '1');
  if (filters.is_free === false) p.set('is_free', '0');
  if (filters.has_in_app_purchases === true)  p.set('has_in_app_purchases', '1');
  if (filters.has_in_app_purchases === false) p.set('has_in_app_purchases', '0');
  if (filters.ai_only) p.set('ai_only', '1');
  const limit = filters.limit ?? 50;
  const skip  = filters.skip  ?? 0;
  if (skip > 0) p.set('page', String(Math.floor(skip / limit) + 1));
  if (limit !== 50) p.set('limit', String(limit));
  return p;
}

function filtersFromSearchParams(params: { get(key: string): string | null }): AppFilters {
  const str = (k: string) => params.get(k) ?? '';
  const num = (k: string): number | '' => {
    const v = params.get(k); if (!v) return '';
    const n = Number(v); return isNaN(n) ? '' : n;
  };
  const bool3 = (k: string): boolean | '' => {
    const v = params.get(k);
    return v === '1' ? true : v === '0' ? false : '';
  };
  const limit = Number(params.get('limit') ?? '50') || 50;
  const page  = Math.max(1, Number(params.get('page') ?? '1') || 1);
  return {
    ...DEFAULT_FILTERS,
    search: str('search'), category: str('category'), developer: str('developer'),
    sort_by: str('sort_by'),
    sort_order: (params.get('sort_order') as 'asc' | 'desc') ?? 'desc',
    updated_after: str('updated_after'), updated_before: str('updated_before'),
    released_after: str('released_after'), released_before: str('released_before'),
    confidence_label: str('confidence_label') as 'low' | 'medium' | 'high' | '',
    min_rating: num('min_rating'), max_rating: num('max_rating'),
    min_reviews: num('min_reviews'), max_reviews: num('max_reviews'),
    min_rank: num('min_rank'), max_rank: num('max_rank'),
    min_success_probability: num('min_success_probability'),
    min_feature_gaps: num('min_feature_gaps'),
    min_estimated_downloads: num('min_estimated_downloads'),
    max_estimated_downloads: num('max_estimated_downloads'),
    min_estimated_revenue: num('min_estimated_revenue'),
    max_estimated_revenue: num('max_estimated_revenue'),
    is_free: bool3('is_free'), has_in_app_purchases: bool3('has_in_app_purchases'),
    ai_only: params.get('ai_only') === '1',
    limit, skip: page > 1 ? (page - 1) * limit : 0,
  };
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AppsClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [apps, setApps] = useState<AppListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // appliedFilters drives API calls; draftFilters lives in the drawer until Apply
  // Both are initialized from URL search params so state survives back navigation.
  const [appliedFilters, setAppliedFilters] = useState<AppFilters>(() => filtersFromSearchParams(searchParams));
  const [draftFilters, setDraftFilters] = useState<AppFilters>(() => filtersFromSearchParams(searchParams));
  const [searchInput, setSearchInput] = useState(() => searchParams.get('search') ?? '');
  const searchTimer = useRef<ReturnType<typeof setTimeout>>();
  const isMounted = useRef(false);

  // App Store search state
  const [storeResults, setStoreResults] = useState<AppImportSearchItem[]>([]);
  const [storeSearching, setStoreSearching] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const storeSearchTimer = useRef<ReturnType<typeof setTimeout>>();

  // Load categories once
  useEffect(() => {
    getCategories()
      .then(setCategories)
      .catch(() => {});
  }, []);

  // Fetch whenever applied filters change
  const fetchApps = useCallback(async (filters: AppFilters) => {
    setLoading(true);
    try {
      const result = await getFilteredApps(filters);
      setApps(result.apps ?? []);
      setTotal(result.total ?? 0);
    } catch {
      setApps([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApps(appliedFilters);
  }, [appliedFilters, fetchApps]);

  // Keep URL in sync with applied filters (skip on first render — URL already correct)
  useEffect(() => {
    if (!isMounted.current) { isMounted.current = true; return; }
    const qs = filtersToSearchParams(appliedFilters).toString();
    router.replace(qs ? `/apps?${qs}` : '/apps', { scroll: false });
  }, [appliedFilters, router]);

  // Debounce search bar — also triggers App Store search
  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setAppliedFilters(prev => ({ ...prev, search: value, skip: 0 }));
    }, 400);

    // App Store parallel search
    clearTimeout(storeSearchTimer.current);
    if (value.trim().length < 2) {
      setStoreResults([]);
      return;
    }

    // If input looks like an App Store URL or numeric ID, skip text search
    const directId = parseAppStoreInput(value);
    if (directId) {
      setStoreSearching(true);
      lookupApp(directId)
        .then(detail => {
          router.push(`/apps/${detail.id}?imported=1`);
        })
        .catch(() => setStoreSearching(false))
        .finally(() => setStoreSearching(false));
      return;
    }

    storeSearchTimer.current = setTimeout(async () => {
      setStoreSearching(true);
      try {
        const res = await searchAppsImport(value.trim(), 6);
        // Only keep results not already in DB
        setStoreResults(res.results.filter(r => r.source === 'app_store'));
      } catch {
        setStoreResults([]);
      } finally {
        setStoreSearching(false);
      }
    }, 600);
  };

  const handleImport = async (app: AppImportSearchItem) => {
    setImporting(app.app_id);
    try {
      const detail = await lookupApp(app.app_id);
      router.push(`/apps/${detail.id}?imported=1`);
    } catch {
      setImporting(null);
    }
  };

  const openDrawer = () => {
    setDraftFilters({ ...appliedFilters });
    setDrawerOpen(true);
  };
  const closeDrawer = () => setDrawerOpen(false);

  const applyFilters = () => {
    setAppliedFilters({ ...draftFilters, search: searchInput, skip: 0 });
    setDrawerOpen(false);
  };

  const resetAll = () => {
    const fresh = { ...DEFAULT_FILTERS };
    setDraftFilters(fresh);
    setAppliedFilters(fresh);
    setSearchInput('');
    setDrawerOpen(false);
  };

  const removeChip = (key: keyof AppFilters) => {
    const updated: AppFilters = { ...appliedFilters, [key]: DEFAULT_FILTERS[key] };
    // If removing sort_by, also reset sort_order
    if (key === 'sort_by') updated.sort_order = 'desc';
    if (key === 'search') setSearchInput('');
    setAppliedFilters({ ...updated, skip: 0 });
    setDraftFilters(updated);
  };

  const activeChips = buildChips(appliedFilters);
  const hasActiveFilters = activeChips.length > 0;

  // Pagination helpers
  const currentPage = Math.floor((appliedFilters.skip ?? 0) / (appliedFilters.limit ?? 50)) + 1;
  const totalPages = Math.ceil(total / (appliedFilters.limit ?? 50));

  const goToPage = (page: number) => {
    const limit = appliedFilters.limit ?? 50;
    setAppliedFilters(prev => ({ ...prev, skip: (page - 1) * limit }));
  };

  return (
    <AppShell>
      <div className="space-y-5">

        {/* ── Page header ─────────────────────────────────────────────── */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Apps</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {loading ? 'Loading…' : `${total.toLocaleString()} tracked apps`}
            </p>
          </div>
        </div>

        {/* ── Search bar + filters button ──────────────────────────────── */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by name, developer, description…"
              value={searchInput}
              onChange={e => handleSearchChange(e.target.value)}
              className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white dark:placeholder-gray-500"
            />
          </div>
          <button
            onClick={openDrawer}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
              hasActiveFilters
                ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-500 dark:bg-indigo-950 dark:text-indigo-300'
                : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800',
            )}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
                {activeChips.length}
              </span>
            )}
          </button>
          {hasActiveFilters && (
            <button
              onClick={resetAll}
              title="Clear all filters"
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-500 hover:text-red-500 transition-colors dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400 dark:hover:text-red-400"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* ── Active filter chips ──────────────────────────────────────── */}
        {hasActiveFilters && (
          <div className="flex flex-wrap gap-2">
            {activeChips.map(chip => (
              <span
                key={chip.key}
                className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
              >
                <span className="text-indigo-400 dark:text-indigo-500">{chip.label}:</span>
                {chip.value}
                <button
                  onClick={() => removeChip(chip.key)}
                  className="ml-0.5 rounded-full p-0.5 hover:bg-indigo-200 dark:hover:bg-indigo-800 transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* ── Results ─────────────────────────────────────────────────── */}
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          </div>
        ) : apps.length > 0 ? (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {apps.map(app => {
                const daily = getDailyDownloads(app);
                return (
                <Link key={app.id} href={`/apps/${app.id}`}>
                  <div className="group cursor-pointer rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition-all duration-200 hover:border-indigo-200 hover:shadow-md dark:border-gray-800 dark:bg-gray-900">
                    <div className="flex items-start gap-3">
                      <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl bg-gray-100 dark:bg-gray-800">
                        {app.icon_url ? (
                          <img src={app.icon_url} alt={app.name} className="h-full w-full object-cover" />
                        ) : (
                          <AppWindow className="h-6 w-6 text-gray-400" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                          {app.name || 'Unknown App'}
                        </h3>
                        <p className="truncate text-xs text-gray-500 dark:text-gray-400">
                          {app.developer || 'Unknown Developer'}
                        </p>
                        {app.primary_category && (
                          <span className="mt-1 inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                            {app.primary_category}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-3 dark:border-gray-800">
                      <div className="flex items-center gap-3">
                        {app.current_rank != null && (
                          <div className="text-center">
                            <span className="block text-xs font-semibold text-gray-900 dark:text-white">
                              #{app.current_rank}
                            </span>
                            <span className="text-xs text-gray-400">Rank</span>
                          </div>
                        )}
                        {app.current_rating != null && (
                          <div className="flex items-center gap-1">
                            <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                            <span className="text-sm font-medium text-gray-900 dark:text-white">
                              {app.current_rating.toFixed(1)}
                            </span>
                          </div>
                        )}
                      </div>
                      {app.current_reviews != null && (
                        <div className="flex items-center gap-1.5 flex-wrap text-xs text-gray-500 dark:text-gray-400">
                          <span className="flex items-center gap-0.5">
                            <MessageCircle className="w-3 h-3" />
                            {app.current_reviews.toLocaleString()} reviews
                          </span>
                          <span>•</span>
                          <span className="flex items-center gap-0.5">
                            <Download className="w-3 h-3" />
                            {daily != null ? `${Math.max(1, Math.round(daily))}/day` : '—/day'}
                          </span>
                        </div>
                      )}
                    </div>
                    {(app.estimated_installs_min != null || app.estimated_revenue_monthly_min != null) && (
                      <div data-testid="estimate-row" className="mt-2 flex items-center justify-between border-t border-gray-100 pt-2 dark:border-gray-800">
                        <div className="flex items-center gap-3">
                          {app.estimated_installs_min != null && (
                            <div className="text-center">
                              <span className="block text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                                {fmtNum(app.estimated_installs_min)}
                              </span>
                              <span className="text-[10px] text-gray-400">DL/mo</span>
                            </div>
                          )}
                          {app.estimated_revenue_monthly_min != null && (
                            <div className="text-center">
                              <span className="block text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                {fmtRev(app.estimated_revenue_monthly_min)}
                              </span>
                              <span className="text-[10px] text-gray-400">Rev/mo</span>
                            </div>
                          )}
                        </div>
                        {(() => {
                          const conf = confidenceLabel(app.install_confidence);
                          if (!conf) return null;
                          return (
                            <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', CONFIDENCE_BADGE[conf])}>
                              {conf}
                            </span>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                </Link>
                );
              })}
            </div>

            {/* ── Pagination ───────────────────────────────────────────── */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-2">
                <button
                  onClick={() => goToPage(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800 disabled:cursor-not-allowed"
                >
                  ← Prev
                </button>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => goToPage(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800 disabled:cursor-not-allowed"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="rounded-xl border border-gray-200 bg-white p-12 text-center dark:border-gray-800 dark:bg-gray-900">
            <AppWindow className="mx-auto mb-4 h-12 w-12 text-gray-300 dark:text-gray-600" />
            <p className="text-base font-medium text-gray-600 dark:text-gray-400">No apps match your filters</p>
            <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">Try adjusting or clearing your filters</p>
            {hasActiveFilters && (
              <button
                onClick={resetAll}
                className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Clear filters
              </button>
            )}
          </div>
        )}

        {/* ── App Store results ─────────────────────────────────────── */}
        {(storeSearching || storeResults.length > 0) && searchInput.trim().length >= 2 && (
          <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
            <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3 dark:border-gray-800">
              <Globe className="h-4 w-4 text-emerald-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">From App Store</h2>
              <span className="text-xs text-gray-400 dark:text-gray-500">— not yet tracked</span>
              {storeSearching && <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-gray-400" />}
            </div>
            {storeResults.length > 0 && (
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {storeResults.map(item => (
                  <div key={item.app_id} className="flex items-center gap-4 px-4 py-3">
                    {item.icon_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={item.icon_url} alt={item.name} className="h-10 w-10 flex-shrink-0 rounded-xl object-cover" />
                    ) : (
                      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500">
                        <span className="text-sm font-bold text-white">{item.name[0]?.toUpperCase()}</span>
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">{item.name}</p>
                      <p className="truncate text-xs text-gray-500 dark:text-gray-400">
                        {item.developer}
                        {item.primary_category && <span className="ml-2 text-gray-400">· {item.primary_category}</span>}
                      </p>
                    </div>
                    {item.current_rating != null && item.current_rating > 0 && (
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                        <span className="text-xs text-gray-600 dark:text-gray-300">{item.current_rating.toFixed(1)}</span>
                      </div>
                    )}
                    <button
                      onClick={() => handleImport(item)}
                      disabled={importing === item.app_id}
                      className="flex flex-shrink-0 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-60"
                    >
                      {importing === item.app_id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Plus className="h-3.5 w-3.5" />
                      )}
                      Import & Track
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Filter drawer ────────────────────────────────────────────────── */}
      {/* Backdrop */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          onClick={closeDrawer}
        />
      )}

      {/* Drawer panel */}
      <div
        className={cn(
          'fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white shadow-2xl transition-transform duration-300 ease-in-out dark:bg-gray-900',
          drawerOpen ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        {/* Drawer header */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-5 w-5 text-indigo-500" />
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">Advanced Filters</h2>
          </div>
          <button
            onClick={closeDrawer}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Drawer body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">

          {/* Search & AI */}
          <DrawerSection title="Search & Discovery">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Keyword / Name / Developer
              </label>
              <input
                type="text"
                placeholder="e.g. fitness tracker"
                value={draftFilters.search ?? ''}
                onChange={e => setDraftFilters({ ...draftFilters, search: e.target.value })}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2.5 dark:border-gray-700">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">AI apps only</span>
              <button
                type="button"
                onClick={() => setDraftFilters({ ...draftFilters, ai_only: !draftFilters.ai_only })}
                className={cn(
                  'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                  draftFilters.ai_only ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700',
                )}
              >
                <span className={cn(
                  'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
                  draftFilters.ai_only ? 'translate-x-4' : 'translate-x-0.5',
                )} />
              </button>
            </div>
          </DrawerSection>

          {/* Category & Developer */}
          <DrawerSection title="Category & Developer">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Category
              </label>
              <select
                value={draftFilters.category ?? ''}
                onChange={e => setDraftFilters({ ...draftFilters, category: e.target.value })}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">Any category</option>
                {Array.from(new Set([
                  ...categories.map(c => c.name),
                  'Productivity', 'Games', 'Health & Fitness', 'Finance',
                  'Education', 'Social Networking', 'Entertainment',
                  'Utilities', 'Travel', 'Music',
                ])).sort().map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Developer
              </label>
              <input
                type="text"
                placeholder="e.g. Google LLC"
                value={draftFilters.developer ?? ''}
                onChange={e => setDraftFilters({ ...draftFilters, developer: e.target.value })}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </DrawerSection>

          {/* Rating */}
          <DrawerSection title="Rating & Reviews">
            <RangeInput
              minKey="min_rating" maxKey="max_rating"
              label="Rating (0–5)" draft={draftFilters} setDraft={setDraftFilters}
              min={0} max={5} step={0.1}
            />
            <RangeInput
              minKey="min_reviews" maxKey="max_reviews"
              label="Review Count" draft={draftFilters} setDraft={setDraftFilters}
              min={0}
            />
          </DrawerSection>

          {/* Rank */}
          <DrawerSection title="Chart Ranking">
            <RangeInput
              minKey="min_rank" maxKey="max_rank"
              label="Rank position" draft={draftFilters} setDraft={setDraftFilters}
              min={1}
            />
          </DrawerSection>

          {/* Pricing */}
          <DrawerSection title="Pricing">
            <TriToggle
              label="Price"
              value={draftFilters.is_free as boolean | ''}
              onChange={v => setDraftFilters({ ...draftFilters, is_free: v })}
            />
            <TriToggle
              label="In-App Purchases"
              value={draftFilters.has_in_app_purchases as boolean | ''}
              onChange={v => setDraftFilters({ ...draftFilters, has_in_app_purchases: v })}
            />
          </DrawerSection>

          {/* Dates */}
          <DrawerSection title="Dates">
            <div className="grid grid-cols-2 gap-3">
              {([
                ['updated_after', 'Updated after'],
                ['updated_before', 'Updated before'],
                ['released_after', 'Released after'],
                ['released_before', 'Released before'],
              ] as [keyof AppFilters, string][]).map(([key, label]) => (
                <div key={key}>
                  <label className="mb-1 block text-xs text-gray-500 dark:text-gray-400">{label}</label>
                  <input
                    type="date"
                    value={(draftFilters[key] as string) ?? ''}
                    onChange={e => setDraftFilters({ ...draftFilters, [key]: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              ))}
            </div>
          </DrawerSection>

          {/* Opportunity Score */}
          <DrawerSection title="Opportunity Score">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Min Success Probability (0–100)
              </label>
              <input
                type="number"
                placeholder="e.g. 60"
                min={0} max={100} step={1}
                value={(draftFilters.min_success_probability as number | '') ?? ''}
                onChange={e => setDraftFilters({
                  ...draftFilters,
                  min_success_probability: e.target.value === '' ? '' : Number(e.target.value),
                })}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </DrawerSection>

          {/* Feature Gaps */}
          <DrawerSection title="Feature Gaps">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Min Unique Feature Requests
              </label>
              <input
                type="number"
                placeholder="e.g. 3"
                min={1} step={1}
                value={(draftFilters.min_feature_gaps as number | '') ?? ''}
                onChange={e => setDraftFilters({
                  ...draftFilters,
                  min_feature_gaps: e.target.value === '' ? '' : Number(e.target.value),
                })}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Show apps where users requested at least N distinct features
              </p>
            </div>
          </DrawerSection>

          {/* Download & Revenue Estimates */}
          <DrawerSection title="Download & Revenue Estimates">
            <RangeInput
              minKey="min_estimated_downloads" maxKey="max_estimated_downloads"
              label="Est. Downloads / month" draft={draftFilters} setDraft={setDraftFilters}
              min={0}
            />
            <RangeInput
              minKey="min_estimated_revenue" maxKey="max_estimated_revenue"
              label="Est. Revenue / month ($)" draft={draftFilters} setDraft={setDraftFilters}
              min={0}
            />
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Confidence Level
              </label>
              <div className="flex gap-1">
                {(['', 'high', 'medium', 'low'] as const).map(level => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setDraftFilters({ ...draftFilters, confidence_label: level })}
                    className={cn(
                      'flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors',
                      draftFilters.confidence_label === level
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600',
                    )}
                  >
                    {level === '' ? 'Any' : level.charAt(0).toUpperCase() + level.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </DrawerSection>

          {/* Sort */}
          <DrawerSection title="Sort">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Sort by
              </label>
              <select
                value={draftFilters.sort_by ?? ''}
                onChange={e => setDraftFilters({ ...draftFilters, sort_by: e.target.value })}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Order
              </label>
              <div className="flex gap-2">
                {(['desc', 'asc'] as const).map(ord => (
                  <button
                    key={ord}
                    type="button"
                    onClick={() => setDraftFilters({ ...draftFilters, sort_order: ord })}
                    className={cn(
                      'flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                      draftFilters.sort_order === ord
                        ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-500 dark:bg-indigo-950 dark:text-indigo-300'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800',
                    )}
                  >
                    {ord === 'desc'
                      ? <><ChevronDown className="h-4 w-4" /> Descending</>
                      : <><ChevronUp className="h-4 w-4" /> Ascending</>}
                  </button>
                ))}
              </div>
            </div>
          </DrawerSection>
        </div>

        {/* Drawer footer */}
        <div className="border-t border-gray-100 px-5 py-4 dark:border-gray-800">
          <div className="flex gap-3">
            <button
              onClick={resetAll}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
            >
              <RotateCcw className="h-4 w-4" />
              Reset
            </button>
            <button
              onClick={applyFilters}
              className="flex-1 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
            >
              Apply Filters
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
