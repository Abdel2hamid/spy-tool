'use client';

import { useState, useEffect, useCallback } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetTrials,
  adminExtendTrial,
  AdminTrialItem,
} from '@/lib/api';
import {
  RefreshCw,
  Clock,
  AlertTriangle,
  ChevronDown,
  CalendarPlus,
  Users,
} from 'lucide-react';

export default function AdminTrialsPage() {
  const [trials, setTrials] = useState<AdminTrialItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [extendingId, setExtendingId] = useState<number | null>(null);
  const [openDropdown, setOpenDropdown] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    adminGetTrials()
      .then((d) => {
        const sorted = [...d.trials].sort(
          (a, b) => (a.days_left ?? 0) - (b.days_left ?? 0),
        );
        setTrials(sorted);
        setTotal(d.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick() {
      setOpenDropdown(null);
    }
    if (openDropdown !== null) {
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [openDropdown]);

  async function handleExtend(workspaceId: number, days: number) {
    setExtendingId(workspaceId);
    setOpenDropdown(null);
    try {
      await adminExtendTrial(workspaceId, days);
      load();
    } catch {
      // ignore
    } finally {
      setExtendingId(null);
    }
  }

  const expiringIn3Days = trials.filter(
    (t) => t.days_left !== null && t.days_left > 0 && t.days_left <= 3,
  ).length;
  const expired = trials.filter(
    (t) => t.days_left !== null && t.days_left <= 0,
  ).length;

  function daysLeftColor(days: number | null): string {
    if (days === null) return 'text-gray-400';
    if (days <= 0) return 'text-red-600 dark:text-red-400';
    if (days < 3) return 'text-red-600 dark:text-red-400';
    if (days < 7) return 'text-amber-600 dark:text-amber-400';
    return 'text-green-600 dark:text-green-400';
  }

  function daysLeftBg(days: number | null): string {
    if (days === null) return 'bg-gray-100 dark:bg-gray-800';
    if (days <= 0) return 'bg-red-50 dark:bg-red-950/50';
    if (days < 3) return 'bg-red-50 dark:bg-red-950/50';
    if (days < 7) return 'bg-amber-50 dark:bg-amber-950/50';
    return 'bg-green-50 dark:bg-green-950/50';
  }

  return (
    <AdminShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Trial Management
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Monitor and extend workspace trials
            </p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/50">
                <Users className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {total}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Total Trials
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 dark:bg-amber-950/50">
                <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">
                  {expiringIn3Days}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Expiring in 3 Days
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50 dark:bg-red-950/50">
                <Clock className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {expired}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Expired
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left dark:bg-gray-800/50">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Workspace
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Owner
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Days Left
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Expires
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {loading ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-12 text-center text-gray-400"
                  >
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto" />
                  </td>
                </tr>
              ) : trials.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-12 text-center text-gray-400"
                  >
                    No trials found
                  </td>
                </tr>
              ) : (
                trials.map((t) => (
                  <tr
                    key={t.workspace_id}
                    className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-900 dark:text-white">
                        {t.workspace_name}
                      </p>
                      <p className="text-xs text-gray-400">
                        {t.plan_code} &middot; {t.status}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
                      {t.owner_email || '\u2014'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${daysLeftBg(t.days_left)} ${daysLeftColor(t.days_left)}`}
                      >
                        {t.days_left !== null && t.days_left > 0
                          ? `${t.days_left}d`
                          : t.days_left === 0 || (t.days_left !== null && t.days_left < 0)
                            ? 'Expired'
                            : '\u2014'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                      {t.trial_ends_at
                        ? new Date(t.trial_ends_at).toLocaleDateString()
                        : '\u2014'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="relative">
                        {extendingId === t.workspace_id ? (
                          <span className="flex items-center gap-1.5 text-xs text-gray-400">
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                            Extending...
                          </span>
                        ) : (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenDropdown(
                                  openDropdown === t.workspace_id
                                    ? null
                                    : t.workspace_id,
                                );
                              }}
                              className="flex items-center gap-1.5 rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950 dark:text-indigo-300 dark:hover:bg-indigo-900 transition"
                            >
                              <CalendarPlus className="h-3.5 w-3.5" />
                              Extend
                              <ChevronDown className="h-3 w-3" />
                            </button>
                            {openDropdown === t.workspace_id && (
                              <div
                                className="absolute right-0 top-full z-20 mt-1 w-36 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-900"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {[7, 14, 30].map((days) => (
                                  <button
                                    key={days}
                                    onClick={() =>
                                      handleExtend(t.workspace_id, days)
                                    }
                                    className="flex w-full items-center px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
                                  >
                                    +{days} days
                                  </button>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AdminShell>
  );
}
