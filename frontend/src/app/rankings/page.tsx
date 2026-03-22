'use client';

export const dynamic = 'force-dynamic';

import { useState, useEffect } from 'react';
import { AppShell } from '@/components';
import { getRankHistory, RankHistory, getApps, AppListItem } from '@/lib/api';
import { BarChart3, TrendingUp, Search } from 'lucide-react';
import { RankHistoryChart } from '@/components/Charts';

function RankingsContent() {
  const [apps, setApps] = useState<AppListItem[]>([]);
  const [selectedApp, setSelectedApp] = useState<number | null>(null);
  const [rankHistory, setRankHistory] = useState<RankHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [appLoading, setAppLoading] = useState(false);

  useEffect(() => {
    async function fetchApps() {
      try {
        const data = await getApps(20);
        setApps(data);
        if (data.length > 0) {
          setSelectedApp(data[0].id);
        }
      } catch (error) {
        console.error('Failed to fetch apps:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchApps();
  }, []);

  useEffect(() => {
    if (!selectedApp) return;

    async function fetchRankHistory() {
      setAppLoading(true);
      try {
        const data = await getRankHistory(selectedApp as number, 30);
        setRankHistory(data);
      } catch (error) {
        console.error('Failed to fetch rank history:', error);
        setRankHistory(null);
      } finally {
        setAppLoading(false);
      }
    }
    fetchRankHistory();
  }, [selectedApp]);

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="h-96 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Rankings</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Track app ranking movements over time
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <select
              value={selectedApp || ''}
              onChange={(e) => setSelectedApp(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-800 dark:bg-gray-900 dark:text-white"
            >
              <option value="">Select an app</option>
              {apps.map((app) => (
                <option key={app.id} value={app.id}>
                  {app.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {appLoading ? (
          <div className="h-80 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
        ) : rankHistory && rankHistory.dates.length > 0 ? (
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Rank History - {apps.find((a) => a.id === selectedApp)?.name}
              </h3>
              <BarChart3 className="h-5 w-5 text-gray-400" />
            </div>
            <RankHistoryChart dates={rankHistory.dates} ranks={rankHistory.ranks} height={350} />
            <div className="mt-4 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
              <span>Last 30 days</span>
              <span>
                {rankHistory.dates.length} data points
              </span>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
            <BarChart3 className="mx-auto mb-4 h-12 w-12 text-gray-300 dark:text-gray-600" />
            <p className="text-gray-500 dark:text-gray-400">
              {selectedApp
                ? 'No ranking data available for this app'
                : 'Select an app to view its ranking history'}
            </p>
          </div>
        )}

        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
            All Tracked Apps
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="pb-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    App
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Current Rank
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Rating
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Reviews
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {apps.map((app) => (
                  <tr
                    key={app.id}
                    className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
                    onClick={() => setSelectedApp(app.id)}
                  >
                    <td className="py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 overflow-hidden dark:bg-gray-800">
                          {app.icon_url ? (
                            <img
                              src={app.icon_url}
                              alt={app.name}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <span className="text-xs font-bold text-gray-400">
                              {app.name?.[0] || '?'}
                            </span>
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white">
                            {app.name}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {app.developer}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 text-right">
                      {app.current_rank ? (
                        <span className="inline-flex items-center rounded-full bg-indigo-100 px-2.5 py-0.5 text-sm font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                          #{app.current_rank}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="py-3 text-right text-gray-600 dark:text-gray-300">
                      {app.current_rating?.toFixed(1) || '-'}
                    </td>
                    <td className="py-3 text-right text-gray-600 dark:text-gray-300">
                      {app.current_reviews?.toLocaleString() || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default function RankingsPage() {
  return <RankingsContent />;
}
