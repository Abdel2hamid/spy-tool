'use client';

import { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import {
  AppListItem,
  CompetitorCompareResponse,
  CompetitorAppSummary,
  CompetitorRankHistoryResponse,
  KeywordGapReportResponse,
  KeywordGapItem,
  getFilteredApps,
  getAppDetail,
  compareCompetitors,
  getCompetitorRankHistory,
  getKeywordGaps,
} from '@/lib/api';
import { fmtRange, fmtRevRange, confidenceLabel, CONFIDENCE_BADGE, fmtNum } from '@/lib/estimate-format';
import { cn } from '@/lib/utils';
import { setComparisonIds, getComparisonIds } from '@/lib/comparison-store';
import {
  Users,
  Search,
  X,
  GitCompare,
  Trophy,
  AlertCircle,
  Loader2,
  Key,
  Bug,
  TrendingUp,
  BarChart3,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

// ── Stable distinct colors for up to 5 apps ────────────────────────────────

const APP_COLORS = ['#6366f1', '#f43f5e', '#10b981', '#f59e0b', '#8b5cf6'];

// ── App Picker ──────────────────────────────────────────────────────────────

function AppPicker({
  selected,
  onAdd,
  onRemove,
}: {
  selected: AppListItem[];
  onAdd: (app: AppListItem) => void;
  onRemove: (id: number) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<AppListItem[]>([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const selectedIds = new Set(selected.map((a) => a.id));

  const doSearch = useCallback(
    (q: string) => {
      if (q.trim().length < 2) {
        setResults([]);
        setOpen(false);
        return;
      }
      setSearching(true);
      getFilteredApps({ search: q, limit: 8, sort_by: 'current_reviews' })
        .then((res) => {
          setResults(res.apps.filter((a) => !selectedIds.has(a.id)));
          setOpen(true);
        })
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected],
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, doSearch]);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div className="space-y-3">
      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((app) => (
            <span
              key={app.id}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
            >
              {app.icon_url ? (
                <img src={app.icon_url} alt="" className="h-5 w-5 rounded" />
              ) : (
                <span className="flex h-5 w-5 items-center justify-center rounded bg-indigo-100 text-[10px] font-bold text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
                  {app.name?.[0]}
                </span>
              )}
              <span className="max-w-[140px] truncate font-medium text-gray-900 dark:text-white">
                {app.name}
              </span>
              <button
                onClick={() => onRemove(app.id)}
                className="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search input + dropdown */}
      <div ref={containerRef} className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        {searching && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-gray-400" />
        )}
        <input
          type="text"
          placeholder={
            selected.length >= 5
              ? 'Maximum 5 apps reached'
              : 'Search apps to compare…'
          }
          disabled={selected.length >= 5}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 dark:border-gray-800 dark:bg-gray-900 dark:text-white"
        />

        {open && results.length > 0 && (
          <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900">
            {results.map((app) => (
              <button
                key={app.id}
                onClick={() => {
                  onAdd(app);
                  setQuery('');
                  setOpen(false);
                  setResults([]);
                }}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                {app.icon_url ? (
                  <img src={app.icon_url} alt="" className="h-8 w-8 flex-shrink-0 rounded-lg" />
                ) : (
                  <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-xs font-bold text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
                    {app.name?.[0]}
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-gray-900 dark:text-white">{app.name}</p>
                  <p className="truncate text-xs text-gray-500 dark:text-gray-400">
                    {app.developer || 'Unknown'}
                    {app.primary_category && ` · ${app.primary_category}`}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Winner cell helper ──────────────────────────────────────────────────────

function WinnerCell({
  isWinner,
  children,
}: {
  isWinner: boolean;
  children: React.ReactNode;
}) {
  return (
    <td
      className={cn(
        'whitespace-nowrap px-4 py-3 text-sm',
        isWinner && 'bg-emerald-50 dark:bg-emerald-950/30',
      )}
    >
      <span className="flex items-center gap-1.5">
        {children}
        {isWinner && <Trophy className="h-3.5 w-3.5 text-emerald-500" />}
      </span>
    </td>
  );
}

// ── Comparison Matrix ───────────────────────────────────────────────────────

function ComparisonMatrix({
  data,
}: {
  data: CompetitorCompareResponse;
}) {
  const { apps, winners } = data;
  const multi = apps.length > 1;

  const isWin = (key: string, appId: number) => multi && winners[key] === appId;

  type MetricRow = {
    label: string;
    winnerKey: string;
    render: (app: CompetitorAppSummary) => React.ReactNode;
  };

  const metrics: MetricRow[] = [
    {
      label: 'Category',
      winnerKey: '',
      render: (a) => a.primary_category || '—',
    },
    {
      label: 'Price',
      winnerKey: '',
      render: (a) => (a.is_free ? 'Free' : `$${a.price}`),
    },
    {
      label: 'Best chart rank',
      winnerKey: 'current_rank',
      render: (a) => (a.current_rank != null ? `#${a.current_rank}` : '—'),
    },
    {
      label: 'Rating',
      winnerKey: 'current_rating',
      render: (a) => (a.current_rating != null ? a.current_rating.toFixed(2) : '—'),
    },
    {
      label: 'Total reviews',
      winnerKey: 'current_reviews',
      render: (a) => (a.current_reviews != null ? fmtNum(a.current_reviews) : '—'),
    },
    {
      label: 'Reviews (30d)',
      winnerKey: 'review_velocity_30d',
      render: (a) => fmtNum(a.review_velocity_30d),
    },
    {
      label: 'Est. downloads/mo',
      winnerKey: 'estimated_installs',
      render: (a) => {
        const text = fmtRange(a.estimated_installs_min, a.estimated_installs_max);
        const conf = confidenceLabel(a.install_confidence);
        return (
          <span className="flex items-center gap-1.5">
            {text}
            {conf && (
              <span className={cn('pill text-[10px]', CONFIDENCE_BADGE[conf])}>
                {conf}
              </span>
            )}
          </span>
        );
      },
    },
    {
      label: 'Est. revenue/mo',
      winnerKey: 'estimated_revenue',
      render: (a) => fmtRevRange(a.estimated_revenue_monthly_min, a.estimated_revenue_monthly_max),
    },
    {
      label: 'Keyword coverage',
      winnerKey: 'keyword_count',
      render: (a) => fmtNum(a.keyword_count),
    },
  ];

  return (
    <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th className="sticky left-0 z-10 bg-gray-50 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:bg-gray-950 dark:text-gray-400">
              Metric
            </th>
            {apps.map((app) => (
              <th
                key={app.app_id}
                className="min-w-[160px] px-4 py-3"
              >
                <Link
                  href={`/apps/${app.app_id}`}
                  className="flex items-center gap-2 group"
                >
                  {app.icon_url ? (
                    <img src={app.icon_url} alt="" className="h-7 w-7 rounded-lg" />
                  ) : (
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-100 text-xs font-bold text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300">
                      {app.name?.[0]}
                    </span>
                  )}
                  <span className="max-w-[120px] truncate text-sm font-semibold text-gray-900 group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-400">
                    {app.name}
                  </span>
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {metrics.map((m) => (
            <tr key={m.label}>
              <td className="sticky left-0 z-10 bg-white px-4 py-3 text-xs font-medium text-gray-500 dark:bg-gray-900 dark:text-gray-400">
                {m.label}
              </td>
              {apps.map((app) => (
                <WinnerCell
                  key={app.app_id}
                  isWinner={!!m.winnerKey && isWin(m.winnerKey, app.app_id)}
                >
                  {m.render(app)}
                </WinnerCell>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Rank Trajectory Chart ───────────────────────────────────────────────────

function RankTrajectoryChart({
  appIds,
}: {
  appIds: number[];
}) {
  const [data, setData] = useState<CompetitorRankHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    if (appIds.length < 2) return;
    setLoading(true);
    getCompetitorRankHistory(appIds, days)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [appIds, days]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
        <div className="h-6 w-40 animate-pulse rounded bg-gray-200 dark:bg-gray-800 mb-4" />
        <div className="h-64 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
      </div>
    );
  }

  const hasSeries = data && data.series.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
          <TrendingUp className="h-5 w-5 text-indigo-500" />
          Rank Trajectory
        </h2>
        <div className="flex items-center gap-1">
          {[30, 60, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                'pill text-xs transition-colors',
                days === d
                  ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700',
              )}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
        {!hasSeries ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <BarChart3 className="h-10 w-10 text-gray-300 dark:text-gray-600" />
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
              No ranking data available for the selected apps in this period.
            </p>
          </div>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="date"
                  stroke="#6B7280"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(v: string) => {
                    const d = new Date(v);
                    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                  }}
                />
                <YAxis
                  stroke="#6B7280"
                  fontSize={11}
                  tickLine={false}
                  reversed
                  label={{ value: 'Rank (lower = better)', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#9CA3AF' } }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #E5E7EB',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelFormatter={(v: string) => {
                    const d = new Date(v);
                    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                  }}
                  formatter={(value: unknown, name: string) => {
                    const app = data.apps.find((a) => `app_${a.id}` === name);
                    return [value != null ? `#${value}` : '—', app?.name ?? name];
                  }}
                />
                <Legend
                  formatter={(value: string) => {
                    const app = data.apps.find((a) => `app_${a.id}` === value);
                    return app?.name ?? value;
                  }}
                />
                {data.apps.map((app, i) => (
                  <Line
                    key={app.id}
                    type="monotone"
                    dataKey={`app_${app.id}`}
                    stroke={APP_COLORS[i % APP_COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Keyword Overlap Section ─────────────────────────────────────────────────

function KeywordOverlapSection({ data }: { data: CompetitorCompareResponse }) {
  const { keyword_overlap } = data;
  return (
    <div className="space-y-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
        <Key className="h-5 w-5 text-indigo-500" />
        Keyword Overlap
      </h2>

      {/* Shared by all */}
      {keyword_overlap.shared_by_all_count > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Shared by all ({keyword_overlap.shared_by_all_count})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {keyword_overlap.shared_by_all.map((kw) => (
              <span key={kw} className="pill bg-indigo-50 text-indigo-600 text-xs dark:bg-indigo-950/40 dark:text-indigo-400">
                {kw}
              </span>
            ))}
            {keyword_overlap.shared_by_all_count > keyword_overlap.shared_by_all.length && (
              <span className="pill bg-gray-100 text-gray-500 text-xs dark:bg-gray-800 dark:text-gray-400">
                +{keyword_overlap.shared_by_all_count - keyword_overlap.shared_by_all.length} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Per-app breakdown */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {keyword_overlap.per_app.map((entry) => (
          <div
            key={entry.app_id}
            className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
          >
            <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">{entry.name}</p>
            <div className="mt-2 flex gap-3 text-xs text-gray-500 dark:text-gray-400">
              <span><strong className="text-gray-900 dark:text-white">{entry.total}</strong> total</span>
              <span><strong className="text-gray-900 dark:text-white">{entry.shared}</strong> shared</span>
              <span><strong className="text-emerald-600 dark:text-emerald-400">{entry.unique}</strong> unique</span>
            </div>
            {entry.unique_samples.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {entry.unique_samples.map((kw) => (
                  <span key={kw} className="pill bg-emerald-50 text-emerald-700 text-[10px] dark:bg-emerald-950/40 dark:text-emerald-400">
                    {kw}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Feature Gaps Section ────────────────────────────────────────────────────

function FeatureGapsSection({ data }: { data: CompetitorCompareResponse }) {
  const { apps } = data;
  const anyGaps = apps.some((a) => a.feature_gaps.length > 0);

  return (
    <div className="space-y-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
        <Bug className="h-5 w-5 text-indigo-500" />
        Feature Gaps
      </h2>

      {!anyGaps ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No feature gap data available for the selected apps yet.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {apps.map((app) => (
            <div
              key={app.app_id}
              className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
            >
              <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">{app.name}</p>
              {app.feature_gaps.length === 0 ? (
                <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">No gaps detected</p>
              ) : (
                <ul className="mt-2 space-y-1.5">
                  {app.feature_gaps.map((g) => (
                    <li key={g.feature} className="flex items-center justify-between text-xs">
                      <span className="truncate text-gray-700 dark:text-gray-300">{g.feature}</span>
                      <span className="pill ml-2 flex-shrink-0 bg-gray-100 text-gray-600 text-[10px] dark:bg-gray-800 dark:text-gray-400">
                        {g.mentions}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Gap Type Badge ──────────────────────────────────────────────────────────

const GAP_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  missing: { label: 'Missing', bg: 'bg-red-100 dark:bg-red-950/40', text: 'text-red-700 dark:text-red-400' },
  weak: { label: 'Weak', bg: 'bg-orange-100 dark:bg-orange-950/40', text: 'text-orange-700 dark:text-orange-400' },
  shared: { label: 'Shared', bg: 'bg-blue-100 dark:bg-blue-950/40', text: 'text-blue-700 dark:text-blue-400' },
  winning: { label: 'Winning', bg: 'bg-emerald-100 dark:bg-emerald-950/40', text: 'text-emerald-700 dark:text-emerald-400' },
  unique: { label: 'Unique', bg: 'bg-purple-100 dark:bg-purple-950/40', text: 'text-purple-700 dark:text-purple-400' },
};

const PRIORITY_DOT: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-orange-400',
  low: 'bg-gray-400',
  info: 'bg-gray-300 dark:bg-gray-600',
};

function MiniDonut({ value, invert = false }: { value: number; invert?: boolean }) {
  const r = 14;
  const circ = 2 * Math.PI * r;
  const eff = invert ? 100 - value : value;
  const color = eff >= 60 ? '#22c55e' : eff >= 35 ? '#f59e0b' : '#ef4444';
  const offset = circ - (value / 100) * circ;
  return (
    <svg width={32} height={32} className="flex-shrink-0">
      <circle cx={16} cy={16} r={r} fill="none" stroke="#e5e7eb" strokeWidth={3} className="dark:stroke-gray-700" />
      <circle
        cx={16} cy={16} r={r} fill="none" stroke={color} strokeWidth={3}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round" transform="rotate(-90 16 16)"
      />
      <text x={16} y={16} textAnchor="middle" dominantBaseline="central" fontSize={9} fontWeight={600} fill={color}>
        {Math.round(value)}
      </text>
    </svg>
  );
}

// ── Keyword Gap Analysis Section ────────────────────────────────────────────

function KeywordGapSection({
  appIds,
}: {
  appIds: number[];
}) {
  const [data, setData] = useState<KeywordGapReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    if (appIds.length < 2) return;
    setLoading(true);
    const [targetId, ...compIds] = appIds;
    getKeywordGaps(targetId, compIds)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [appIds]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-6 w-56 animate-pulse rounded bg-gray-200 dark:bg-gray-800" />
        <div className="h-64 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
      </div>
    );
  }

  if (!data || data.keywords.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
          <Key className="h-5 w-5 text-indigo-500" />
          Keyword Gap Analysis
        </h2>
        <div className="flex flex-col items-center justify-center rounded-2xl border border-gray-200 bg-white p-12 text-center dark:border-gray-800 dark:bg-gray-900">
          <Key className="h-10 w-10 text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            No keyword data available yet. Run keyword discovery on both apps first.
          </p>
        </div>
      </div>
    );
  }

  const { summary, keywords, target, competitors } = data;

  const filtered =
    filter === 'all'
      ? keywords
      : keywords.filter((k) => k.gap_type === filter);

  const filterOptions = [
    { key: 'all', label: 'All', count: summary.total_keywords },
    { key: 'missing', label: 'Missing', count: summary.missing },
    { key: 'weak', label: 'Weak', count: summary.weak },
    { key: 'shared', label: 'Shared', count: summary.shared },
    { key: 'winning', label: 'Winning', count: summary.winning },
    { key: 'unique', label: 'Unique', count: summary.unique },
  ];

  return (
    <div className="space-y-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
        <Key className="h-5 w-5 text-indigo-500" />
        Keyword Gap Analysis
        {summary.high_priority_gaps > 0 && (
          <span className="pill bg-red-100 text-red-700 text-xs dark:bg-red-950/40 dark:text-red-400">
            {summary.high_priority_gaps} high priority
          </span>
        )}
      </h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {filterOptions.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setFilter(opt.key)}
            className={cn(
              'rounded-xl border p-3 text-left transition-colors',
              filter === opt.key
                ? 'border-indigo-300 bg-indigo-50 dark:border-indigo-700 dark:bg-indigo-950/30'
                : 'border-gray-200 bg-white hover:border-gray-300 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700',
            )}
          >
            <p className="text-xl font-bold text-gray-900 dark:text-white">{opt.count}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{opt.label}</p>
          </button>
        ))}
      </div>

      {/* Gap table */}
      <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-950">
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                Keyword
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                Type
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-center">
                Volume
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-center">
                Difficulty
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-center">
                {target.name.length > 12 ? target.name.slice(0, 12) + '…' : target.name}
              </th>
              {competitors.map((c) => (
                <th key={c.app_id} className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-center">
                  {c.name.length > 12 ? c.name.slice(0, 12) + '…' : c.name}
                </th>
              ))}
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-center">
                Priority
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {filtered.slice(0, 100).map((kw) => {
              const badge = GAP_BADGE[kw.gap_type] || GAP_BADGE.shared;
              const dot = PRIORITY_DOT[kw.opportunity_priority] || PRIORITY_DOT.info;
              return (
                <tr key={kw.keyword} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-4 py-2.5 font-medium text-gray-900 dark:text-white max-w-[200px] truncate">
                    {kw.keyword}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={cn('pill text-[10px] font-semibold', badge.bg, badge.text)}>
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <MiniDonut value={kw.volume_score} />
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <MiniDonut value={kw.difficulty_v2} invert />
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {kw.target_rank != null ? (
                      <span className={cn(
                        'font-mono text-xs font-semibold',
                        kw.target_rank <= 10 ? 'text-emerald-600 dark:text-emerald-400' :
                        kw.target_rank <= 30 ? 'text-yellow-600 dark:text-yellow-400' :
                        'text-gray-500',
                      )}>
                        #{kw.target_rank}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-300 dark:text-gray-600">—</span>
                    )}
                  </td>
                  {competitors.map((c) => {
                    const rank = kw.competitor_ranks[c.app_id];
                    return (
                      <td key={c.app_id} className="px-3 py-2.5 text-center">
                        {rank != null ? (
                          <span className={cn(
                            'font-mono text-xs font-semibold',
                            rank <= 10 ? 'text-emerald-600 dark:text-emerald-400' :
                            rank <= 30 ? 'text-yellow-600 dark:text-yellow-400' :
                            'text-gray-500',
                          )}>
                            #{rank}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-300 dark:text-gray-600">—</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-3 py-2.5 text-center">
                    <span className="inline-flex items-center gap-1.5">
                      <span className={cn('h-2 w-2 rounded-full', dot)} />
                      <span className="text-[10px] capitalize text-gray-500 dark:text-gray-400">
                        {kw.opportunity_priority}
                      </span>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length > 100 && (
          <div className="border-t border-gray-200 px-4 py-3 text-center text-xs text-gray-400 dark:border-gray-800 dark:text-gray-500">
            Showing 100 of {filtered.length} keywords
          </div>
        )}
      </div>
    </div>
  );
}

// ── Helper: resolve numeric IDs → AppListItem stubs ─────────────────────────

async function resolveAppIds(ids: number[]): Promise<AppListItem[]> {
  const items: AppListItem[] = [];
  // Fetch each app's detail (parallel); we only need id/name/icon for chips
  const results = await Promise.allSettled(ids.map((id) => getAppDetail(id)));
  for (const r of results) {
    if (r.status === 'fulfilled') {
      const d = r.value;
      items.push({
        id: d.id,
        app_id: d.app_id,
        name: d.name,
        icon_url: d.icon_url ?? null,
        developer: d.developer ?? null,
        primary_category: d.primary_category ?? null,
        current_rating: d.current_rating ?? null,
        current_reviews: d.current_reviews ?? 0,
        current_rank: d.current_rank ?? null,
        is_free: d.is_free ?? true,
        price: d.price ?? 0,
        estimated_installs_min: null,
        estimated_installs_max: null,
        estimated_revenue_monthly_min: null,
        install_confidence: null,
        release_date: null,
      });
    }
  }
  return items;
}

// ── Inner component (uses useSearchParams) ──────────────────────────────────

function CompetitorsInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [selected, setSelected] = useState<AppListItem[]>([]);
  const [result, setResult] = useState<CompetitorCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initRef = useRef(false);

  // On mount: read ids from URL (?ids=) or localStorage store, resolve them, auto-compare
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    async function init() {
      const urlIdsRaw = searchParams.get('ids');
      let ids: number[] = [];

      if (urlIdsRaw) {
        ids = urlIdsRaw
          .split(',')
          .map((s) => parseInt(s.trim(), 10))
          .filter((n) => !isNaN(n) && n > 0);
      }

      if (ids.length === 0) {
        ids = getComparisonIds();
      }

      // De-duplicate, cap at 5
      ids = Array.from(new Set(ids)).slice(0, 5);

      if (ids.length === 0) {
        setInitializing(false);
        return;
      }

      // Sync to store
      setComparisonIds(ids);

      // Resolve ids to display info
      const apps = await resolveAppIds(ids);
      setSelected(apps);

      // Auto-compare if >= 2
      if (apps.length >= 2) {
        setLoading(true);
        try {
          const data = await compareCompetitors(apps.map((a) => a.id));
          setResult(data);
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Comparison failed');
        } finally {
          setLoading(false);
        }
      }

      setInitializing(false);
    }

    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync URL when selection changes (skip during initialization)
  useEffect(() => {
    if (initializing) return;
    const ids = selected.map((s) => s.id);
    setComparisonIds(ids);
    const idsParam = ids.length > 0 ? ids.join(',') : '';
    const currentIds = searchParams.get('ids') ?? '';
    if (idsParam !== currentIds) {
      router.replace(idsParam ? `/competitors?ids=${idsParam}` : '/competitors', { scroll: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, initializing]);

  function handleAdd(app: AppListItem) {
    if (selected.length >= 5) return;
    if (selected.some((s) => s.id === app.id)) return;
    setSelected((prev) => [...prev, app]);
  }

  function handleRemove(id: number) {
    setSelected((prev) => prev.filter((s) => s.id !== id));
    // Clear result if we drop below 2
    if (selected.length - 1 < 2) {
      setResult(null);
    }
  }

  async function handleCompare() {
    if (selected.length < 2) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await compareCompetitors(selected.map((s) => s.id));
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Comparison failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
          <Users className="h-6 w-6 text-indigo-500" />
          Competitors
        </h1>
        <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
          Compare apps side-by-side: metrics, keywords, and feature gaps
        </p>
      </div>

      {/* App picker */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
        <p className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
          Select 2–5 apps to compare
        </p>
        {initializing ? (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading apps…
          </div>
        ) : (
          <AppPicker selected={selected} onAdd={handleAdd} onRemove={handleRemove} />
        )}

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleCompare}
            disabled={selected.length < 2 || loading || initializing}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              selected.length >= 2 && !initializing
                ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed dark:bg-gray-800 dark:text-gray-500',
            )}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <GitCompare className="h-4 w-4" />
            )}
            Compare
          </button>
          {!initializing && selected.length > 0 && selected.length < 2 && (
            <span className="text-xs text-gray-400">Add at least one more app</span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-8">
          <ComparisonMatrix data={result} />
          <RankTrajectoryChart appIds={result.apps.map((a) => a.app_id)} />
          <KeywordGapSection appIds={selected.map((s) => s.id)} />
          <KeywordOverlapSection data={result} />
          <FeatureGapsSection data={result} />
        </div>
      )}

      {/* Empty state (no selection yet, no result) */}
      {!result && !loading && !initializing && selected.length === 0 && (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/50 p-12 text-center dark:border-gray-700 dark:bg-gray-900/30">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 dark:bg-indigo-950/40">
            <GitCompare className="h-8 w-8 text-indigo-500" />
          </div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Side-by-Side Comparison
          </h2>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            Search and select 2–5 apps above, or use the <GitCompare className="inline h-3.5 w-3.5" /> button on any app page to add it here.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Exported wrapper (Suspense boundary for useSearchParams) ────────────────

export default function CompetitorsClient() {
  return (
    <ErrorBoundary>
      <AppShell>
        <Suspense
          fallback={
            <div className="space-y-6">
              <div className="h-8 w-48 animate-pulse rounded bg-gray-200 dark:bg-gray-800" />
              <div className="h-40 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800" />
            </div>
          }
        >
          <CompetitorsInner />
        </Suspense>
      </AppShell>
    </ErrorBoundary>
  );
}
