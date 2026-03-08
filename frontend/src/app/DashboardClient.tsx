'use client';

import { useState, useEffect } from 'react';
import { AppShell, StatsCard, TrendingAppCard, OpportunityOfDayCard } from '@/components';
import { SimpleChart } from '@/components/Charts';
import {
  getDashboardStats,
  getTrendingApps,
  getOpportunityOfDay,
  getKeywords,
  DashboardStats,
  TrendingApp,
  OpportunityOfDay,
  Keyword,
} from '@/lib/api';
import { AppWindow, Search, TrendingUp, Target, BarChart3, RefreshCw } from 'lucide-react';

export default function DashboardClient() {
  const [stats, setStats] = useState<DashboardStats>({
    total_apps_tracked: 0,
    total_keywords: 0,
    trending_apps_count: 0,
    opportunities_count: 0,
  });
  const [trendingApps, setTrendingApps] = useState<TrendingApp[]>([]);
  const [opportunity, setOpportunity] = useState<OpportunityOfDay | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function fetchAll(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const [s, t, o, k] = await Promise.all([
        getDashboardStats().catch(() => ({
          total_apps_tracked: 0,
          total_keywords: 0,
          trending_apps_count: 0,
          opportunities_count: 0,
        })),
        getTrendingApps(5).catch(() => []),
        getOpportunityOfDay().catch(() => null),
        getKeywords(10).catch(() => []),
      ]);
      setStats(s);
      setTrendingApps(t);
      setOpportunity(o);
      setKeywords(k);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    fetchAll();
  }, []);

  const keywordTrendData = keywords.map((kw) => ({
    name: kw.term?.slice(0, 10) || 'N/A',
    trend: kw.trend || 0,
    volume: kw.search_volume || 0,
  }));

  const hasKeywordData = keywordTrendData.some((k) => k.trend > 0 || k.volume > 0);

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-28 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
            <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              AI-powered App Store intelligence
            </p>
          </div>
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <StatsCard
            title="Apps Tracked"
            value={stats?.total_apps_tracked?.toLocaleString() || '0'}
            icon={AppWindow}
            description="Total apps being monitored"
          />
          <StatsCard
            title="Keywords"
            value={stats?.total_keywords?.toLocaleString() || '0'}
            icon={Search}
            description="Tracked keywords"
          />
          <StatsCard
            title="Trending Now"
            value={String(trendingApps.length)}
            icon={TrendingUp}
            description="Apps with positive velocity"
          />
          <StatsCard
            title="Opportunities"
            value={stats?.opportunities_count?.toLocaleString() || '0'}
            icon={Target}
            description="Identified opportunities"
          />
        </div>

        {opportunity && (
          <div>
            <OpportunityOfDayCard opportunity={opportunity} />
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Keyword Trends
              </h3>
              <BarChart3 className="h-5 w-5 text-gray-400" />
            </div>
            {hasKeywordData ? (
              <SimpleChart
                data={keywordTrendData}
                dataKey="trend"
                xAxisKey="name"
                type="bar"
                color="#8b5cf6"
                height={250}
              />
            ) : (
              <div className="flex h-[250px] items-center justify-center text-gray-400">
                No keyword trend data yet
              </div>
            )}
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Search Volume
              </h3>
              <Search className="h-5 w-5 text-gray-400" />
            </div>
            {hasKeywordData ? (
              <SimpleChart
                data={keywordTrendData}
                dataKey="volume"
                xAxisKey="name"
                type="area"
                color="#06b6d4"
                height={250}
              />
            ) : (
              <div className="flex h-[250px] items-center justify-center text-gray-400">
                No search volume data yet
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Top Trending Apps
            </h3>
            <TrendingUp className="h-5 w-5 text-gray-400" />
          </div>
          <div className="space-y-3">
            {trendingApps.length > 0 ? (
              trendingApps.map((app) => (
                <TrendingAppCard key={app.id} app={app} />
              ))
            ) : (
              <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
                <TrendingUp className="mx-auto mb-4 h-12 w-12 text-gray-300 dark:text-gray-600" />
                <p className="text-gray-500 dark:text-gray-400">No trending apps found</p>
                <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                  Velocity data builds up after multiple scraping cycles
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
