'use client';

import { useState, useEffect } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetSystemHealth,
  adminGetDataQuality,
  adminBulkBackfill,
  AdminSystemHealth,
  DataQualityMetrics,
} from '@/lib/api';
import {
  Database,
  Server,
  Activity,
  Search,
  BarChart3,
  Clock,
  RefreshCw,
  Download,
  Globe,
  TrendingUp,
  MessageSquare,
  Smartphone,
} from 'lucide-react';

export default function AdminSystemPage() {
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [quality, setQuality] = useState<DataQualityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [backfilling, setBackfilling] = useState(false);
  const [backfillResult, setBackfillResult] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([
      adminGetSystemHealth().catch(() => null),
      adminGetDataQuality().catch(() => null),
    ])
      .then(([h, q]) => {
        setHealth(h);
        setQuality(q);
      })
      .finally(() => setLoading(false));
  }

  async function handleBackfill() {
    setBackfilling(true);
    setBackfillResult(null);
    try {
      const res = await adminBulkBackfill(1000);
      setBackfillResult(res.message + ` (${res.total_incomplete} incomplete)`);
    } catch {
      setBackfillResult('Failed to start backfill');
    } finally {
      setBackfilling(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <AdminShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">System Health</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Database, infrastructure, and data quality monitoring</p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : !health ? (
          <div className="flex items-center justify-center h-48">
            <p className="text-sm text-red-500">Failed to load system health</p>
          </div>
        ) : (
          <>
            {/* Status indicator */}
            <div className="rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-900 dark:bg-green-950/50">
              <div className="flex items-center gap-3">
                <span className="h-3 w-3 rounded-full bg-green-400 animate-pulse" />
                <span className="text-sm font-semibold text-green-700 dark:text-green-400">{health.uptime_info}</span>
                <span className="text-xs text-green-600 dark:text-green-500">All systems operational</span>
              </div>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {[
                { label: 'Database Size', value: `${health.db_size_mb} MB`, icon: Database, color: 'text-blue-600 bg-blue-50 dark:bg-blue-950' },
                { label: 'Total Tables', value: String(health.total_tables), icon: Server, color: 'text-purple-600 bg-purple-50 dark:bg-purple-950' },
                { label: 'Apps in DB', value: health.app_count.toLocaleString(), icon: Activity, color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-950' },
                { label: 'Keywords', value: health.keyword_count.toLocaleString(), icon: Search, color: 'text-orange-600 bg-orange-50 dark:bg-orange-950' },
                { label: 'Reviews', value: health.review_count.toLocaleString(), icon: BarChart3, color: 'text-pink-600 bg-pink-50 dark:bg-pink-950' },
                { label: 'Pending Queue', value: health.pending_queue.toLocaleString(), icon: Clock, color: health.pending_queue > 0 ? 'text-amber-600 bg-amber-50 dark:bg-amber-950' : 'text-green-600 bg-green-50 dark:bg-green-950' },
              ].map((it) => {
                const Icon = it.icon;
                return (
                  <div key={it.label} className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                    <div className={`inline-flex rounded-lg p-2 ${it.color} mb-3`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">{it.value}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{it.label}</p>
                  </div>
                );
              })}
            </div>

            {/* Data quality section */}
            {quality && (
              <>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white pt-2">Data Quality</h2>

                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  {[
                    {
                      label: 'Total Apps',
                      value: quality.apps.total.toLocaleString(),
                      sub: `${quality.apps.enriched_last_24h.toLocaleString()} enriched (24h)`,
                      icon: Smartphone,
                      color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-950',
                    },
                    {
                      label: 'Countries Enabled',
                      value: quality.countries.enabled.toLocaleString(),
                      sub: 'Storefronts tracked',
                      icon: Globe,
                      color: 'text-blue-600 bg-blue-50 dark:bg-blue-950',
                    },
                    {
                      label: 'Rankings (24h)',
                      value: quality.rankings.total_last_24h.toLocaleString(),
                      sub: quality.rankings.age_hours != null
                        ? `newest ${quality.rankings.age_hours}h ago`
                        : 'no data',
                      icon: TrendingUp,
                      color: quality.rankings.age_hours != null && quality.rankings.age_hours < 6
                        ? 'text-green-600 bg-green-50 dark:bg-green-950'
                        : 'text-amber-600 bg-amber-50 dark:bg-amber-950',
                    },
                    {
                      label: 'Total Reviews',
                      value: quality.reviews.total.toLocaleString(),
                      sub: `${quality.reviews.by_storefront.length} storefront(s)`,
                      icon: MessageSquare,
                      color: 'text-pink-600 bg-pink-50 dark:bg-pink-950',
                    },
                  ].map((it) => {
                    const Icon = it.icon;
                    return (
                      <div key={it.label} className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                        <div className={`inline-flex rounded-lg p-2 ${it.color} mb-3`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <p className="text-2xl font-bold text-gray-900 dark:text-white">{it.value}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{it.label}</p>
                        <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">{it.sub}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  {/* Ranking freshness by country */}
                  <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Ranking Freshness by Country</h3>
                    {quality.rankings.countries.length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400">No ranking data yet.</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full text-sm">
                          <thead>
                            <tr className="border-b border-gray-100 dark:border-gray-800 text-left text-xs text-gray-500 dark:text-gray-400">
                              <th className="pb-2 font-medium">Country</th>
                              <th className="pb-2 font-medium">Apps</th>
                              <th className="pb-2 font-medium">Latest</th>
                            </tr>
                          </thead>
                          <tbody>
                            {quality.rankings.countries
                              .sort((a, b) => (a.age_hours ?? Infinity) - (b.age_hours ?? Infinity))
                              .map((c) => (
                                <tr key={c.country} className="border-b border-gray-50 dark:border-gray-800/50 last:border-0">
                                  <td className="py-2 font-medium text-gray-900 dark:text-white uppercase">{c.country}</td>
                                  <td className="py-2 text-gray-600 dark:text-gray-400">{c.distinct_apps.toLocaleString()}</td>
                                  <td className="py-2">
                                    <span className={`text-xs ${c.age_hours != null && c.age_hours < 6 ? 'text-green-600 dark:text-green-400' : c.age_hours != null && c.age_hours < 24 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>
                                      {c.age_hours != null ? `${c.age_hours}h ago` : '—'}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Review coverage by storefront */}
                  <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Review Coverage by Storefront</h3>
                    {quality.reviews.by_storefront.length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400">No review data yet.</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full text-sm">
                          <thead>
                            <tr className="border-b border-gray-100 dark:border-gray-800 text-left text-xs text-gray-500 dark:text-gray-400">
                              <th className="pb-2 font-medium">Storefront</th>
                              <th className="pb-2 font-medium">Reviews</th>
                              <th className="pb-2 font-medium">Apps</th>
                            </tr>
                          </thead>
                          <tbody>
                            {quality.reviews.by_storefront
                              .slice()
                              .sort((a, b) => b.count - a.count)
                              .map((r) => {
                                const apps = quality.reviews.apps_by_storefront.find((a) => a.storefront === r.storefront);
                                return (
                                  <tr key={r.storefront} className="border-b border-gray-50 dark:border-gray-800/50 last:border-0">
                                    <td className="py-2 font-medium text-gray-900 dark:text-white uppercase">{r.storefront}</td>
                                    <td className="py-2 text-gray-600 dark:text-gray-400">{r.count.toLocaleString()}</td>
                                    <td className="py-2 text-gray-600 dark:text-gray-400">{apps?.count.toLocaleString() ?? '—'}</td>
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* Bulk Backfill */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Bulk Backfill Missing Data</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Fetch descriptions, ratings, and metadata for apps missing data using iTunes batch API.
                  </p>
                  {backfillResult && (
                    <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-1">{backfillResult}</p>
                  )}
                </div>
                <button
                  onClick={handleBackfill}
                  disabled={backfilling}
                  className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {backfilling ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  {backfilling ? 'Running...' : 'Run Backfill'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </AdminShell>
  );
}
