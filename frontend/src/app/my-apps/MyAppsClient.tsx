'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import { getMyApps, removeMyApp, MyAppItem } from '@/lib/api';
import {
  Star,
  TrendingUp,
  MessageSquare,
  Search,
  Trash2,
  ArrowRight,
  Zap,
  ChevronRight,
  Crown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

function ASOScoreRing({ score, size = 44 }: { score: number; size?: number }) {
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(score, 100));
  const offset = circ - (pct / 100) * circ;
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#3b82f6' : score >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <svg width={size} height={size} className="flex-shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" className="text-gray-200 dark:text-gray-700" strokeWidth={4} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4} strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" textAnchor="middle" dy=".35em" className="fill-gray-900 dark:fill-white text-[11px] font-bold">{score}</text>
    </svg>
  );
}

function MyAppCard({ app, onRemove }: { app: MyAppItem; onRemove: (id: number) => void }) {
  const grade = app.aso_grade || 'F';
  const score = Math.round(app.aso_score ?? 0);

  return (
    <div className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition hover:shadow-sm dark:border-gray-800 dark:bg-gray-900">
      {/* Icon */}
      <Link href={`/my-apps/${app.app_id}`} className="flex-shrink-0">
        {app.icon_url ? (
          <img src={app.icon_url} alt="" className="h-14 w-14 rounded-xl object-cover shadow-sm ring-1 ring-black/5 dark:ring-white/10" />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
            <span className="text-xl font-bold text-white">{(app.name || '?')[0]}</span>
          </div>
        )}
      </Link>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <Link href={`/my-apps/${app.app_id}`} className="group">
          <h3 className="truncate text-sm font-semibold text-gray-900 group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-400">
            {app.name}
          </h3>
        </Link>
        <p className="truncate text-xs text-gray-500 dark:text-gray-400">
          {app.developer || 'Unknown developer'}
          {app.primary_category && ` · ${app.primary_category}`}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-gray-400">
          {app.current_rating != null && (
            <span className="flex items-center gap-0.5">
              <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" /> {app.current_rating.toFixed(1)}
            </span>
          )}
          {app.current_reviews != null && app.current_reviews > 0 && (
            <span className="flex items-center gap-0.5">
              <MessageSquare className="h-3 w-3" /> {app.current_reviews.toLocaleString()}
            </span>
          )}
          {app.current_rank != null && (
            <span className="flex items-center gap-0.5">
              <TrendingUp className="h-3 w-3" /> #{app.current_rank}
            </span>
          )}
        </div>
      </div>

      {/* ASO Score */}
      <div className="flex-shrink-0 text-center">
        <ASOScoreRing score={score} size={44} />
        <p className={cn(
          'mt-0.5 text-[10px] font-bold',
          score >= 60 ? 'text-emerald-600' : score >= 40 ? 'text-amber-600' : 'text-red-500',
        )}>
          {grade}
        </p>
      </div>

      {/* Actions */}
      <div className="flex flex-shrink-0 items-center gap-1.5">
        <button
          onClick={(e) => { e.preventDefault(); onRemove(app.app_id); }}
          title="Remove from My Apps"
          className="rounded-lg p-2 text-gray-300 transition hover:bg-red-50 hover:text-red-500 dark:text-gray-600 dark:hover:bg-red-950/30 dark:hover:text-red-400"
        >
          <Trash2 className="h-4 w-4" />
        </button>
        <Link
          href={`/my-apps/${app.app_id}`}
          className="rounded-lg p-2 text-gray-400 transition hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-950/30 dark:hover:text-indigo-400"
          title="View details"
        >
          <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

export default function MyAppsClient() {
  const [apps, setApps] = useState<MyAppItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    getMyApps()
      .then((r) => setApps(r.apps || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleRemove(appId: number) {
    try {
      await removeMyApp(appId);
      setApps((prev) => prev.filter((a) => a.app_id !== appId));
    } catch { /* ignore */ }
  }

  const filtered = search
    ? apps.filter((a) =>
        (a.name || '').toLowerCase().includes(search.toLowerCase()) ||
        (a.developer || '').toLowerCase().includes(search.toLowerCase()),
      )
    : apps;

  return (
    <AppShell>
      <div className="space-y-5">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
              <Crown className="h-6 w-6 text-indigo-500" />
              My Apps
            </h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              {apps.length > 0
                ? `${apps.length} app${apps.length !== 1 ? 's' : ''} tracked — click any app for full ASO insights`
                : 'Track your apps for ASO health, keyword gaps, and optimization tips'}
            </p>
          </div>
          <Link href="/apps" className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 self-start sm:self-auto">
            <Search className="h-4 w-4" /> Find Apps
          </Link>
        </div>

        {/* Search */}
        {!loading && apps.length > 3 && (
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search my apps..."
              className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white dark:placeholder-gray-500"
            />
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && apps.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-gray-200 bg-gray-50 py-16 text-center dark:border-gray-700 dark:bg-gray-900">
            <Zap className="h-10 w-10 text-gray-300 dark:text-gray-600" />
            <div>
              <p className="text-base font-semibold text-gray-900 dark:text-white">No apps tracked yet</p>
              <p className="mt-1 text-sm text-gray-500">Go to any app page and click &quot;My App&quot; to start tracking</p>
            </div>
            <Link href="/apps" className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
              Browse Apps <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        )}

        {/* App list */}
        {!loading && filtered.length > 0 && (
          <div className="space-y-2">
            {filtered.map((app) => (
              <MyAppCard key={app.id} app={app} onRemove={handleRemove} />
            ))}
          </div>
        )}

        {/* No results */}
        {!loading && apps.length > 0 && filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-gray-400">No apps match &quot;{search}&quot;</p>
        )}
      </div>
    </AppShell>
  );
}
