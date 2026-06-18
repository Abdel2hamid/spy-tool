'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components';
import { useAuth } from '@/lib/auth';
import {
  adminGetDashboard,
  adminGetUsers,
  adminUpdateUser,
  adminDeleteUser,
  adminGetWorkspaces,
  adminUpdateSubscription,
  adminGetJobs,
  adminTriggerJob,
  adminGetSystemHealth,
  AdminDashboardStats,
  AdminUserItem,
  AdminWorkspaceItem,
  AdminJobItem,
  AdminSystemHealth,
} from '@/lib/api';
import {
  Shield,
  Users,
  Building2,
  Clock,
  Server,
  Search,
  Trash2,
  Play,
  RefreshCw,
  UserCheck,
  UserX,
  ChevronLeft,
  ChevronRight,
  Database,
  Activity,
  BarChart3,
} from 'lucide-react';

type Tab = 'dashboard' | 'users' | 'workspaces' | 'jobs' | 'system';

export default function AdminClient() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('dashboard');

  // Redirect non-superadmins
  useEffect(() => {
    if (!authLoading && (!user || !user.is_superadmin)) {
      router.replace('/');
    }
  }, [user, authLoading, router]);

  if (authLoading || !user?.is_superadmin) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      </AppShell>
    );
  }

  const tabs: { key: Tab; label: string; icon: React.ElementType }[] = [
    { key: 'dashboard', label: 'Dashboard', icon: BarChart3 },
    { key: 'users', label: 'Users', icon: Users },
    { key: 'workspaces', label: 'Workspaces', icon: Building2 },
    { key: 'jobs', label: 'Jobs', icon: Clock },
    { key: 'system', label: 'System', icon: Server },
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-red-500 to-orange-500">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Console</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Manage users, workspaces, and system</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800/50">
          {tabs.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all ${
                  tab === t.key
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {tab === 'dashboard' && <DashboardTab />}
        {tab === 'users' && <UsersTab />}
        {tab === 'workspaces' && <WorkspacesTab />}
        {tab === 'jobs' && <JobsTab />}
        {tab === 'system' && <SystemTab />}
      </div>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Dashboard Tab
// ---------------------------------------------------------------------------

function DashboardTab() {
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminGetDashboard()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (!stats) return <ErrorMsg msg="Failed to load dashboard" />;

  const cards = [
    { label: 'Total Users', value: stats.total_users, icon: Users, color: 'text-blue-600 bg-blue-50 dark:bg-blue-950' },
    { label: 'Active Users', value: stats.active_users, icon: UserCheck, color: 'text-green-600 bg-green-50 dark:bg-green-950' },
    { label: 'Workspaces', value: stats.total_workspaces, icon: Building2, color: 'text-purple-600 bg-purple-50 dark:bg-purple-950' },
    { label: 'Apps Tracked', value: stats.total_apps, icon: Activity, color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-950' },
    { label: 'Keywords', value: stats.total_keywords, icon: Search, color: 'text-orange-600 bg-orange-50 dark:bg-orange-950' },
    { label: 'Reviews', value: stats.total_reviews, icon: BarChart3, color: 'text-pink-600 bg-pink-50 dark:bg-pink-950' },
  ];

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map((c) => {
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

      {/* Plans breakdown */}
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
    </div>
  );
}

// ---------------------------------------------------------------------------
// Users Tab
// ---------------------------------------------------------------------------

function UsersTab() {
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
    <div className="space-y-4">
      {/* Search */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search users..."
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
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto" /></td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No users found</td></tr>
            ) : users.map((u) => (
              <tr key={u.id} className="bg-white dark:bg-gray-900">
                <td className="px-4 py-3">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">{u.full_name || u.email}</p>
                    <p className="text-xs text-gray-400">{u.email}</p>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-300">{u.workspace_name || '—'}</td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
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
                      className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
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
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="rounded-lg border p-2 text-gray-500 hover:bg-gray-50 disabled:opacity-30 dark:border-gray-700 dark:hover:bg-gray-800"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Workspaces Tab
// ---------------------------------------------------------------------------

function WorkspacesTab() {
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
    <div className="space-y-4">
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
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto" /></td></tr>
            ) : workspaces.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No workspaces found</td></tr>
            ) : workspaces.map((ws) => (
              <tr key={ws.id} className="bg-white dark:bg-gray-900">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900 dark:text-white">{ws.name}</p>
                  <p className="text-xs text-gray-400">{ws.slug}</p>
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-300">{ws.owner_email || '—'}</td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-300">{ws.member_count}</td>
                <td className="px-4 py-3">
                  <div>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                      {ws.plan_code || 'none'}
                    </span>
                    {ws.plan_status && (
                      <span className={`ml-1 text-xs ${ws.plan_status === 'trialing' ? 'text-amber-500' : ws.plan_status === 'active' ? 'text-green-500' : 'text-gray-400'}`}>
                        {ws.plan_status}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                  {ws.usage.app_imports} imports, {ws.usage.keyword_refreshes} kw, {ws.usage.ai_requests} AI
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => openEdit(ws)}
                    className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 font-medium"
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

      {/* Edit modal */}
      {editWs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Edit Subscription — {editWs.name}
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Plan Code</label>
                <select
                  value={editPlan}
                  onChange={(e) => setEditPlan(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                >
                  <option value="trial">trial</option>
                  <option value="starter">starter</option>
                  <option value="pro">pro</option>
                  <option value="enterprise">enterprise</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                >
                  <option value="trialing">trialing</option>
                  <option value="active">active</option>
                  <option value="canceled">canceled</option>
                  <option value="expired">expired</option>
                </select>
              </div>
            </div>
            <div className="mt-5 flex gap-2 justify-end">
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
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Jobs Tab
// ---------------------------------------------------------------------------

function JobsTab() {
  const [jobs, setJobs] = useState<AdminJobItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    adminGetJobs()
      .then((d) => setJobs(d.jobs))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleTrigger(jobId: string) {
    setTriggering(jobId);
    try {
      await adminTriggerJob(jobId);
      load();
    } catch {
      // ignore
    } finally {
      setTriggering(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{jobs.length} scheduled jobs</p>
        <button onClick={load} className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 dark:text-indigo-400">
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left dark:bg-gray-800/50">
            <tr>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Job ID</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Trigger</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Next Run</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto" /></td></tr>
            ) : jobs.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">No jobs found</td></tr>
            ) : jobs.map((j) => (
              <tr key={j.job_id} className="bg-white dark:bg-gray-900">
                <td className="px-4 py-3 font-mono text-xs text-gray-900 dark:text-white">{j.job_id}</td>
                <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-[200px] truncate">{j.trigger || '—'}</td>
                <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                  {j.next_run ? new Date(j.next_run).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleTrigger(j.job_id)}
                    disabled={triggering === j.job_id}
                    className="flex items-center gap-1 rounded-lg bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 disabled:opacity-50 dark:bg-green-950 dark:text-green-400 dark:hover:bg-green-900"
                  >
                    {triggering === j.job_id ? (
                      <RefreshCw className="h-3 w-3 animate-spin" />
                    ) : (
                      <Play className="h-3 w-3" />
                    )}
                    Run Now
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// System Tab
// ---------------------------------------------------------------------------

function SystemTab() {
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminGetSystemHealth()
      .then(setHealth)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (!health) return <ErrorMsg msg="Failed to load system health" />;

  const items = [
    { label: 'Database Size', value: `${health.db_size_mb} MB`, icon: Database },
    { label: 'Total Tables', value: health.total_tables, icon: Server },
    { label: 'Apps', value: health.app_count.toLocaleString(), icon: Activity },
    { label: 'Keywords', value: health.keyword_count.toLocaleString(), icon: Search },
    { label: 'Reviews', value: health.review_count.toLocaleString(), icon: BarChart3 },
    { label: 'Pending Queue', value: health.pending_queue.toLocaleString(), icon: Clock },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-green-400 animate-pulse" />
        <span className="text-sm font-medium text-green-600 dark:text-green-400">{health.uptime_info}</span>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {items.map((it) => {
          const Icon = it.icon;
          return (
            <div key={it.label} className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
              <Icon className="h-5 w-5 text-gray-400 mb-2" />
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{it.value}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">{it.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared components
// ---------------------------------------------------------------------------

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-48">
      <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
    </div>
  );
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="flex items-center justify-center h-48">
      <p className="text-sm text-red-500">{msg}</p>
    </div>
  );
}
