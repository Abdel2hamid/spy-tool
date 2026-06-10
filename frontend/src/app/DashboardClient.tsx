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
import { AppWindow, Search, TrendingUp, Target, BarChart3, RefreshCw, ArrowRight, Lightbulb } from 'lucide-react';

function SectionSkeleton({ height = 'h-52' }: { height?: string }) {
  return <div className={`${height} animate-pulse rounded-2xl bg-gray-200 dark:bg-gray-800`} />;
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
    Promise.all([fetchStats(), fetchTrending(), fetchOpportunity(), fetchKeywords()])
      .finally(() => { if (isRefresh) setRefreshing(false); });
  }

  useEffect(() => {
    fetchStats();
    fetchTrending();
    fetchOpportunity();
    fetchKeywords();
  }, []);

  const keywordChartData = keywords.map((kw) => ({
    name: kw.term?.slice(0, 10) || 'N/A',
    trend: kw.trend_score || 0,
    volume: kw.search_volume || 0,
  }));

  const hasKeywordData = keywordChartData.some((k) => k.trend > 0 || k.volume > 0);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Dashboard
            </h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              AI-powered App Store intelligence — {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
            </p>
          </div>
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        {/* Stats row */}
        {loadingStats ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-28 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
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

        {/* Opportunity of the Day */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="section-heading flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-indigo-500" />
              Opportunity of the Day
            </h2>
            <Link
              href="/opportunities"
              className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
            >
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          {loadingOpportunity ? (
            <SectionSkeleton height="h-52" />
          ) : opportunity && opportunity.status === 'success' && opportunity.item ? (
            <OpportunityOfDayCard opportunity={opportunity.item} />
          ) : (
            <div className="rounded-2xl border border-dashed border-gray-200 dark:border-gray-700 p-6 text-center text-sm text-gray-500 dark:text-gray-400">
              {opportunity?.message ?? 'Not enough signals yet. Keep tracking apps to generate an opportunity.'}
            </div>
          )}
        </section>

        {/* Keyword charts */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="section-heading flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-indigo-500" />
              Keyword Intelligence
            </h2>
            <Link
              href="/keywords"
              className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
            >
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          {loadingKeywords ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <SectionSkeleton height="h-64" />
              <SectionSkeleton height="h-64" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="card p-6">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">Keyword Trends</p>
                  <BarChart3 className="h-4 w-4 text-gray-400" />
                </div>
                {hasKeywordData ? (
                  <SimpleChart
                    data={keywordChartData}
                    dataKey="trend"
                    xAxisKey="name"
                    type="bar"
                    color="#8b5cf6"
                    height={220}
                  />
                ) : (
                  <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
                    <BarChart3 className="h-8 w-8 text-gray-300 dark:text-gray-600" />
                    <p className="text-sm text-gray-400 dark:text-gray-500">No trend data yet</p>
                    <p className="text-xs text-gray-300 dark:text-gray-600">Run the keyword pipeline to populate</p>
                  </div>
                )}
              </div>

              <div className="card p-6">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">Search Volume</p>
                  <Search className="h-4 w-4 text-gray-400" />
                </div>
                {hasKeywordData ? (
                  <SimpleChart
                    data={keywordChartData}
                    dataKey="volume"
                    xAxisKey="name"
                    type="area"
                    color="#06b6d4"
                    height={220}
                  />
                ) : (
                  <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
                    <Search className="h-8 w-8 text-gray-300 dark:text-gray-600" />
                    <p className="text-sm text-gray-400 dark:text-gray-500">No volume data yet</p>
                    <p className="text-xs text-gray-300 dark:text-gray-600">Run the keyword pipeline to populate</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Trending apps */}
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="section-heading flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-indigo-500" />
              Top Trending Apps
            </h2>
            <Link
              href="/trending"
              className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
            >
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          {loadingTrending ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
              ))}
            </div>
          ) : (
            <div className="space-y-2.5">
              {trendingApps.length > 0 ? (
                trendingApps.map((app) => (
                  <TrendingAppCard key={app.id} app={app} />
                ))
              ) : (
                <div className="card p-10 text-center">
                  <TrendingUp className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-700" />
                  <p className="font-medium text-gray-500 dark:text-gray-400">No trending apps yet</p>
                  <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                    Velocity data builds up after multiple scraping cycles
                  </p>
                  <Link
                    href="/apps"
                    className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
                  >
                    Browse tracked apps <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
