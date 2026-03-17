export const dynamic = 'force-dynamic';

import { AppShell } from '@/components';
import { Users, ArrowRight, Search, BarChart3, GitCompare } from 'lucide-react';

export default function CompetitorsPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
            <Users className="h-6 w-6 text-indigo-500" />
            Competitors
          </h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
            Compare apps, keyword overlap, and competitive positioning
          </p>
        </div>

        {/* Coming soon card */}
        <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/50 p-12 text-center dark:border-gray-700 dark:bg-gray-900/30">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 dark:bg-indigo-950/40">
            <GitCompare className="h-8 w-8 text-indigo-500" />
          </div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Coming Soon</h2>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            Head-to-head app comparisons, shared keyword space analysis, review sentiment differences, and feature gap mapping between competing apps.
          </p>
        </div>

        {/* Planned features */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            {
              icon: Search,
              title: 'Keyword Overlap',
              description: 'See which keywords you share with competing apps and where gaps exist.',
            },
            {
              icon: BarChart3,
              title: 'Ranking Comparison',
              description: 'Compare rank trajectories for the same keywords across multiple apps.',
            },
            {
              icon: GitCompare,
              title: 'Review Analysis',
              description: 'Contrast sentiment, feature requests, and pain points across competitors.',
            },
          ].map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900"
            >
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/40">
                <f.icon className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{f.title}</h3>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
