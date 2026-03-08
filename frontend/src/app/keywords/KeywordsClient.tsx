'use client';

import { useState } from 'react';
import { AppShell } from '@/components';
import { SimpleChart } from '@/components/Charts';
import { Keyword, KeywordOpportunity } from '@/lib/api';
import { Search, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface KeywordsClientProps {
  initialKeywords: Keyword[];
  initialKeywordOpps: KeywordOpportunity[];
}

export default function KeywordsClient({ 
  initialKeywords, 
  initialKeywordOpps 
}: KeywordsClientProps) {
  const [keywords] = useState<Keyword[]>(initialKeywords || []);
  const [keywordOpps] = useState<KeywordOpportunity[]>(initialKeywordOpps || []);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'opportunities'>('all');

  const filteredKeywords = (keywords || []).filter((kw) =>
    (kw.term || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const chartData = (keywordOpps || []).slice(0, 10).map((kw) => ({
    name: (kw.keyword || '').slice(0, 12),
    trend: kw.trend || 0,
    difficulty: kw.difficulty || 0,
  }));

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Keywords</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Track keyword performance and discover opportunities
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900 lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Keyword Trends
              </h3>
              <BarChart3 className="h-5 w-5 text-gray-400" />
            </div>
            {chartData.length > 0 ? (
              <SimpleChart
                data={chartData}
                dataKey="trend"
                xAxisKey="name"
                type="line"
                color="#8b5cf6"
                height={200}
              />
            ) : (
              <div className="flex h-[200px] items-center justify-center text-gray-400">
                No data available
              </div>
            )}
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Top Opportunities
            </h3>
            <div className="space-y-3">
              {(keywordOpps || []).slice(0, 5).map((kw, i) => (
                <div
                  key={kw.keyword || i}
                  className="flex items-center justify-between rounded-lg bg-gray-50 p-2 dark:bg-gray-800"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400">
                      {i + 1}
                    </span>
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {kw.keyword || 'N/A'}
                    </span>
                  </div>
                  <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                    {(kw.opportunity_score || 0).toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search keywords..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-800 dark:bg-gray-900 dark:text-white"
            />
          </div>
          <div className="flex rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-800 dark:bg-gray-900">
            <button
              onClick={() => setActiveTab('all')}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                activeTab === 'all'
                  ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                  : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
              )}
            >
              All Keywords
            </button>
            <button
              onClick={() => setActiveTab('opportunities')}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                activeTab === 'opportunities'
                  ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                  : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
              )}
            >
              Opportunities
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
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
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {(activeTab === 'all' ? filteredKeywords : keywordOpps).map((kw) => {
                  const kwTerm = 'keyword' in kw ? kw.keyword : kw.term;
                  const kwTrend = 'trend' in kw ? kw.trend : 0;
                  const kwVolume = 'search_volume' in kw ? kw.search_volume : 0;
                  const kwDifficulty = 'difficulty' in kw ? kw.difficulty : 0;

                  return (
                    <tr key={kwTerm} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-3 font-medium text-gray-900 dark:text-white">
                        {kwTerm || 'N/A'}
                      </td>
                      <td className="py-3 text-right text-gray-600 dark:text-gray-300">
                        {kwVolume.toLocaleString()}
                      </td>
                      <td className="py-3 text-right">
                        <span
                          className={cn(
                            'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
                            kwDifficulty < 40
                              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
                              : kwDifficulty < 70
                              ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400'
                          )}
                        >
                          {kwDifficulty.toFixed(0)}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 text-sm font-medium',
                            kwTrend > 0
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : kwTrend < 0
                              ? 'text-red-600 dark:text-red-400'
                              : 'text-gray-500 dark:text-gray-400'
                          )}
                        >
                          {kwTrend > 0 ? (
                            <TrendingUp className="h-3 w-3" />
                          ) : kwTrend < 0 ? (
                            <TrendingDown className="h-3 w-3" />
                          ) : null}
                          {Math.abs(kwTrend).toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
