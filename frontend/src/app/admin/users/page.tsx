'use client';

import { useState, useEffect, useCallback } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetUsers,
  adminUpdateUser,
  adminDeleteUser,
  AdminUserItem,
} from '@/lib/api';
import {
  Search,
  Trash2,
  RefreshCw,
  UserCheck,
  UserX,
  Shield,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const limit = 20;

  const load = useCallback(() => {
    setLoading(true);
    adminGetUsers(search || undefined, page * limit, limit)
      .then((d) => { setUsers(d.users); setTotal(d.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [search, page]);

  useEffect(() => { load(); }, [load]);

  async function toggleActive(u: AdminUserItem) {
    await adminUpdateUser(u.id, { is_active: !u.is_active });
    load();
  }

  async function toggleSuperadmin(u: AdminUserItem) {
    await adminUpdateUser(u.id, { is_superadmin: !u.is_superadmin });
    load();
  }

  async function handleDelete(u: AdminUserItem) {
    if (!confirm(`Delete user ${u.email}? This cannot be undone.`)) return;
    await adminDeleteUser(u.id);
    load();
  }

  const totalPages = Math.ceil(total / limit);

  return (
    <AdminShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Users</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Manage all platform users</p>
        </div>

        {/* Search */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search by email or name..."
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
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">User</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Workspace</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Plan</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Joined</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto" /></td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-400">No users found</td></tr>
              ) : users.map((u) => (
                <tr key={u.id} className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                        {(u.full_name?.[0] || u.email[0]).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">{u.full_name || '—'}</p>
                        <p className="text-xs text-gray-400">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-300">{u.workspace_name || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.plan_code === 'pro' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300' :
                      u.plan_code === 'enterprise' ? 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300' :
                      u.plan_code === 'starter' ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300' :
                      'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                    }`}>
                      {u.plan_code || 'none'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${u.is_active ? 'bg-green-400' : 'bg-red-400'}`} />
                      <span className="text-xs text-gray-500">{u.is_active ? 'Active' : 'Inactive'}</span>
                      {u.is_superadmin && (
                        <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600 dark:bg-red-950 dark:text-red-400">
                          ADMIN
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => toggleActive(u)}
                        title={u.is_active ? 'Deactivate' : 'Activate'}
                        className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
                      >
                        {u.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                      </button>
                      <button
                        onClick={() => toggleSuperadmin(u)}
                        title={u.is_superadmin ? 'Remove admin' : 'Make admin'}
                        className={`rounded p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 ${u.is_superadmin ? 'text-red-500' : 'text-gray-400 hover:text-gray-600'}`}
                      >
                        <Shield className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(u)}
                        title="Delete user"
                        className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
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
      </div>
    </AdminShell>
  );
}
