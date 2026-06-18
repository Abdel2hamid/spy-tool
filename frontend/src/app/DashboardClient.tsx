'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { AppShell, StatsCard, TrendingAppCard, OpportunityOfDayCard } from '@/components';
import { SimpleChart } from '@/components/Charts';
import {
  getDashboardStats,
  getTrendingApps,
  getOpportunityOfDay,
  getDashboardKeywordHighlights,
  DashboardStats,
  TrendingApp,
  OpportunityOfDayWrapper,
  DashboardKeywordHighlight,
} from '@/lib/api';
import {
  AppWindow,
  Search,
  TrendingUp,
  Target,
  BarChart3,
  RefreshCw,
  ArrowRight,
  Lightbulb,
  Plus,
  Compass,
  Users,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';

function SectionSkeleton({ height = 'h-52' }: { height?: string }) {
  return <div className={`${height} animate-pulse rounded-2xl bg-gray-200 dark:bg-gray-800`} />;
}

function SectionHeader({
  icon: Icon,
  title,
  href,
  linkText = 'View all',
}: {
  icon: typeof BarChart3;
  title: string;
  href: string;
  linkText?: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900 dark:text-white">
        <Icon className="h-4.5 w-4.5 text-indigo-500" />
        {title}
      </h2>
      <Link
        href={href}
        className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
      >
        {linkText} <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

/** Mini keyword row for the dashboard highlights table */
function KeywordHighlightRow({
  kw,
  rank,
}: {
  kw: DashboardKeywordHighlight;
  rank: number;
}) {
  const opp = Math.round(kw.opportunity_score);
  const vol = Math.round(kw.volume_score || kw.search_volume);
  const diff = Math.round(kw.difficulty_v2);
  const oppColor =
    opp >= 60
      ? 'text-emerald-600 dark:text-emerald-400'
      : opp >= 40
      ? 'text-amber-600 dark:text-amber-400'
      : 'text-gray-500';
  const diffColor =
    diff <= 30
      ? 'text-emerald-600 dark:text-emerald-400'
      : diff <= 60
      ? 'text-amber-600 dark:text-amber-400'
      : 'text-red-500';

  return (
    <Link
      href={`/keywords`}
      className="group flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
    >
      <span className="flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold text-gray-400 dark:text-gray-500">
        {rank}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900 dark:text-white">
        {kw.term}
      </span>
      <div className="flex items-center gap-4 text-xs tabular-nums">
        <div className="w-8 text-right">
          <span className="text-gray-500">{vol}</span>
        </div>
        <div className="w-8 text-right">
          <span className={diffColor}>{diff}</span>
        </div>
        <div className="w-8 text-right">
          <span className={cn('font-semibold', oppColor)}>{opp}</span>
        </div>
      </div>
    </Link>
  );
}

export default function DashboardClient() {
  const [stats, setStats] = useState<DashboardStats>({
    total_apps_tracked: 0,
    total_keywords: 0,
    trending_apps_count: 0,
    opportunities_count: 0,
  });
  const [trendingApps, setTrendingApps] = useState<TrendingApp[]>([]);
  const [opportunity, setOpportunity] = useState<OpportunityOfDayWrapper | null>(null);
  const [keywords, setKeywords] = useState<DashboardKeywordHighlight[]>([]);

  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingTrending, setLoadingTrending] = useState(true);
  const [loadingOpportunity, setLoadingOpportunity] = useState(true);
  const [loadingKeywords, setLoadingKeywords] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  function fetchStats() {
    setLoadingStats(true);
    return getDashboardStats()
      .then(setStats)
      .catch((e) => console.error('[Dashboard] stats fetch failed:', e))
      .finally(() => setLoadingStats(false));
  }

  function fetchTrending() {
    setLoadingTrending(true);
    return getTrendingApps(5)
      .then(setTrendingApps)
      .catch((e) => console.error('[Dashboard] trending fetch failed:', e))
      .finally(() => setLoadingTrending(false));
  }

  function fetchOpportunity() {
    setLoadingOpportunity(true);
    return getOpportunityOfDay()
      .then(setOpportunity)
      .catch((e) => console.error('[Dashboard] opportunity fetch failed:', e))
      .finally(() => setLoadingOpportunity(false));
  }

  function fetchKeywords() {
    setLoadingKeywords(true);
    return getDashboardKeywordHighlights()
      .then(setKeywords)
      .catch((e) => console.error('[Dashboard] keywords fetch failed:', e))
      .finally(() => setLoadingKeywords(false));
  }

  function fetchAll(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    Promise.all([fetchStats(), fetchTrending(), fetchOpportunity(), fetchKeywords()]).finally(
      () => {
        if (isRefresh) setRefreshing(false);
      },
    );
  }

  useEffect(() => {
    fetchStats();
    fetchTrending();
    fetchOpportunity();
    fetchKeywords();
  }, []);

  const hasKeywordData = keywords.length > 0 && keywords.some((k) => k.opportunity_score > 0 || k.volume_score > 0);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              {new Date().toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/apps"
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <Plus className="h-4 w-4" />
              Add App
            </Link>
            <button
              onClick={() => fetchAll(true)}
              disabled={refreshing}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
            >
              <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* ── Stats Row ───────────────────────────────────────────── */}
        {loadingStats ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-28 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800"
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatsCard
              title="Apps Tracked"
              value={stats?.total_apps_tracked?.toLocaleString() || '0'}
              icon={AppWindow}
              description="Total apps being monitored"
              accent="indigo"
            />
            <StatsCard
              title="Keywords"
              value={stats?.total_keywords?.toLocaleString() || '0'}
              icon={Search}
              description="Tracked keywords"
              accent="purple"
            />
            <StatsCard
              title="Trending Now"
              value={String(trendingApps.length)}
              icon={TrendingUp}
              description="Apps with positive velocity"
              accent="emerald"
            />
            <StatsCard
              title="Opportunities"
              value={stats?.opportunities_count?.toLocaleString() || '0'}
              icon={Target}
              description="Identified opportunities"
              accent="amber"
            />
          </div>
        )}

        {/* ── Quick Actions ───────────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { href: '/keywords', icon: Search, label: 'Explore Keywords', color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-950/30' },
            { href: '/trending', icon: TrendingUp, label: 'Trending Apps', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/30' },
            { href: '/competitors', icon: Users, label: 'Compare Apps', color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-950/30' },
            { href: '/opportunities', icon: Zap, label: 'Opportunities', color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/30' },
          ].map(({ href, icon: Icon, label, color, bg }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-2.5 rounded-xl border border-transparent p-3 text-sm font-medium transition-all hover:border-gray-200 hover:shadow-sm dark:hover:border-gray-700',
                bg,
              )}
            >
              <Icon className={cn('h-4.5 w-4.5', color)} />
              <span className="text-gray-700 dark:text-gray-300">{label}</span>
            </Link>
          ))}
        </div>

        {/* ── Opportunity + Trending (2-col on desktop) ────────────── */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          {/* Opportunity of the Day — wider */}
          <div className="lg:col-span-3">
            <div className="mb-3">
              <SectionHeader
                icon={Lightbulb}
                title="Opportunity of the Day"
                href="/opportunities"
              />
            </div>
            {loadingOpportunity ? (
              <SectionSkeleton height="h-72" />
            ) : opportunity && opportunity.status === 'success' && opportunity.item ? (
              <OpportunityOfDayCard opportunity={opportunity.item} />
            ) : (
              <div className="flex h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-gray-50 text-center dark:border-gray-700 dark:bg-gray-900">
                <Lightbulb className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  No opportunity yet
                </p>
                <p className="mt-1 text-xs text-gray-400">
                  {opportunity?.message || 'Keep tracking apps to generate insights'}
                </p>
              </div>
            )}
          </div>

          {/* Trending Apps — narrower */}
          <div className="lg:col-span-2">
            <div className="mb-3">
              <SectionHeader icon={TrendingUp} title="Trending Apps" href="/trending" />
            </div>
            {loadingTrending ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div
                    key={i}
                    className="h-20 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800"
                  />
                ))}
              </div>
            ) : trendingApps.length > 0 ? (
              <div className="space-y-2.5">
                {trendingApps.slice(0, 4).map((app) => (
                  <TrendingAppCard key={app.id} app={app} />
                ))}
              </div>
            ) : (
              <div className="flex h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-gray-50 text-center dark:border-gray-700 dark:bg-gray-900">
                <TrendingUp className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  No trending apps yet
                </p>
                <p className="mt-1 text-xs text-gray-400">
                  Velocity data builds after multiple scraping cycles
                </p>
                <Link
                  href="/apps"
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
                >
                  Browse tracked apps <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* ── Keyword Intelligence (table + chart) ─────────────────── */}
        <section>
          <div className="mb-3">
            <SectionHeader icon={BarChart3} title="Keyword Intelligence" href="/keywords" />
          </div>
          {loadingKeywords ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <SectionSkeleton height="h-80" />
              <SectionSkeleton height="h-80" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {/* Top keywords mini-table */}
              <div className="card overflow-hidden">
                <div className="border-b border-gray-100 px-4 py-3 dark:border-gray-800">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Top Keywords by Opportunity
                  </p>
                </div>
                {hasKeywordData ? (
                  <>
                    <div className="flex items-center gap-3 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                      <span className="w-5" />
                      <span className="min-w-0 flex-1">Keyword</span>
                      <div className="flex items-center gap-4">
                        <span className="w-8 text-right">Vol</span>
                        <span className="w-8 text-right">Diff</span>
                        <span className="w-8 text-right">Opp</span>
                      </div>
                    </div>
                    <div className="divide-y divide-gray-50 dark:divide-gray-800/50">
                      {keywords.slice(0, 8).map((kw, i) => (
                        <KeywordHighlightRow key={kw.term} kw={kw} rank={i + 1} />
                      ))}
                    </div>
                    <div className="border-t border-gray-100 px-4 py-2 dark:border-gray-800">
                      <Link
                        href="/keywords"
                        className="text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
                      >
                        View all keywords →
                      </Link>
                    </div>
                  </>
                ) : (
                  <div className="flex h-64 flex-col items-center justify-center gap-2 px-6 text-center">
                    <Search className="h-8 w-8 text-gray-300 dark:text-gray-600" />
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      No keyword data yet
                    </p>
                    <p className="text-xs text-gray-300 dark:text-gray-600">
                      Track apps to discover keyword opportunities
                    </p>
                  </div>
                )}
              </div>

              {/* Opportunity chart */}
              <div className="card p-6">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                    Opportunity Scores
                  </p>
                  <BarChart3 className="h-4 w-4 text-gray-400" />
                </div>
                {hasKeywordData ? (
                  <SimpleChart
                    data={keywords.map((kw) => ({
                      name: kw.term?.slice(0, 10) || 'N/A',
                      opportunity: kw.opportunity_score || 0,
                      volume: kw.volume_score || kw.search_volume || 0,
                    }))}
                    dataKey="opportunity"
                    xAxisKey="name"
                    type="bar"
                    color="#8b5cf6"
                    height={280}
                  />
                ) : (
                  <div className="flex h-[280px] flex-col items-center justify-center gap-2 text-center">
                    <BarChart3 className="h-8 w-8 text-gray-300 dark:text-gray-600" />
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      No keyword data yet
                    </p>
                    <p className="text-xs text-gray-300 dark:text-gray-600">
                      Track apps to discover keyword opportunities
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
