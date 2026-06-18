'use client';

import { useState, useEffect, useCallback } from 'react';
import { AdminShell } from '@/components/AdminShell';
import { adminGetActivity, AdminActivityItem } from '@/lib/api';
import {
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Activity,
} from 'lucide-react';

function actionBadgeColor(action: string): string {
  if (action.startsWith('user.'))
    return 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300';
  if (action.startsWith('subscription.'))
    return 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300';
  if (action.startsWith('job.'))
    return 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300';
  if (action.startsWith('export.'))
    return 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300';
  if (action.startsWith('announcement.'))
    return 'bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300';
  return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300';
}

function actionDotColor(action: string): string {
  if (action.startsWith('user.')) return 'bg-blue-500';
  if (action.startsWith('subscription.')) return 'bg-purple-500';
  if (action.startsWith('job.')) return 'bg-green-500';
  if (action.startsWith('export.')) return 'bg-orange-500';
  if (action.startsWith('announcement.')) return 'bg-pink-500';
  return 'bg-gray-400';
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return '\u2014';
  const d = new Date(ts);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export default function AdminActivityPage() {
  const [items, setItems] = useState<AdminActivityItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const limit = 50;

  const load = useCallback(() => {
    setLoading(true);
    adminGetActivity(page * limit, limit)
      .then((d) => {
        setItems(d.activity);
        setTotal(d.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.ceil(total / limit);

  return (
    <AdminShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Activity Log
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {total} total admin actions
            </p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>

        {/* Timeline */}
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <Activity className="h-8 w-8 mb-2" />
              <p className="text-sm">No activity recorded yet</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {items.map((item) => (
                <div
                  key={item.id}
                  className="group relative flex gap-4 px-4 py-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition"
                >
                  {/* Timeline dot */}
                  <div className="flex flex-col items-center pt-1">
                    <div
                      className={`h-2.5 w-2.5 rounded-full ring-4 ring-white dark:ring-gray-900 ${actionDotColor(item.action)}`}
                    />
                    <div className="mt-1 w-px flex-1 bg-gray-200 dark:bg-gray-800 group-last:hidden" />
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${actionBadgeColor(item.action)}`}
                      >
                        {item.action}
                      </span>
                      <span className="text-xs text-gray-400">
                        {formatTimestamp(item.created_at)}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {item.admin_email || 'System'}
                      </span>
                      {item.target_type && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {item.target_type}
                          {item.target_id !== null && (
                            <span className="ml-1 font-mono text-gray-600 dark:text-gray-300">
                              #{item.target_id}
                            </span>
                          )}
                        </span>
                      )}
                    </div>

                    {/* Expandable details */}
                    {item.details &&
                      Object.keys(item.details).length > 0 && (
                        <div>
                          <button
                            onClick={() =>
                              setExpandedId(
                                expandedId === item.id ? null : item.id,
                              )
                            }
                            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
                          >
                            {expandedId === item.id ? (
                              <ChevronUp className="h-3 w-3" />
                            ) : (
                              <ChevronDown className="h-3 w-3" />
                            )}
                            Details
                          </button>
                          {expandedId === item.id && (
                            <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300 font-mono">
                              {JSON.stringify(item.details, null, 2)}
                            </pre>
                          )}
                        </div>
                      )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Page {page + 1} of {totalPages}
            </p>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="rounded-lg border p-2 text-gray-500 hover:bg-gray-50 disabled:opacity-30 dark:border-gray-700 dark:hover:bg-gray-800"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() =>
                  setPage((p) => Math.min(totalPages - 1, p + 1))
                }
                disabled={page >= totalPages - 1}
                className="rounded-lg border p-2 text-gray-500 hover:bg-gray-50 disabled:opacity-30 dark:border-gray-700 dark:hover:bg-gray-800"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </AdminShell>
  );
}
