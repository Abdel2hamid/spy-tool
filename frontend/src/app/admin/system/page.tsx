'use client';

import { useState, useEffect } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetSystemHealth,
  AdminSystemHealth,
} from '@/lib/api';
import {
  Database,
  Server,
  Activity,
  Search,
  BarChart3,
  Clock,
  RefreshCw,
} from 'lucide-react';

export default function AdminSystemPage() {
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    adminGetSystemHealth()
      .then(setHealth)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  return (
    <AdminShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">System Health</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Database and infrastructure monitoring</p>
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
          </>
        )}
      </div>
    </AdminShell>
  );
}
