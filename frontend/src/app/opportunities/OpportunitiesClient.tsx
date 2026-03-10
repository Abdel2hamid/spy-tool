'use client';

import { useState, useEffect } from 'react';
import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { OpportunityOfDayCard } from '@/components/OpportunityOfDayCard';
import { SimpleChart } from '@/components/Charts';
import { OpportunityOfDay, KeywordOpportunity, getOpportunityOfDay, getKeywordOpportunities } from '@/lib/api';
import { Search, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function OpportunitiesClient() {
  const [opportunity, setOpportunity] = useState<OpportunityOfDay | null>(null);
  const [keywordOpportunities, setKeywordOpportunities] = useState<KeywordOpportunity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const [opp, kwOpps] = await Promise.all([
        getOpportunityOfDay().catch(() => null),
        getKeywordOpportunities().then((r) => (Array.isArray(r) ? r : [])).catch(() => []),
      ]);
      setOpportunity(opp ?? null);
      setKeywordOpportunities(kwOpps);
      setLoading(false);
    }
    fetchData();
  }, []);

  const chartData = keywordOpportunities.map((kw) => ({
    name: (kw.keyword || '').slice(0, 12),
    score: kw.opportunity_score || 0,
    difficulty: kw.difficulty || 0,
  }));

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="h-8 w-48 animate-pulse rounded bg-gray-200 dark:bg-gray-800" />
          <div className="h-48 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
            <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <ErrorBoundary>
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Opportunities</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            AI-scored app ideas with high success probability
          </p>
        </div>

        {opportunity && (
          <div>
            <OpportunityOfDayCard opportunity={opportunity} />
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="section-heading">Top Keyword Opportunities</h3>
              <Search className="h-4 w-4 text-gray-400" />
            </div>
            <div className="space-y-3">
              {keywordOpportunities.slice(0, 5).map((kw, i) => (
                <div
                  key={kw.keyword || i}
                  className="flex items-center justify-between rounded-lg bg-gray-50 p-3 dark:bg-gray-800"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400">
                      {i + 1}
                    </span>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {kw.keyword || 'N/A'}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-500 dark:text-gray-400">
                      {(kw.search_volume || 0).toLocaleString()} vol
                    </span>
                    <span
                      className={cn(
                        'font-semibold',
                        (kw.opportunity_score || 0) > 60
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : (kw.opportunity_score || 0) > 40
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-gray-500 dark:text-gray-400'
                      )}
                    >
                      {(kw.opportunity_score || 0).toFixed(0)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="section-heading">Score Distribution</h3>
              <BarChart3 className="h-4 w-4 text-gray-400" />
            </div>
            {chartData.length > 0 ? (
              <SimpleChart
                data={chartData}
                dataKey="score"
                xAxisKey="name"
                type="bar"
                color="#10b981"
                height={220}
              />
            ) : (
              <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
                <BarChart3 className="h-8 w-8 text-gray-300 dark:text-gray-600" />
                <p className="text-sm text-gray-400 dark:text-gray-500">No data available</p>
              </div>
            )}
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-800">
            <h3 className="section-heading">All Keyword Opportunities</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th className="text-right">Search Volume</th>
                  <th className="text-right">Difficulty</th>
                  <th className="text-right">Trend</th>
                  <th className="text-right">Score</th>
                  <th className="text-right">Apps</th>
                </tr>
              </thead>
              <tbody>
                {keywordOpportunities.map((kw) => (
                  <tr key={kw.keyword}>
                    <td className="font-medium text-gray-900 dark:text-white">
                      {kw.keyword || 'N/A'}
                    </td>
                    <td className="text-right text-gray-600 dark:text-gray-300">
                      {(kw.search_volume || 0).toLocaleString()}
                    </td>
                    <td className="text-right">
                      <span
                        className={cn(
                          'pill',
                          (kw.difficulty || 0) < 40
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
                            : (kw.difficulty || 0) < 70
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
                            : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400'
                        )}
                      >
                        {(kw.difficulty || 0).toFixed(0)}
                      </span>
                    </td>
                    <td className="text-right">
                      <span
                        className={cn(
                          'text-sm font-medium',
                          (kw.trend || 0) > 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-red-600 dark:text-red-400'
                        )}
                      >
                        {(kw.trend || 0) > 0 ? '+' : ''}
                        {(kw.trend || 0).toFixed(1)}
                      </span>
                    </td>
                    <td className="text-right font-semibold text-gray-900 dark:text-white">
                      {(kw.opportunity_score || 0).toFixed(0)}
                    </td>
                    <td className="text-right text-gray-600 dark:text-gray-300">
                      {kw.current_apps || 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
    </ErrorBoundary>
  );
}
