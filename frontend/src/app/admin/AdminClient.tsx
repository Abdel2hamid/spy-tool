'use client';

import { useState, useEffect } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetDashboard,
  AdminDashboardStats,
} from '@/lib/api';
import {
  Users,
  Building2,
  Search,
  RefreshCw,
  UserCheck,
  Activity,
  BarChart3,
} from 'lucide-react';

export default function AdminClient() {
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminGetDashboard()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <AdminShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Overview of platform activity</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : !stats ? (
          <div className="flex items-center justify-center h-48">
            <p className="text-sm text-red-500">Failed to load dashboard</p>
          </div>
        ) : (
          <>
            {/* Stat cards */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {[
                { label: 'Total Users', value: stats.total_users, icon: Users, color: 'text-blue-600 bg-blue-50 dark:bg-blue-950' },
                { label: 'Active Users', value: stats.active_users, icon: UserCheck, color: 'text-green-600 bg-green-50 dark:bg-green-950' },
                { label: 'Workspaces', value: stats.total_workspaces, icon: Building2, color: 'text-purple-600 bg-purple-50 dark:bg-purple-950' },
                { label: 'Apps Tracked', value: stats.total_apps, icon: Activity, color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-950' },
                { label: 'Keywords', value: stats.total_keywords, icon: Search, color: 'text-orange-600 bg-orange-50 dark:bg-orange-950' },
                { label: 'Reviews', value: stats.total_reviews, icon: BarChart3, color: 'text-pink-600 bg-pink-50 dark:bg-pink-950' },
              ].map((c) => {
                const Icon = c.icon;
                return (
                  <div key={c.label} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
                    <div className={`inline-flex rounded-lg p-2 ${c.color}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">{c.value.toLocaleString()}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{c.label}</p>
                  </div>
                );
              })}
            </div>

            {/* Plans + Usage */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Plans</h3>
                <div className="space-y-2">
                  {Object.entries(stats.plans).length === 0 && (
                    <p className="text-sm text-gray-400">No subscriptions yet</p>
                  )}
                  {Object.entries(stats.plans).map(([plan, count]) => (
                    <div key={plan} className="flex items-center justify-between">
                      <span className="text-sm capitalize text-gray-600 dark:text-gray-300">{plan}</span>
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                        {count}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Usage This Month</h3>
                <div className="space-y-2">
                  {Object.entries(stats.usage_this_month).map(([key, val]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-300">{key.replace(/_/g, ' ')}</span>
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                        {val.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AdminShell>
  );
}
