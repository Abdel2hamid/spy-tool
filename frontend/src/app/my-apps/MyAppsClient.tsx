'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import {
  getMyApps,
  removeMyApp,
  getASOScore,
  MyAppItem,
  ASOScoreResponse,
} from '@/lib/api';
import {
  Star,
  TrendingUp,
  MessageSquare,
  Search,
  Trash2,
  ArrowRight,
  ExternalLink,
  Lightbulb,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/* ── ASO Grade helpers ───────────────────────────────────────── */
const gradeColor: Record<string, string> = {
  A: 'from-emerald-500 to-emerald-600',
  B: 'from-blue-500 to-blue-600',
  C: 'from-yellow-500 to-yellow-600',
  D: 'from-orange-500 to-orange-600',
  F: 'from-red-500 to-red-600',
};

const gradeText: Record<string, string> = {
  A: 'Excellent',
  B: 'Good',
  C: 'Needs work',
  D: 'Poor',
  F: 'Critical',
};

function ASOScoreRing({ score, size = 48 }: { score: number; size?: number }) {
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(score, 100));
  const offset = circ - (pct / 100) * circ;
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#3b82f6' : score >= 40 ? '#f59e0b' : '#ef4444';

  return (
    <svg width={size} height={size} className="flex-shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" className="text-gray-200 dark:text-gray-700" strokeWidth={4} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4} strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" textAnchor="middle" dy=".35em" className="fill-gray-900 dark:fill-white text-xs font-bold">{score}</text>
    </svg>
  );
}

function BreakdownBar({ label, score }: { label: string; score: number }) {
  const color = score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-blue-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-gray-600 dark:text-gray-400">{label}</span>
        <span className="font-medium text-gray-900 dark:text-white">{score}/100</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

/* ── App Card with ASO detail ────────────────────────────────── */
function MyAppCard({
  app,
  onRemove,
}: {
  app: MyAppItem;
  onRemove: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [aso, setAso] = useState<ASOScoreResponse | null>(null);
  const [loadingAso, setLoadingAso] = useState(false);

  async function loadASO() {
    if (aso || loadingAso) return;
    setLoadingAso(true);
    try {
      const data = await getASOScore(app.app_id);
      setAso(data);
    } catch {
      // ignore
    }
    setLoadingAso(false);
  }

  function handleExpand() {
    const next = !expanded;
    setExpanded(next);
    if (next) loadASO();
  }

  const grade = app.aso_grade || 'F';
  const score = Math.round(app.aso_score ?? 0);

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center gap-4 p-4">
        <Link href={`/apps/${app.app_id}`} className="flex-shrink-0">
          {app.icon_url ? (
            <img src={app.icon_url} alt="" className="h-14 w-14 rounded-xl object-cover shadow-sm ring-1 ring-black/5 dark:ring-white/10" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
              <span className="text-xl font-bold text-white">{(app.name || '?')[0]}</span>
            </div>
          )}
        </Link>

        <div className="min-w-0 flex-1">
          <Link href={`/apps/${app.app_id}`} className="group">
            <h3 className="truncate text-base font-semibold text-gray-900 group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-400">{app.name}</h3>
          </Link>
          <p className="truncate text-xs text-gray-500">{app.developer}</p>
          <div className="mt-1.5 flex items-center gap-3 text-xs text-gray-400">
            {app.current_rating != null && (
              <span className="flex items-center gap-0.5">
                <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                {app.current_rating.toFixed(1)}
              </span>
            )}
            {app.current_reviews != null && app.current_reviews > 0 && (
              <span className="flex items-center gap-0.5">
                <MessageSquare className="h-3 w-3" />
                {app.current_reviews.toLocaleString()}
              </span>
            )}
            {app.current_rank != null && (
              <span className="flex items-center gap-0.5">
                <TrendingUp className="h-3 w-3" />
                #{app.current_rank}
              </span>
            )}
            {app.primary_category && <span>{app.primary_category}</span>}
          </div>
        </div>

        {/* ASO score badge */}
        <div className="flex items-center gap-3">
          <div className="text-center">
            <ASOScoreRing score={score} size={48} />
            <p className={cn('mt-0.5 text-[10px] font-bold', score >= 60 ? 'text-emerald-600' : score >= 40 ? 'text-amber-600' : 'text-red-500')}>
              Grade {grade}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <button
              onClick={handleExpand}
              className="rounded-lg border border-gray-200 p-1.5 text-gray-400 hover:bg-gray-50 hover:text-gray-600 dark:border-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-300"
              title={expanded ? 'Collapse' : 'Expand ASO details'}
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            <button
              onClick={() => onRemove(app.app_id)}
              className="rounded-lg border border-gray-200 p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 dark:border-gray-700 dark:hover:bg-red-950/30 dark:hover:text-red-400"
              title="Remove from My Apps"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Expanded ASO details */}
      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50/50 p-4 dark:border-gray-800 dark:bg-gray-950/50">
          {loadingAso ? (
            <div className="flex items-center justify-center py-6">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
            </div>
          ) : aso ? (
            <div className="space-y-4">
              {/* Score header */}
              <div className={cn('flex items-center gap-3 rounded-lg bg-gradient-to-r p-3 text-white', gradeColor[grade] || gradeColor.F)}>
                <ASOScoreRing score={score} size={40} />
                <div>
                  <p className="text-sm font-bold">ASO Score: {score}/100</p>
                  <p className="text-xs opacity-80">Grade {grade} — {gradeText[grade] || 'Unknown'}</p>
                </div>
              </div>

              {/* Breakdown bars */}
              {aso.breakdown && Object.keys(aso.breakdown).length > 0 && (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {Object.entries(aso.breakdown).map(([key, item]) => (
                    <BreakdownBar key={key} label={item.label || key} score={Math.round(item.score)} />
                  ))}
                </div>
              )}

              {/* Tips */}
              {aso.tips && aso.tips.length > 0 && (
                <div>
                  <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300">
                    <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
                    Optimization Tips
                  </p>
                  <div className="space-y-1.5">
                    {aso.tips.slice(0, 5).map((tip, i) => (
                      <div key={i} className="flex items-start gap-2 rounded-lg bg-white px-3 py-2 text-xs dark:bg-gray-900">
                        <span className={cn(
                          'mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase',
                          tip.impact === 'high' ? 'bg-red-100 text-red-600 dark:bg-red-950/40 dark:text-red-400'
                            : tip.impact === 'medium' ? 'bg-amber-100 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400'
                            : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
                        )}>
                          {tip.impact}
                        </span>
                        <span className="text-gray-700 dark:text-gray-300">{tip.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Link
                href={`/apps/${app.app_id}`}
                className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
              >
                View full app details <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          ) : (
            <p className="py-4 text-center text-sm text-gray-400">Failed to load ASO data</p>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────── */
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
    } catch {
      // ignore
    }
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
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">My Apps</h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              Apps you own or manage — track ASO scores, get optimization tips
            </p>
          </div>
          <Link
            href="/apps"
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            <Search className="h-4 w-4" />
            Find Apps
          </Link>
        </div>

        {/* Search */}
        {apps.length > 0 && (
          <div className="relative">
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
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && apps.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-gray-200 bg-gray-50 py-16 text-center dark:border-gray-700 dark:bg-gray-900">
            <Star className="h-10 w-10 text-gray-300 dark:text-gray-600" />
            <div>
              <p className="text-base font-semibold text-gray-900 dark:text-white">No apps marked yet</p>
              <p className="mt-1 text-sm text-gray-500">
                Go to any app page and click the &quot;My App&quot; button to add it here
              </p>
            </div>
            <Link
              href="/apps"
              className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Browse Apps <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        )}

        {/* App cards */}
        {!loading && filtered.length > 0 && (
          <div className="space-y-3">
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
