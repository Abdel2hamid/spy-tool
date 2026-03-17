export const dynamic = 'force-dynamic';

import { AppShell } from '@/components';
import { Bell, TrendingUp, Search, Zap, Star } from 'lucide-react';

export default function AlertsPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
            <Bell className="h-6 w-6 text-amber-500" />
            Alerts
          </h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
            Get notified when apps trend, keywords rise, or new opportunities emerge
          </p>
        </div>

        {/* Coming soon card */}
        <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/50 p-12 text-center dark:border-gray-700 dark:bg-gray-900/30">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-950/40">
            <Bell className="h-8 w-8 text-amber-500" />
          </div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Coming Soon</h2>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            Proactive monitoring and notifications for the signals that matter — app momentum, keyword trends, competitor moves, and new opportunities.
          </p>
        </div>

        {/* Planned alert types */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: TrendingUp,
              title: 'App Trending',
              description: 'Notify when a tracked app starts gaining unusual momentum.',
              accent: 'emerald',
            },
            {
              icon: Search,
              title: 'Keyword Rising',
              description: 'Alert when a keyword opportunity score crosses a threshold.',
              accent: 'blue',
            },
            {
              icon: Zap,
              title: 'New Opportunity',
              description: 'Alert when a new high-score niche or feature gap is detected.',
              accent: 'indigo',
            },
            {
              icon: Star,
              title: 'New Release',
              description: 'Notify when a newly released app shows early traction signals.',
              accent: 'amber',
            },
          ].map((a) => {
            const accentMap: Record<string, string> = {
              emerald: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400',
              blue: 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400',
              indigo: 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400',
              amber: 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400',
            };
            return (
              <div
                key={a.title}
                className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900"
              >
                <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-lg ${accentMap[a.accent]}`}>
                  <a.icon className="h-4 w-4" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{a.title}</h3>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{a.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
