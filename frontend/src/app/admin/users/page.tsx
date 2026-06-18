'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetUsers,
  adminCreateUser,
  adminUpdateUser,
  adminDeleteUser,
  adminResetPassword,
  adminImpersonateUser,
  adminBulkAction,
  adminExportUsersCSV,
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
  UserPlus,
  X,
  Key,
  LogIn,
  Download,
  CheckSquare,
  Square,
  Minus,
  Users,
  Clock,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Plan badge color map
// ---------------------------------------------------------------------------
const PLAN_COLORS: Record<string, string> = {
  pro: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
  enterprise: 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300',
  starter: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  trial: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
  lifetime: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
};

function planBadgeClass(plan: string | null): string {
  return PLAN_COLORS[plan ?? ''] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300';
}

const STATUS_COLORS: Record<string, string> = {
  active: 'text-green-600 dark:text-green-400',
  trialing: 'text-amber-600 dark:text-amber-400',
  canceled: 'text-red-600 dark:text-red-400',
  expired: 'text-gray-500 dark:text-gray-400',
};

type FilterTab = 'all' | 'trialing' | 'expired' | 'inactive';

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState<FilterTab>('all');
  const router = useRouter();
  const [showCreate, setShowCreate] = useState(false);
  const [resetTarget, setResetTarget] = useState<AdminUserItem | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkPlanOpen, setBulkPlanOpen] = useState(false);
  const [busyAction, setBusyAction] = useState(false);
  const limit = 20;

  // --- Summary stats ---------------------------------------------------------
  const trialingCount = users.filter((u) => u.plan_status === 'trialing').length;
  const expiringCount = users.filter(
    (u) => u.trial_days_left !== null && u.trial_days_left > 0 && u.trial_days_left <= 3,
  ).length;

  // --- Data loading ----------------------------------------------------------

  const load = useCallback(() => {
    setLoading(true);
    adminGetUsers(search || undefined, page * limit, limit, filterTab !== 'all' ? filterTab : undefined)
      .then((d) => {
        setUsers(d.users);
        setTotal(d.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [search, page, filterTab]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setSelected(new Set());
  }, [users]);

  // --- Row-level actions -----------------------------------------------------

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

  async function handleImpersonate(u: AdminUserItem) {
    try {
      const data = await adminImpersonateUser(u.id);
      sessionStorage.setItem('impersonate_token', data.token);
      window.open('/impersonate', '_blank');
    } catch {
      alert('Failed to impersonate user');
    }
  }

  // --- CSV Export -------------------------------------------------------------

  async function handleExportCSV() {
    try {
      const blob = await adminExportUsersCSV();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `users-export-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      alert('Failed to export CSV');
    }
  }

  // --- Selection helpers -----------------------------------------------------

  const selectableUsers = users.filter((u) => !u.is_superadmin);
  const allSelected = selectableUsers.length > 0 && selectableUsers.every((u) => selected.has(u.id));
  const someSelected = selectableUsers.some((u) => selected.has(u.id));

  function toggleSelectAll() {
    setSelected(allSelected ? new Set() : new Set(selectableUsers.map((u) => u.id)));
  }

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // --- Bulk actions ----------------------------------------------------------

  async function handleBulk(action: string, planCode?: string) {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    if (action === 'delete' && !confirm(`Delete ${ids.length} user(s)? This cannot be undone.`)) return;
    setBusyAction(true);
    try {
      await adminBulkAction({ user_ids: ids, action, plan_code: planCode });
      setSelected(new Set());
      load();
    } catch {
      alert(`Bulk ${action} failed`);
    } finally {
      setBusyAction(false);
      setBulkPlanOpen(false);
    }
  }

  // --- Pagination ------------------------------------------------------------

  const totalPages = Math.ceil(total / limit);

  // --- Filter tabs -----------------------------------------------------------

  const tabs: { key: FilterTab; label: string; count?: number }[] = [
    { key: 'all', label: 'All Users' },
    { key: 'trialing', label: 'Trialing', count: trialingCount },
    { key: 'expired', label: 'Expired' },
    { key: 'inactive', label: 'Inactive' },
  ];

  // --- Render ----------------------------------------------------------------

  return (
    <AdminShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Users & Accounts</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Manage users, workspaces, subscriptions, and trials
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExportCSV}
              className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition"
            >
              <UserPlus className="h-4 w-4" />
              Add User
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/50">
                <Users className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div>
                <p className="text-xl font-bold text-gray-900 dark:text-white">{total}</p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400">Total Users</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 dark:bg-amber-950/50">
                <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-xl font-bold text-amber-600 dark:text-amber-400">{trialingCount}</p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400">Trialing</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-50 dark:bg-red-950/50">
                <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <p className="text-xl font-bold text-red-600 dark:text-red-400">{expiringCount}</p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400">Expiring Soon</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-green-50 dark:bg-green-950/50">
                <UserCheck className="h-4 w-4 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-xl font-bold text-green-600 dark:text-green-400">
                  {users.filter((u) => u.is_active).length}
                </p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400">Active</p>
              </div>
            </div>
          </div>
        </div>

        {/* Search + Filter Tabs */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 overflow-x-auto">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => { setFilterTab(t.key); setPage(0); }}
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  filterTab === t.key
                    ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
                }`}
              >
                {t.label}
                {t.count !== undefined && t.count > 0 && (
                  <span className="rounded-full bg-white/60 px-1.5 py-0.5 text-[10px] font-bold dark:bg-black/30">
                    {t.count}
                  </span>
                )}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <div className="relative flex-1 sm:flex-initial sm:w-64">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search by email or name..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(0); }}
                className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <span className="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">{total} total</span>
          </div>
        </div>

        {/* Bulk action bar */}
        {selected.size > 0 && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 dark:border-indigo-900 dark:bg-indigo-950/40">
            <span className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
              {selected.size} selected
            </span>
            <div className="mx-2 h-4 w-px bg-indigo-200 dark:bg-indigo-800" />
            <button onClick={() => handleBulk('activate')} disabled={busyAction} className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 transition">Activate</button>
            <button onClick={() => handleBulk('deactivate')} disabled={busyAction} className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50 transition">Deactivate</button>
            <button onClick={() => handleBulk('delete')} disabled={busyAction} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition">Delete</button>
            <div className="relative">
              <button onClick={() => setBulkPlanOpen(!bulkPlanOpen)} disabled={busyAction} className="rounded-lg border border-indigo-300 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50 transition dark:border-indigo-700 dark:bg-gray-900 dark:text-indigo-300 dark:hover:bg-gray-800">Change Plan</button>
              {bulkPlanOpen && (
                <div className="absolute left-0 top-full z-20 mt-1 w-40 rounded-lg border border-gray-200 bg-white py-1 shadow-xl dark:border-gray-700 dark:bg-gray-900">
                  {['trial', 'starter', 'pro', 'enterprise'].map((p) => (
                    <button key={p} onClick={() => handleBulk('change_plan', p)} className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800 capitalize">{p}</button>
                  ))}
                </div>
              )}
            </div>
            {busyAction && <RefreshCw className="ml-2 h-4 w-4 animate-spin text-indigo-500" />}
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left dark:bg-gray-800/50">
              <tr>
                <th className="px-4 py-3 w-10">
                  <button onClick={toggleSelectAll} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                    {allSelected ? <CheckSquare className="h-4 w-4 text-indigo-600 dark:text-indigo-400" /> : someSelected ? <Minus className="h-4 w-4 text-indigo-400" /> : <Square className="h-4 w-4" />}
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">User</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Workspace</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Plan</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Trial</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Joined</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {loading ? (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto" /></td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-400">No users found</td></tr>
              ) : (
                users.map((u) => (
                    <tr
                      key={u.id}
                      className={`bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition cursor-pointer ${
                        selected.has(u.id) ? 'bg-indigo-50/50 dark:bg-indigo-950/20' : ''
                      }`}
                      onClick={() => router.push(`/admin/users/${u.id}`)}
                    >
                      {/* Checkbox */}
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        {u.is_superadmin ? (
                          <span className="inline-block h-4 w-4" />
                        ) : (
                          <button onClick={() => toggleSelect(u.id)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                            {selected.has(u.id) ? <CheckSquare className="h-4 w-4 text-indigo-600 dark:text-indigo-400" /> : <Square className="h-4 w-4" />}
                          </button>
                        )}
                      </td>

                      {/* User */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                            {(u.full_name?.[0] || u.email[0]).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <p className="font-medium text-gray-900 dark:text-white truncate">{u.full_name || '\u2014'}</p>
                            <p className="text-xs text-gray-400 truncate">{u.email}</p>
                          </div>
                        </div>
                      </td>

                      {/* Workspace */}
                      <td className="px-4 py-3">
                        <p className="text-gray-600 dark:text-gray-300 truncate">{u.workspace_name || '\u2014'}</p>
                        {u.workspace_slug && (
                          <p className="text-[10px] text-gray-400 truncate">{u.workspace_slug}</p>
                        )}
                      </td>

                      {/* Plan */}
                      <td className="px-4 py-3">
                        {u.is_superadmin ? (
                          <span className="inline-block rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-600 dark:bg-red-950 dark:text-red-400">Superadmin</span>
                        ) : (
                          <>
                            <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${planBadgeClass(u.plan_code)}`}>
                              {u.plan_code || 'none'}
                            </span>
                            {u.plan_status && (
                              <p className={`text-[10px] font-medium mt-0.5 ${STATUS_COLORS[u.plan_status] || 'text-gray-400'}`}>
                                {u.plan_status}
                              </p>
                            )}
                          </>
                        )}
                      </td>

                      {/* Active Status */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${u.is_active ? 'bg-green-400' : 'bg-red-400'}`} />
                          <span className="text-xs text-gray-500 dark:text-gray-400">{u.is_active ? 'Active' : 'Inactive'}</span>
                          {u.is_superadmin && (
                            <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600 dark:bg-red-950 dark:text-red-400">ADMIN</span>
                          )}
                        </div>
                      </td>

                      {/* Trial */}
                      <td className="px-4 py-3">
                        {u.is_superadmin ? (
                          <span className="text-xs text-gray-400">{'\u2014'}</span>
                        ) : u.plan_status === 'trialing' && u.trial_days_left !== null ? (
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                            u.trial_days_left <= 0 ? 'bg-red-50 text-red-600 dark:bg-red-950/50 dark:text-red-400' :
                            u.trial_days_left <= 3 ? 'bg-red-50 text-red-600 dark:bg-red-950/50 dark:text-red-400' :
                            u.trial_days_left <= 7 ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400' :
                            'bg-green-50 text-green-600 dark:bg-green-950/50 dark:text-green-400'
                          }`}>
                            {u.trial_days_left > 0 ? `${u.trial_days_left}d` : 'Expired'}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">{'\u2014'}</span>
                        )}
                      </td>

                      {/* Joined */}
                      <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : '\u2014'}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-1">
                          <button onClick={() => router.push(`/admin/users/${u.id}`)} title="View details" className="rounded p-1.5 text-gray-400 hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-950 dark:hover:text-indigo-400 transition">
                            <ExternalLink className="h-4 w-4" />
                          </button>
                          <button onClick={() => setResetTarget(u)} title="Reset password" className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200 transition">
                            <Key className="h-4 w-4" />
                          </button>
                          {!u.is_superadmin && (
                            <>
                              <button onClick={() => toggleActive(u)} title={u.is_active ? 'Deactivate' : 'Activate'} className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200 transition">
                                {u.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                              </button>
                              <button onClick={() => handleImpersonate(u)} title="Login as user" className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200 transition">
                                <LogIn className="h-4 w-4" />
                              </button>
                              <button onClick={() => handleDelete(u)} title="Delete user" className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400 transition">
                                <Trash2 className="h-4 w-4" />
                              </button>
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

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">Page {page + 1} of {totalPages}</p>
            <div className="flex gap-1">
              <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="rounded-lg border border-gray-200 p-2 text-gray-500 hover:bg-gray-50 disabled:opacity-30 dark:border-gray-700 dark:hover:bg-gray-800 transition">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="rounded-lg border border-gray-200 p-2 text-gray-500 hover:bg-gray-50 disabled:opacity-30 dark:border-gray-700 dark:hover:bg-gray-800 transition">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Modals */}
        {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />}
        {resetTarget && <ResetPasswordModal user={resetTarget} onClose={() => setResetTarget(null)} onReset={() => setResetTarget(null)} />}
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Create User Modal
// ---------------------------------------------------------------------------

function CreateUserModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [plan, setPlan] = useState('trial');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!email || !password) { setError('Email and password are required'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    setSaving(true);
    try {
      await adminCreateUser({ email, password, full_name: fullName || undefined, plan_code: plan !== 'trial' ? plan : undefined });
      onCreated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Add New User</h3>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition"><X className="h-5 w-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Email *</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Full Name</label>
            <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Password *</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Min 8 characters" className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white" required minLength={8} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Plan</label>
            <select value={plan} onChange={(e) => setPlan(e.target.value)} className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white">
              <option value="trial">Trial (7 days)</option>
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/50 dark:text-red-400">{error}</div>}
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800 transition">Cancel</button>
            <button type="submit" disabled={saving} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition">
              {saving && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
              Create User
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reset Password Modal
// ---------------------------------------------------------------------------

function ResetPasswordModal({ user, onClose, onReset }: { user: AdminUserItem; onClose: () => void; onReset: () => void }) {
  const [newPassword, setNewPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (newPassword.length < 8) { setError('Password must be at least 8 characters'); return; }
    setSaving(true);
    try {
      await adminResetPassword(user.id, newPassword);
      onReset();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Reset Password</h3>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition"><X className="h-5 w-5" /></button>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Set a new password for <span className="font-medium text-gray-700 dark:text-gray-300">{user.email}</span>
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">New Password</label>
            <input ref={inputRef} type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Min 8 characters" className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white" required minLength={8} />
          </div>
          {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/50 dark:text-red-400">{error}</div>}
          <div className="flex gap-2 justify-end pt-1">
            <button type="button" onClick={onClose} className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800 transition">Cancel</button>
            <button type="submit" disabled={saving} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition">
              {saving && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
              Reset Password
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


