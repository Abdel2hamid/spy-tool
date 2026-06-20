'use client';

import { useState, useEffect, useCallback } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetWorkspaces,
  adminUpdateSubscription,
  AdminWorkspaceItem,
} from '@/lib/api';
import {
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export default function AdminWorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<AdminWorkspaceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [editWs, setEditWs] = useState<AdminWorkspaceItem | null>(null);
  const [editPlan, setEditPlan] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const limit = 20;

  const load = useCallback(() => {
    setLoading(true);
    adminGetWorkspaces(search || undefined, page * limit, limit)
      .then((d) => { setWorkspaces(d.workspaces); setTotal(d.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [search, page]);

  useEffect(() => { load(); }, [load]);

  function openEdit(ws: AdminWorkspaceItem) {
    setEditWs(ws);
    setEditPlan(ws.plan_code || '');
    setEditStatus(ws.plan_status || '');
  }

  async function saveSubscription() {
    if (!editWs) return;
    await adminUpdateSubscription(editWs.id, { plan_code: editPlan, status: editStatus });
    setEditWs(null);
    load();
  }

  const totalPages = Math.ceil(total / limit);

  return (
    <AdminShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Workspaces</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Manage workspaces and subscriptions</p>
        </div>

        {/* Search */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search workspaces..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
            />
          </div>
          <span className="text-sm text-gray-500">{total} total</span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left dark:bg-gray-800/50">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Workspace</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Owner</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Members</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Plan</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Usage</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Created</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto" /></td></tr>
              ) : workspaces.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-400">No workspaces found</td></tr>
              ) : workspaces.map((ws) => (
                <tr key={ws.id} className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900 dark:text-white">{ws.name}</p>
                    <p className="text-xs text-gray-400">{ws.slug}</p>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{ws.owner_email || '—'}</td>
                  <td className="px-4 py-3 text-center text-gray-600 dark:text-gray-300">{ws.member_count}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium w-fit ${
                        ws.plan_code === 'pro' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300' :
                        ws.plan_code === 'starter' ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300' :
                        'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                      }`}>
                        {ws.plan_code || 'none'}
                      </span>
                      {ws.plan_status && (
                        <span className={`text-[10px] font-medium ${
                          ws.plan_status === 'trialing' ? 'text-amber-500' :
                          ws.plan_status === 'active' ? 'text-green-500' :
                          'text-gray-400'
                        }`}>
                          {ws.plan_status}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
                      <p>{ws.usage.app_imports} imports</p>
                      <p>{ws.usage.keyword_refreshes} keywords</p>
                      <p>{ws.usage.ai_requests} AI reqs</p>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {ws.created_at ? new Date(ws.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => openEdit(ws)}
                      className="rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950 dark:text-indigo-300 dark:hover:bg-indigo-900"
                    >
                      Edit Plan
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">Page {page + 1} of {totalPages}</p>
            <div className="flex gap-1">
              <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="rounded-lg border p-2 text-gray-500 hover:bg-gray-50 disabled:opacity-30 dark:border-gray-700 dark:hover:bg-gray-800">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="rounded-lg border p-2 text-gray-500 hover:bg-gray-50 disabled:opacity-30 dark:border-gray-700 dark:hover:bg-gray-800">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Edit subscription modal */}
        {editWs && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                Edit Subscription
              </h3>
              <p className="text-sm text-gray-500 mb-5">{editWs.name}</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">Plan</label>
                  <select
                    value={editPlan}
                    onChange={(e) => setEditPlan(e.target.value)}
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                  >
                    <option value="trial">Trial</option>
                    <option value="starter">Starter</option>
                    <option value="pro">Pro</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">Status</label>
                  <select
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value)}
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                  >
                    <option value="trialing">Trialing</option>
                    <option value="active">Active</option>
                    <option value="canceled">Canceled</option>
                    <option value="expired">Expired</option>
                  </select>
                </div>
              </div>
              <div className="mt-6 flex gap-2 justify-end">
                <button
                  onClick={() => setEditWs(null)}
                  className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  Cancel
                </button>
                <button
                  onClick={saveSubscription}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminShell>
  );
}
