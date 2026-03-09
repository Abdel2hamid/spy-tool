'use client';

import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { OpportunityOfDayCard } from '@/components/OpportunityOfDayCard';
import { SimpleChart } from '@/components/Charts';
import { OpportunityOfDay, KeywordOpportunity } from '@/lib/api';
import { Search, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface OpportunitiesClientProps {
  initialOpportunity: OpportunityOfDay | null;
  initialKeywordOpps: KeywordOpportunity[];
}

export default function OpportunitiesClient({ 
  initialOpportunity, 
  initialKeywordOpps 
}: OpportunitiesClientProps) {
  const opportunity = initialOpportunity;
  const keywordOpportunities = Array.isArray(initialKeywordOpps) ? initialKeywordOpps : [];

  const chartData = keywordOpportunities.map((kw) => ({
    name: (kw.keyword || '').slice(0, 12),
    score: kw.opportunity_score || 0,
    difficulty: kw.difficulty || 0,
  }));

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
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Top Keyword Opportunities
              </h3>
              <Search className="h-5 w-5 text-gray-400" />
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

          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Opportunity Score Distribution
              </h3>
              <BarChart3 className="h-5 w-5 text-gray-400" />
            </div>
            {chartData.length > 0 ? (
              <SimpleChart
                data={chartData}
                dataKey="score"
                xAxisKey="name"
                type="bar"
                color="#10b981"
                height={250}
              />
            ) : (
              <div className="flex h-[250px] items-center justify-center text-gray-400">
                No data available
              </div>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              All Keyword Opportunities
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="pb-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Keyword
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Search Volume
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Difficulty
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Trend
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Score
                  </th>
                  <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Apps
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {keywordOpportunities.map((kw) => (
                  <tr key={kw.keyword} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="py-3 font-medium text-gray-900 dark:text-white">
                      {kw.keyword || 'N/A'}
                    </td>
                    <td className="py-3 text-right text-gray-600 dark:text-gray-300">
                      {(kw.search_volume || 0).toLocaleString()}
                    </td>
                    <td className="py-3 text-right">
                      <span
                        className={cn(
                          'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
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
                    <td className="py-3 text-right">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 text-sm font-medium',
                          (kw.trend || 0) > 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-red-600 dark:text-red-400'
                        )}
                      >
                        {(kw.trend || 0) > 0 ? '+' : ''}
                        {(kw.trend || 0).toFixed(1)}
                      </span>
                    </td>
                    <td className="py-3 text-right font-semibold text-gray-900 dark:text-white">
                      {(kw.opportunity_score || 0).toFixed(0)}
                    </td>
                    <td className="py-3 text-right text-gray-600 dark:text-gray-300">
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
