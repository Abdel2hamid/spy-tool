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
  DollarSign,
  TrendingUp,
  ArrowRight,
  Zap,
  Crown,
  Trophy,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';

const PLAN_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  trial: { bg: 'bg-amber-50 dark:bg-amber-950/30', text: 'text-amber-700 dark:text-amber-400', bar: 'bg-amber-400' },
  starter: { bg: 'bg-blue-50 dark:bg-blue-950/30', text: 'text-blue-700 dark:text-blue-400', bar: 'bg-blue-500' },
  pro: { bg: 'bg-indigo-50 dark:bg-indigo-950/30', text: 'text-indigo-700 dark:text-indigo-400', bar: 'bg-indigo-500' },
  enterprise: { bg: 'bg-purple-50 dark:bg-purple-950/30', text: 'text-purple-700 dark:text-purple-400', bar: 'bg-purple-500' },
  free: { bg: 'bg-gray-50 dark:bg-gray-800/30', text: 'text-gray-600 dark:text-gray-400', bar: 'bg-gray-400' },
};

const BILLING_ACTION_LABELS: Record<string, string> = {
  'subscription.update': 'Plan Changed',
  'trial.extend': 'Trial Extended',
  'user.bulk_change_plan': 'Bulk Plan Change',
  'user.create': 'User Created',
};

function pc(plan: string) {
  return PLAN_COLORS[plan] || PLAN_COLORS.free;
}

export default function AdminClient() {
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminGetDashboard()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <AdminShell>
        <div className="flex items-center justify-center h-48">
          <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      </AdminShell>
    );
  }

  if (!stats) {
    return (
      <AdminShell>
        <div className="flex items-center justify-center h-48">
          <p className="text-sm text-red-500">Failed to load dashboard</p>
        </div>
      </AdminShell>
    );
  }

  const totalPlanCount = Object.values(stats.plans).reduce((a, b) => a + b, 0);

  return (
    <AdminShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Revenue, subscriptions, and platform activity</p>
        </div>

        {/* ── Revenue + Key Metrics Row ────────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 dark:bg-green-950/50">
                <DollarSign className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">MRR</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">${stats.revenue.mrr.toLocaleString()}</p>
              </div>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              ARR: <span className="font-semibold text-gray-700 dark:text-gray-300">${stats.revenue.arr.toLocaleString()}</span>
            </p>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/50">
                <Crown className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Paying</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.revenue.total_paying}</p>
              </div>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              of {stats.total_users} total users
            </p>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 dark:bg-amber-950/50">
                <TrendingUp className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Conversion</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.trial_funnel.conversion_rate}%</p>
              </div>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {stats.trial_funnel.converted} of {stats.trial_funnel.total_trials} trials
            </p>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 dark:bg-blue-950/50">
                <Users className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Active Users</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.active_users}</p>
              </div>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              of {stats.total_users} total
            </p>
          </div>
        </div>

        {/* ── MRR Breakdown + Plan Distribution Row ────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* MRR Breakdown */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-green-500" />
              Revenue Breakdown
            </h3>
            {Object.keys(stats.revenue.breakdown).length === 0 ? (
              <p className="text-sm text-gray-400 py-4">No paying subscribers yet</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(stats.revenue.breakdown)
                  .sort(([, a], [, b]) => b.mrr - a.mrr)
                  .map(([plan, data]) => (
                    <div key={plan} className="flex items-center gap-3">
                      <div className={`w-2 h-8 rounded-full ${pc(plan).bar}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-900 dark:text-white capitalize">{plan}</span>
                          <span className="text-sm font-bold text-gray-900 dark:text-white">${data.mrr.toLocaleString()}</span>
                        </div>
                        <div className="flex items-center justify-between mt-0.5">
                          <span className="text-xs text-gray-500">{data.count} subscribers × ${data.price}/mo</span>
                          <span className="text-xs text-gray-400">
                            {stats.revenue.mrr > 0 ? Math.round((data.mrr / stats.revenue.mrr) * 100) : 0}% of MRR
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                <div className="border-t border-gray-100 dark:border-gray-800 pt-3 mt-3 flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">Total MRR</span>
                  <span className="text-lg font-bold text-green-600 dark:text-green-400">${stats.revenue.mrr.toLocaleString()}/mo</span>
                </div>
              </div>
            )}
          </div>

          {/* Plan Distribution */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-indigo-500" />
              Plan Distribution
            </h3>
            {/* Horizontal stacked bar */}
            {totalPlanCount > 0 && (
              <div className="flex h-6 rounded-full overflow-hidden mb-4">
                {Object.entries(stats.plans)
                  .sort(([, a], [, b]) => b - a)
                  .map(([plan, count]) => (
                    <div
                      key={plan}
                      className={`${pc(plan).bar} transition-all`}
                      style={{ width: `${(count / totalPlanCount) * 100}%` }}
                      title={`${plan}: ${count}`}
                    />
                  ))}
              </div>
            )}
            <div className="space-y-2.5">
              {Object.entries(stats.plans)
                .sort(([, a], [, b]) => b - a)
                .map(([plan, count]) => (
                  <div key={plan} className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className={`h-3 w-3 rounded-full ${pc(plan).bar}`} />
                      <span className="text-sm capitalize text-gray-700 dark:text-gray-300">{plan}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-400">
                        {totalPlanCount > 0 ? Math.round((count / totalPlanCount) * 100) : 0}%
                      </span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${pc(plan).bg} ${pc(plan).text}`}>
                        {count}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>

        {/* ── Trial Conversion Funnel ──────────────────────────────────────── */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-amber-500" />
            Trial Conversion Funnel
          </h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <FunnelStep
              label="Total Trials"
              value={stats.trial_funnel.total_trials}
              color="bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
              icon={<Users className="h-4 w-4" />}
            />
            <FunnelStep
              label="Active Trials"
              value={stats.trial_funnel.active_trials}
              color="bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400"
              icon={<Clock className="h-4 w-4" />}
              subtext={stats.trial_funnel.total_trials > 0
                ? `${Math.round((stats.trial_funnel.active_trials / stats.trial_funnel.total_trials) * 100)}% of total`
                : undefined}
            />
            <FunnelStep
              label="Converted to Paid"
              value={stats.trial_funnel.converted}
              color="bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-400"
              icon={<ArrowUpRight className="h-4 w-4" />}
              subtext={`${stats.trial_funnel.conversion_rate}% conversion`}
            />
            <FunnelStep
              label="Expired"
              value={stats.trial_funnel.expired}
              color="bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400"
              icon={<ArrowDownRight className="h-4 w-4" />}
              subtext={stats.trial_funnel.total_trials > 0
                ? `${Math.round((stats.trial_funnel.expired / stats.trial_funnel.total_trials) * 100)}% lost`
                : undefined}
            />
          </div>
          {/* Visual funnel bar */}
          {stats.trial_funnel.total_trials > 0 && (
            <div className="mt-4 flex items-center gap-2">
              <div className="flex-1 h-3 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden flex">
                <div
                  className="bg-green-500 transition-all"
                  style={{ width: `${stats.trial_funnel.conversion_rate}%` }}
                  title={`Converted: ${stats.trial_funnel.conversion_rate}%`}
                />
                <div
                  className="bg-amber-400 transition-all"
                  style={{ width: `${(stats.trial_funnel.active_trials / stats.trial_funnel.total_trials) * 100}%` }}
                  title={`Still trialing`}
                />
                <div
                  className="bg-red-400 transition-all"
                  style={{ width: `${(stats.trial_funnel.expired / stats.trial_funnel.total_trials) * 100}%` }}
                  title={`Expired`}
                />
              </div>
            </div>
          )}
        </div>

        {/* ── Platform Stats + Usage Leaderboard Row ──────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Platform Stats */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Activity className="h-4 w-4 text-pink-500" />
              Platform Stats
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Apps Tracked', value: stats.total_apps, icon: Activity, color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-950/40' },
                { label: 'Keywords', value: stats.total_keywords, icon: Search, color: 'text-orange-600 bg-orange-50 dark:bg-orange-950/40' },
                { label: 'Reviews', value: stats.total_reviews, icon: BarChart3, color: 'text-pink-600 bg-pink-50 dark:bg-pink-950/40' },
                { label: 'Workspaces', value: stats.total_workspaces, icon: Building2, color: 'text-purple-600 bg-purple-50 dark:bg-purple-950/40' },
              ].map((c) => {
                const Icon = c.icon;
                return (
                  <div key={c.label} className="flex items-center gap-3 rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                    <div className={`inline-flex rounded-lg p-2 ${c.color}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-lg font-bold text-gray-900 dark:text-white">{c.value.toLocaleString()}</p>
                      <p className="text-[11px] text-gray-500 dark:text-gray-400">{c.label}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Usage this month */}
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mt-5 mb-3">Usage This Month</h4>
            <div className="space-y-2">
              {Object.entries(stats.usage_this_month).map(([key, val]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 dark:text-gray-300 capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                    {val.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Usage Leaderboard */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" />
              Top Users by Usage
              <span className="ml-auto text-[11px] font-normal text-gray-400">This month</span>
            </h3>
            {stats.usage_leaderboard.length === 0 ? (
              <p className="text-sm text-gray-400 py-4">No usage this month</p>
            ) : (
              <div className="space-y-2">
                {stats.usage_leaderboard.map((u, i) => (
                  <div
                    key={u.user_id}
                    className="flex items-center gap-3 rounded-lg border border-gray-100 p-3 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition"
                  >
                    <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold flex-shrink-0 ${
                      i === 0 ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400' :
                      i === 1 ? 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300' :
                      i === 2 ? 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-400' :
                      'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
                    }`}>
                      {i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          {u.full_name || u.email}
                        </p>
                        {u.plan_code && (
                          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium capitalize ${pc(u.plan_code).bg} ${pc(u.plan_code).text}`}>
                            {u.plan_code}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-[11px] text-gray-400">
                        <span>{u.app_imports} imports</span>
                        <span>{u.keyword_refreshes} kw</span>
                        <span>{u.ai_requests} AI</span>
                        <span>{u.exports} exp</span>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-bold text-gray-900 dark:text-white">{u.total.toLocaleString()}</p>
                      <p className="text-[10px] text-gray-400">actions</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Billing Actions Log ──────────────────────────────────────────── */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Zap className="h-4 w-4 text-violet-500" />
            Recent Billing Actions
          </h3>
          {stats.billing_log.length === 0 ? (
            <p className="text-sm text-gray-400 py-4">No billing actions yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left">
                  <tr className="border-b border-gray-100 dark:border-gray-800">
                    <th className="pb-2 font-medium text-gray-500 dark:text-gray-400 pr-4">Action</th>
                    <th className="pb-2 font-medium text-gray-500 dark:text-gray-400 pr-4">Admin</th>
                    <th className="pb-2 font-medium text-gray-500 dark:text-gray-400 pr-4">Details</th>
                    <th className="pb-2 font-medium text-gray-500 dark:text-gray-400">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                  {stats.billing_log.map((entry) => (
                    <tr key={entry.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="py-2.5 pr-4">
                        <span className="inline-block rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 dark:bg-violet-950/40 dark:text-violet-400">
                          {BILLING_ACTION_LABELS[entry.action] || entry.action}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-300">{entry.admin_email || '\u2014'}</td>
                      <td className="py-2.5 pr-4 text-gray-500 dark:text-gray-400 max-w-xs truncate">
                        {entry.details ? formatBillingDetails(entry.action, entry.details) : '\u2014'}
                      </td>
                      <td className="py-2.5 text-xs text-gray-400 whitespace-nowrap">
                        {entry.created_at ? new Date(entry.created_at).toLocaleString() : '\u2014'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function FunnelStep({
  label,
  value,
  color,
  icon,
  subtext,
}: {
  label: string;
  value: number;
  color: string;
  icon: React.ReactNode;
  subtext?: string;
}) {
  return (
    <div className={`rounded-xl p-4 ${color}`}>
      <div className="flex items-center gap-2 mb-2 opacity-70">{icon}<span className="text-xs font-medium">{label}</span></div>
      <p className="text-2xl font-bold">{value}</p>
      {subtext && <p className="text-[11px] mt-1 opacity-70">{subtext}</p>}
    </div>
  );
}

function formatBillingDetails(action: string, details: Record<string, unknown>): string {
  if (action === 'subscription.update') {
    const parts: string[] = [];
    if (details.plan_code) parts.push(`plan → ${details.plan_code}`);
    if (details.status) parts.push(`status → ${details.status}`);
    return parts.join(', ') || JSON.stringify(details);
  }
  if (action === 'trial.extend') {
    return `+${details.days || '?'} days`;
  }
  if (action === 'user.bulk_change_plan') {
    return `${details.affected || '?'} users → ${details.plan_code || '?'}`;
  }
  if (action === 'user.create') {
    return `${details.email || ''} (${details.plan || 'trial'})`;
  }
  return JSON.stringify(details);
}
