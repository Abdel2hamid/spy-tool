'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { AppShell, StatsCard } from '@/components';
import {
  getDashboardStats,
  getTrendingApps,
  getOpportunityOfDay,
  getDashboardKeywordHighlights,
  getBlowingUpApps,
  getTrendingKeywords,
  getIdeas,
  DashboardStats,
  TrendingApp,
  OpportunityOfDayWrapper,
  DashboardKeywordHighlight,
  BlowingUpApp,
  TrendingKeywordItem,
  AppIdea,
} from '@/lib/api';
import {
  AppWindow,
  Search,
  TrendingUp,
  Target,
  RefreshCw,
  ArrowRight,
  Zap,
  TrendingDown,
  Flame,
  Lightbulb,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/* ── Skeleton ────────────────────────────────────────────────── */
function Skeleton({ className = '' }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800', className)} />;
}

/* ── Compact Opportunity Banner ──────────────────────────────── */
function OpportunityBanner({ opp }: { opp: OpportunityOfDayWrapper | null }) {
  if (!opp || opp.status !== 'success' || !opp.item) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
        <Zap className="h-4 w-4 text-gray-300 dark:text-gray-600" />
        <p className="text-sm text-gray-400 dark:text-gray-500">
          {opp?.message || 'No opportunity yet — keep tracking apps'}
        </p>
      </div>
    );
  }

  const o = opp.item;
  const scores = [
    { label: 'Competition', value: o.competition_score, invert: true },
    { label: 'Trend', value: o.trend_score },
    { label: 'Success', value: o.success_probability },
  ];

  return (
    <Link href="/opportunities" className="block">
      <div className="group relative overflow-hidden rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-5 py-4 text-white shadow-sm transition-shadow hover:shadow-md">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs text-indigo-200">
              <Zap className="h-3.5 w-3.5 text-yellow-300" />
              Opportunity of the Day
            </div>
            <p className="mt-1 truncate text-base font-bold">{o.app_name}</p>
            <p className="truncate text-xs text-indigo-200">
              {o.primary_keyword}
              {o.category && (
                <span className="ml-1.5 rounded bg-white/15 px-1.5 py-0.5 text-[10px]">{o.category}</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {scores.map((s) => {
              const v = Math.round(s.value || 0);
              const good = s.invert ? v < 30 : v >= 60;
              const mid = s.invert ? v < 60 : v >= 40;
              return (
                <div key={s.label} className="text-center">
                  <p className="text-[10px] text-indigo-200">{s.label}</p>
                  <p className={cn('text-lg font-bold', good ? 'text-emerald-300' : mid ? 'text-amber-300' : 'text-red-300')}>
                    {v}%
                  </p>
                </div>
              );
            })}
            <ArrowRight className="ml-1 h-4 w-4 text-indigo-200 opacity-0 transition-opacity group-hover:opacity-100" />
          </div>
        </div>
        {o.ai_summary && (
          <p className="mt-2 line-clamp-1 text-xs text-indigo-100/80">{o.ai_summary}</p>
        )}
      </div>
    </Link>
  );
}

/* ── Compact Trending Row ────────────────────────────────────── */
function TrendingRow({ app, rank }: { app: TrendingApp; rank: number }) {
  const up = (app.momentum_7d || 0) > 0;
  const score = app.trend_score ?? 0;

  return (
    <Link
      href={`/apps/${app.id}`}
      className="group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
    >
      <span className="flex h-5 w-5 items-center justify-center text-xs font-bold text-gray-400">{rank}</span>
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800">
        {app.icon_url ? (
          <img src={app.icon_url} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="text-sm font-bold text-gray-400">{(app.name || '?')[0]}</span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{app.name}</p>
        <p className="truncate text-xs text-gray-400">{app.developer}</p>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="text-gray-400">#{app.current_rank ?? '-'}</span>
        <span className={cn('flex items-center gap-0.5 font-medium', up ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500')}>
          {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
          {Math.abs(app.momentum_7d || 0).toFixed(1)}
        </span>
        <span className={cn(
          'min-w-[2rem] text-right font-bold',
          score > 50 ? 'text-emerald-600 dark:text-emerald-400' : score > 25 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-400',
        )}>
          {score.toFixed(0)}
        </span>
      </div>
    </Link>
  );
}

/* ── Keyword Row ─────────────────────────────────────────────── */
function KeywordRow({ kw, rank }: { kw: DashboardKeywordHighlight; rank: number }) {
  const opp = Math.round(kw.opportunity_score);
  const vol = Math.round(kw.volume_score || kw.search_volume);
  const diff = Math.round(kw.difficulty_v2);
  const oppColor = opp >= 60 ? 'text-emerald-600 dark:text-emerald-400' : opp >= 40 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-500';
  const diffColor = diff <= 30 ? 'text-emerald-600 dark:text-emerald-400' : diff <= 60 ? 'text-amber-600 dark:text-amber-400' : 'text-red-500';

  return (
    <Link
      href="/keywords"
      className="group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
    >
      <span className="flex h-5 w-5 items-center justify-center text-xs font-bold text-gray-400">{rank}</span>
      <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900 dark:text-white">{kw.term}</span>
      <div className="flex items-center gap-4 text-xs tabular-nums">
        <span className="w-8 text-right text-gray-500">{vol}</span>
        <span className={cn('w-8 text-right', diffColor)}>{diff}</span>
        <span className={cn('w-8 text-right font-semibold', oppColor)}>{opp}</span>
      </div>
    </Link>
  );
}

/* ── Blowing Up Row ──────────────────────────────────────────── */
function BlowingUpRow({ app, rank }: { app: BlowingUpApp; rank: number }) {
  const score = app.blowing_up_score ?? 0;
  return (
    <Link
      href={`/apps/${app.id}`}
      className="group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
    >
      <span className="flex h-5 w-5 items-center justify-center text-xs font-bold text-gray-400">{rank}</span>
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800">
        {app.icon_url ? (
          <img src={app.icon_url} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="text-sm font-bold text-gray-400">{(app.name || '?')[0]}</span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{app.name}</p>
        <div className="flex items-center gap-2 text-[10px] text-gray-400">
          {app.rank_change !== 0 && (
            <span className={cn(app.rank_change < 0 ? 'text-emerald-500' : 'text-red-400')}>
              {app.rank_change < 0 ? '+' : ''}{Math.abs(app.rank_change)} ranks
            </span>
          )}
          {app.primary_category && <span>{app.primary_category}</span>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {app.badges && app.badges.length > 0 && (
          <span className="rounded bg-orange-50 px-1.5 py-0.5 text-[10px] font-medium text-orange-600 dark:bg-orange-950/30 dark:text-orange-400">
            {app.badges[0]}
          </span>
        )}
        <span className={cn(
          'min-w-[2rem] text-right text-sm font-bold',
          score > 70 ? 'text-orange-500' : score > 40 ? 'text-amber-500' : 'text-gray-400',
        )}>
          {score.toFixed(0)}
        </span>
      </div>
    </Link>
  );
}

/* ── Rising Keyword Row ──────────────────────────────────────── */
function RisingKeywordRow({ kw, rank }: { kw: TrendingKeywordItem; rank: number }) {
  const growth = kw.trend_growth ?? 0;
  const opp = Math.round(kw.opportunity_score ?? 0);
  const cls = kw.classification;
  const clsColor = cls === 'easy' ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-400'
    : cls === 'medium' ? 'text-amber-600 bg-amber-50 dark:bg-amber-950/30 dark:text-amber-400'
    : 'text-red-600 bg-red-50 dark:bg-red-950/30 dark:text-red-400';

  return (
    <Link
      href="/keywords"
      className="group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
    >
      <span className="flex h-5 w-5 items-center justify-center text-xs font-bold text-gray-400">{rank}</span>
      <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900 dark:text-white">{kw.term}</span>
      <div className="flex items-center gap-2 text-xs">
        <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium capitalize', clsColor)}>{cls}</span>
        <span className={cn('font-medium', growth > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-400')}>
          {growth > 0 ? '+' : ''}{growth.toFixed(0)}%
        </span>
        <span className="min-w-[1.5rem] text-right font-semibold text-gray-600 dark:text-gray-300">{opp}</span>
      </div>
    </Link>
  );
}

/* ── App Idea Row ────────────────────────────────────────────── */
function IdeaRow({ idea, rank }: { idea: AppIdea; rank: number }) {
  const score = idea.opportunity_score ?? 0;
  const typeLabel = idea.pattern_type === 'feature_gap' ? 'Feature Gap'
    : idea.pattern_type === 'weak_market' ? 'Weak Market'
    : 'Keyword Gap';
  const typeColor = idea.pattern_type === 'feature_gap' ? 'text-blue-600 bg-blue-50 dark:bg-blue-950/30 dark:text-blue-400'
    : idea.pattern_type === 'weak_market' ? 'text-purple-600 bg-purple-50 dark:bg-purple-950/30 dark:text-purple-400'
    : 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-400';

  return (
    <Link
      href="/ideas"
      className="group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
    >
      <span className="flex h-5 w-5 items-center justify-center text-xs font-bold text-gray-400">{rank}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{idea.idea_title}</p>
        {idea.category && <p className="truncate text-[10px] text-gray-400">{idea.category}</p>}
      </div>
      <div className="flex items-center gap-2">
        <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', typeColor)}>{typeLabel}</span>
        <span className={cn(
          'min-w-[2rem] text-right text-sm font-bold',
          score >= 70 ? 'text-emerald-600 dark:text-emerald-400' : score >= 40 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-400',
        )}>
          {score.toFixed(0)}
        </span>
      </div>
    </Link>
  );
}

/* ── Section Card Wrapper ────────────────────────────────────── */
function SectionCard({
  title,
  icon: Icon,
  href,
  headerRight,
  children,
  emptyState,
  isEmpty,
}: {
  title: string;
  icon: typeof TrendingUp;
  href: string;
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  emptyState?: React.ReactNode;
  isEmpty?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-gray-800">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <Icon className="h-4 w-4 text-indigo-500" />
          {title}
        </h3>
        <div className="flex items-center gap-3">
          {headerRight}
          <Link
            href={href}
            className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
      {isEmpty ? emptyState : children}
    </div>
  );
}

function EmptyBlock({ icon: Icon, text }: { icon: typeof Search; text: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <Icon className="h-7 w-7 text-gray-300 dark:text-gray-600" />
      <p className="text-xs text-gray-400">{text}</p>
    </div>
  );
}

/* ── Main Dashboard ──────────────────────────────────────────── */
export default function DashboardClient() {
  const [stats, setStats] = useState<DashboardStats>({ total_apps_tracked: 0, total_keywords: 0, trending_apps_count: 0, opportunities_count: 0 });
  const [trendingApps, setTrendingApps] = useState<TrendingApp[]>([]);
  const [opportunity, setOpportunity] = useState<OpportunityOfDayWrapper | null>(null);
  const [keywords, setKeywords] = useState<DashboardKeywordHighlight[]>([]);
  const [blowingUp, setBlowingUp] = useState<BlowingUpApp[]>([]);
  const [risingKw, setRisingKw] = useState<TrendingKeywordItem[]>([]);
  const [ideas, setIdeas] = useState<AppIdea[]>([]);

  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingTrending, setLoadingTrending] = useState(true);
  const [loadingOpp, setLoadingOpp] = useState(true);
  const [loadingKw, setLoadingKw] = useState(true);
  const [loadingBlowing, setLoadingBlowing] = useState(true);
  const [loadingRising, setLoadingRising] = useState(true);
  const [loadingIdeas, setLoadingIdeas] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetch_ = (setter: (v: boolean) => void, fn: () => Promise<unknown>) => {
    setter(true);
    return fn().catch((e) => console.error('[Dashboard]', e)).finally(() => setter(false));
  };

  function fetchAll(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    Promise.all([
      fetch_(setLoadingStats, () => getDashboardStats().then(setStats)),
      fetch_(setLoadingTrending, () => getTrendingApps(6).then(setTrendingApps)),
      fetch_(setLoadingOpp, () => getOpportunityOfDay().then(setOpportunity)),
      fetch_(setLoadingKw, () => getDashboardKeywordHighlights().then(setKeywords)),
      fetch_(setLoadingBlowing, () => getBlowingUpApps({ limit: 5 }).then((r) => setBlowingUp(r.items || []))),
      fetch_(setLoadingRising, () => getTrendingKeywords(5).then((r) => setRisingKw(r.keywords || []))),
      fetch_(setLoadingIdeas, () => getIdeas({ limit: 4, sort_by: 'opportunity_score', sort_order: 'desc' }).then((r) => setIdeas(r.ideas || []))),
    ]).finally(() => { if (isRefresh) setRefreshing(false); });
  }

  useEffect(() => { fetchAll(); }, []);

  const hasKw = keywords.length > 0 && keywords.some((k) => k.opportunity_score > 0 || k.volume_score > 0);

  return (
    <AppShell>
      <div className="space-y-5">
        {/* ── Header ──────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
            </p>
          </div>
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {/* ── Stats Row ───────────────────────────────────────── */}
        {loadingStats ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatsCard title="Apps Tracked" value={stats.total_apps_tracked.toLocaleString()} icon={AppWindow} description="Total apps monitored" accent="indigo" />
            <StatsCard title="Keywords" value={stats.total_keywords.toLocaleString()} icon={Search} description="Tracked keywords" accent="purple" />
            <StatsCard title="Trending Now" value={String(stats.trending_apps_count)} icon={TrendingUp} description="Positive velocity" accent="emerald" />
            <StatsCard title="Opportunities" value={stats.opportunities_count.toLocaleString()} icon={Target} description="Identified" accent="amber" />
          </div>
        )}

        {/* ── Opportunity Banner ──────────────────────────────── */}
        {loadingOpp ? <Skeleton className="h-20" /> : <OpportunityBanner opp={opportunity} />}

        {/* ── Row 1: Trending Apps + Blowing Up ───────────────── */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {loadingTrending ? <Skeleton className="h-80" /> : (
            <SectionCard title="Trending Apps" icon={TrendingUp} href="/trending" isEmpty={trendingApps.length === 0} emptyState={<EmptyBlock icon={TrendingUp} text="No trending data yet" />}>
              <div className="divide-y divide-gray-50 dark:divide-gray-800/50">
                {trendingApps.slice(0, 5).map((app, i) => <TrendingRow key={app.id} app={app} rank={i + 1} />)}
              </div>
            </SectionCard>
          )}
          {loadingBlowing ? <Skeleton className="h-80" /> : (
            <SectionCard title="Blowing Up" icon={Flame} href="/blowing-up" isEmpty={blowingUp.length === 0} emptyState={<EmptyBlock icon={Flame} text="No momentum data yet" />}>
              <div className="divide-y divide-gray-50 dark:divide-gray-800/50">
                {blowingUp.slice(0, 5).map((app, i) => <BlowingUpRow key={app.id} app={app} rank={i + 1} />)}
              </div>
            </SectionCard>
          )}
        </div>

        {/* ── Row 2: Top Keywords + Rising Keywords ───────────── */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {loadingKw ? <Skeleton className="h-72" /> : (
            <SectionCard
              title="Top Keywords"
              icon={Search}
              href="/keywords"
              isEmpty={!hasKw}
              emptyState={<EmptyBlock icon={Search} text="No keyword data yet" />}
              headerRight={
                <div className="hidden items-center gap-4 text-[10px] font-semibold uppercase text-gray-400 sm:flex">
                  <span className="w-8 text-right">Vol</span>
                  <span className="w-8 text-right">Diff</span>
                  <span className="w-8 text-right">Opp</span>
                </div>
              }
            >
              <div className="divide-y divide-gray-50 dark:divide-gray-800/50">
                {keywords.slice(0, 5).map((kw, i) => <KeywordRow key={kw.term} kw={kw} rank={i + 1} />)}
              </div>
            </SectionCard>
          )}
          {loadingRising ? <Skeleton className="h-72" /> : (
            <SectionCard title="Rising Keywords" icon={Sparkles} href="/keywords" isEmpty={risingKw.length === 0} emptyState={<EmptyBlock icon={Sparkles} text="No rising keywords yet" />}>
              <div className="divide-y divide-gray-50 dark:divide-gray-800/50">
                {risingKw.slice(0, 5).map((kw, i) => <RisingKeywordRow key={kw.id} kw={kw} rank={i + 1} />)}
              </div>
            </SectionCard>
          )}
        </div>

        {/* ── Row 3: App Ideas (full width, compact) ──────────── */}
        {loadingIdeas ? <Skeleton className="h-52" /> : ideas.length > 0 && (
          <SectionCard title="App Ideas" icon={Lightbulb} href="/ideas" isEmpty={ideas.length === 0} emptyState={<EmptyBlock icon={Lightbulb} text="No ideas generated yet" />}>
            <div className="divide-y divide-gray-50 dark:divide-gray-800/50">
              {ideas.slice(0, 4).map((idea, i) => <IdeaRow key={idea.id} idea={idea} rank={i + 1} />)}
            </div>
          </SectionCard>
        )}
      </div>
    </AppShell>
  );
}
