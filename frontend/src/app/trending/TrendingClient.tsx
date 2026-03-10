'use client';

import { useState, useEffect } from 'react';
import { AppShell } from '@/components';
import { TrendingAppCard } from '@/components/TrendingAppCard';
import { TrendingApp, getTrendingApps } from '@/lib/api';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { TrendingUp, Search } from 'lucide-react';

export default function TrendingClient() {
  const [apps, setApps] = useState<TrendingApp[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTrendingApps(20)
      .then((data) => setApps(Array.isArray(data) ? data : []))
      .catch(() => setApps([]))
      .finally(() => setLoading(false));
  }, []);

  const filteredApps = apps.filter((app) =>
    (app.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (app.developer || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <ErrorBoundary>
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Trending Apps</h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              Apps with the highest rank velocity and growth
            </p>
          </div>
          {!loading && apps.length > 0 && (
            <span className="pill bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400 self-start sm:self-auto">
              {filteredApps.length} app{filteredApps.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Search */}
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search apps or developers…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-800 dark:bg-gray-900 dark:text-white"
          />
        </div>

        {/* Content */}
        {loading ? (
          <div className="space-y-2.5">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
            ))}
          </div>
        ) : filteredApps.length > 0 ? (
          <div className="space-y-2.5">
            {filteredApps.map((app) => (
              <TrendingAppCard key={app.id} app={app} />
            ))}
          </div>
        ) : (
          <div className="card p-10 text-center">
            <TrendingUp className="mx-auto mb-3 h-10 w-10 text-gray-300 dark:text-gray-700" />
            <p className="font-medium text-gray-500 dark:text-gray-400">
              {searchQuery ? 'No apps match your search' : 'No trending apps found'}
            </p>
            {!searchQuery && (
              <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                Velocity data builds up after multiple scraping cycles
              </p>
            )}
          </div>
        )}
      </div>
    </AppShell>
    </ErrorBoundary>
  );
}
