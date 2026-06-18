'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetUserDetail,
  adminUpdateUser,
  adminResetPassword,
  adminImpersonateUser,
  adminDeleteUser,
  adminUpdateSubscription,
  adminExtendTrial,
  AdminUserDetail,
  UserActivityItem,
} from '@/lib/api';
import {
  ArrowLeft,
  RefreshCw,
  UserCheck,
  UserX,
  Shield,
  Key,
  LogIn,
  Trash2,
  X,
  CalendarPlus,
  ChevronDown,
  Star,
  Smartphone,
  Clock,
  Mail,
  Hash,
  Building2,
  CreditCard,
  BarChart3,
  Activity,
  Pencil,
  Check,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------
const PLAN_COLORS: Record<string, string> = {
  pro: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
  enterprise: 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300',
  starter: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  trial: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'text-green-600 dark:text-green-400',
  trialing: 'text-amber-600 dark:text-amber-400',
  canceled: 'text-red-600 dark:text-red-400',
  expired: 'text-gray-500 dark:text-gray-400',
};

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  'auth.login': { label: 'Login', color: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400' },
  'app.lookup': { label: 'App Lookup', color: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400' },
  'favorite.add': { label: 'Favorited', color: 'bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-400' },
  'favorite.remove': { label: 'Unfavorited', color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
  'myapp.add': { label: 'Added My App', color: 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-400' },
  'myapp.remove': { label: 'Removed My App', color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
  'keywords.extract': { label: 'Keywords Extract', color: 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-400' },
};

const ADMIN_ACTION_LABELS: Record<string, string> = {
  'user.create': 'Created',
  'user.update': 'Updated',
  'user.delete': 'Deleted',
  'user.reset_password': 'Password Reset',
  'user.impersonate': 'Impersonated',
  'user.promote': 'Promoted',
  'user.bulk_activate': 'Bulk Activated',
  'user.bulk_deactivate': 'Bulk Deactivated',
  'subscription.update': 'Subscription Changed',
  'trial.extend': 'Trial Extended',
};

function planBadge(plan: string | null) {
  return PLAN_COLORS[plan ?? ''] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300';
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AdminUserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = Number(params.id);

  const [data, setData] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  function load() {
    setLoading(true);
    adminGetUserDetail(userId)
      .then(setData)
      .catch(() => setError('Failed to load user'))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [userId]);

  if (loading) {
    return (
      <AdminShell>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      </AdminShell>
    );
  }

  if (error || !data) {
    return (
      <AdminShell>
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <p className="text-sm text-red-500">{error || 'User not found'}</p>
          <button onClick={() => router.push('/admin/users')} className="text-sm text-indigo-600 hover:underline">Back to users</button>
        </div>
      </AdminShell>
    );
  }

  const { user, workspace, subscription, usage, favorites, my_apps, activity, admin_log } = data;

  return (
    <AdminShell>
      <div className="space-y-6 max-w-6xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/admin/users')}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200 transition"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div className="h-14 w-14 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-xl font-bold flex-shrink-0">
              {(user.full_name?.[0] || user.email[0]).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-gray-900 dark:text-white">{user.full_name || user.email}</h1>
                {user.is_superadmin && (
                  <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600 dark:bg-red-950 dark:text-red-400">ADMIN</span>
                )}
                <span className={`h-2.5 w-2.5 rounded-full ${user.is_active ? 'bg-green-400' : 'bg-red-400'}`} title={user.is_active ? 'Active' : 'Inactive'} />
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">{user.email}</p>
              <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                <span>Joined {user.created_at ? new Date(user.created_at).toLocaleDateString() : '\u2014'}</span>
                <span>&middot;</span>
                <span>Last active {timeAgo(user.last_active)}</span>
              </div>
            </div>
          </div>
          <UserActions user={user} workspace={workspace} onRefresh={load} />
        </div>

        {/* Quick Info Cards */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <InfoCard
            icon={<CreditCard className="h-4 w-4" />}
            label="Plan"
            value={
              <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${planBadge(subscription?.plan_code ?? null)}`}>
                {subscription?.plan_code || 'none'}
              </span>
            }
            sub={subscription?.status ? <span className={`text-xs font-medium ${STATUS_COLORS[subscription.status] || ''}`}>{subscription.status}</span> : undefined}
          />
          <InfoCard
            icon={<Clock className="h-4 w-4" />}
            label="Trial"
            value={
              subscription?.status === 'trialing' && subscription.trial_days_left !== null
                ? <span className={`text-lg font-bold ${subscription.trial_days_left <= 3 ? 'text-red-600 dark:text-red-400' : subscription.trial_days_left <= 7 ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'}`}>{subscription.trial_days_left}d left</span>
                : <span className="text-gray-400">{'\u2014'}</span>
            }
            sub={subscription?.trial_ends_at ? <span className="text-xs text-gray-400">ends {new Date(subscription.trial_ends_at).toLocaleDateString()}</span> : undefined}
          />
          <InfoCard
            icon={<Star className="h-4 w-4" />}
            label="Favorites"
            value={<span className="text-lg font-bold text-gray-900 dark:text-white">{data.favorite_count}</span>}
            sub={<span className="text-xs text-gray-400">apps saved</span>}
          />
          <InfoCard
            icon={<Smartphone className="h-4 w-4" />}
            label="My Apps"
            value={<span className="text-lg font-bold text-gray-900 dark:text-white">{data.my_app_count}</span>}
            sub={<span className="text-xs text-gray-400">apps tracked</span>}
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Workspace + Subscription */}
            <div className="grid gap-4 sm:grid-cols-2">
              <Section title="Workspace" icon={<Building2 className="h-4 w-4 text-purple-500" />}>
                {workspace ? (
                  <div className="space-y-2.5">
                    <DetailRow label="Name" value={workspace.name} />
                    <DetailRow label="Slug" value={workspace.slug} />
                    <DetailRow label="Role" value={<span className="capitalize">{workspace.role || '\u2014'}</span>} />
                    <DetailRow label="Created" value={workspace.created_at ? new Date(workspace.created_at).toLocaleDateString() : '\u2014'} />
                  </div>
                ) : <p className="text-sm text-gray-400">No workspace</p>}
              </Section>

              <SubscriptionSection
                subscription={subscription}
                workspaceId={workspace?.id ?? null}
                onRefresh={load}
              />
            </div>

            {/* Usage This Month */}
            <Section title="Usage This Month" icon={<BarChart3 className="h-4 w-4 text-blue-500" />}>
              {usage ? (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    { key: 'app_imports', label: 'App Imports', color: 'text-indigo-600 dark:text-indigo-400' },
                    { key: 'keyword_refreshes', label: 'Keywords', color: 'text-orange-600 dark:text-orange-400' },
                    { key: 'ai_requests', label: 'AI Requests', color: 'text-pink-600 dark:text-pink-400' },
                    { key: 'exports', label: 'Exports', color: 'text-green-600 dark:text-green-400' },
                  ].map((m) => (
                    <div key={m.key} className="rounded-lg border border-gray-100 p-3 dark:border-gray-800 text-center">
                      <p className={`text-2xl font-bold ${m.color}`}>{usage[m.key] ?? 0}</p>
                      <p className="text-[11px] text-gray-500 mt-0.5">{m.label}</p>
                    </div>
                  ))}
                </div>
              ) : <p className="text-sm text-gray-400">No usage data</p>}
            </Section>

            {/* Favorites */}
            <Section title={`Favorites (${data.favorite_count})`} icon={<Star className="h-4 w-4 text-pink-500" />}>
              {favorites.length === 0 ? (
                <p className="text-sm text-gray-400">No favorites yet</p>
              ) : (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {favorites.map((app) => (
                    <AppCard key={app.app_id} app={app} />
                  ))}
                </div>
              )}
            </Section>

            {/* My Apps */}
            <Section title={`My Apps (${data.my_app_count})`} icon={<Smartphone className="h-4 w-4 text-purple-500" />}>
              {my_apps.length === 0 ? (
                <p className="text-sm text-gray-400">No apps tracked yet</p>
              ) : (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {my_apps.map((app) => (
                    <AppCard key={app.app_id} app={app} />
                  ))}
                </div>
              )}
            </Section>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Activity Timeline */}
            <Section title={`Recent Activity (${data.activity_count})`} icon={<Activity className="h-4 w-4 text-green-500" />}>
              {activity.length === 0 ? (
                <p className="text-sm text-gray-400">No activity yet</p>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                  {activity.map((a) => {
                    const info = ACTION_LABELS[a.action] || { label: a.action, color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' };
                    return (
                      <div key={a.id} className="flex items-start gap-2.5">
                        <div className="mt-1.5 h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${info.color}`}>{info.label}</span>
                            {a.detail && <span className="text-xs text-gray-600 dark:text-gray-300 truncate">{a.detail}</span>}
                          </div>
                          <p className="text-[10px] text-gray-400 mt-0.5">{timeAgo(a.created_at)}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Section>

            {/* Admin Actions Log */}
            <Section title="Admin Actions" icon={<Shield className="h-4 w-4 text-red-500" />}>
              {admin_log.length === 0 ? (
                <p className="text-sm text-gray-400">No admin actions</p>
              ) : (
                <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                  {admin_log.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-2.5">
                      <div className="mt-1.5 h-2 w-2 rounded-full bg-red-300 dark:bg-red-600 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="inline-block rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-700 dark:bg-red-950/40 dark:text-red-400">
                            {ADMIN_ACTION_LABELS[entry.action] || entry.action}
                          </span>
                          {entry.admin_email && (
                            <span className="text-[10px] text-gray-400">by {entry.admin_email}</span>
                          )}
                        </div>
                        {entry.details && (
                          <p className="text-[10px] text-gray-500 mt-0.5 truncate">
                            {formatAdminDetails(entry.action, entry.details)}
                          </p>
                        )}
                        <p className="text-[10px] text-gray-400 mt-0.5">{timeAgo(entry.created_at)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </div>
        </div>
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// User Actions Bar
// ---------------------------------------------------------------------------

function UserActions({
  user,
  workspace,
  onRefresh,
}: {
  user: AdminUserDetail['user'];
  workspace: AdminUserDetail['workspace'];
  onRefresh: () => void;
}) {
  const router = useRouter();
  const [resetOpen, setResetOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function toggleActive() {
    setBusy(true);
    try { await adminUpdateUser(user.id, { is_active: !user.is_active }); onRefresh(); } catch { alert('Failed'); }
    finally { setBusy(false); }
  }

  async function toggleAdmin() {
    setBusy(true);
    try { await adminUpdateUser(user.id, { is_superadmin: !user.is_superadmin }); onRefresh(); } catch { alert('Failed'); }
    finally { setBusy(false); }
  }

  async function handleImpersonate() {
    try {
      const data = await adminImpersonateUser(user.id);
      sessionStorage.setItem('impersonate_token', data.token);
      window.open('/impersonate', '_blank');
    } catch { alert('Failed to impersonate'); }
  }

  async function handleDelete() {
    if (!confirm(`Delete ${user.email}? This cannot be undone.`)) return;
    try { await adminDeleteUser(user.id); router.push('/admin/users'); } catch { alert('Failed to delete'); }
  }

  return (
    <div className="flex items-center gap-1.5 flex-shrink-0 flex-wrap">
      <ActionBtn icon={user.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />} label={user.is_active ? 'Deactivate' : 'Activate'} onClick={toggleActive} disabled={busy} />
      <ActionBtn icon={<Shield className="h-4 w-4" />} label={user.is_superadmin ? 'Remove Admin' : 'Make Admin'} onClick={toggleAdmin} disabled={busy} className={user.is_superadmin ? 'text-red-500' : ''} />
      <ActionBtn icon={<Key className="h-4 w-4" />} label="Reset Password" onClick={() => setResetOpen(true)} disabled={busy} />
      <ActionBtn icon={<LogIn className="h-4 w-4" />} label="Login As" onClick={handleImpersonate} disabled={busy} />
      <ActionBtn icon={<Trash2 className="h-4 w-4" />} label="Delete" onClick={handleDelete} disabled={busy} className="hover:!bg-red-50 hover:!text-red-600 dark:hover:!bg-red-950 dark:hover:!text-red-400" />

      {resetOpen && <ResetPasswordModal userId={user.id} email={user.email} onClose={() => setResetOpen(false)} onDone={() => { setResetOpen(false); }} />}
    </div>
  );
}

function ActionBtn({ icon, label, onClick, disabled, className }: { icon: React.ReactNode; label: string; onClick: () => void; disabled?: boolean; className?: string }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      className={`rounded-lg border border-gray-200 p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-40 transition dark:border-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200 ${className || ''}`}
    >
      {icon}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Subscription Section with inline edit
// ---------------------------------------------------------------------------

function SubscriptionSection({
  subscription,
  workspaceId,
  onRefresh,
}: {
  subscription: AdminUserDetail['subscription'];
  workspaceId: number | null;
  onRefresh: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [plan, setPlan] = useState(subscription?.plan_code || 'trial');
  const [status, setStatus] = useState(subscription?.status || 'trialing');
  const [saving, setSaving] = useState(false);
  const [extendOpen, setExtendOpen] = useState(false);

  useEffect(() => {
    if (!editing) return;
    const close = () => setExtendOpen(false);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [editing]);

  async function handleSave() {
    if (!workspaceId) return;
    setSaving(true);
    try {
      await adminUpdateSubscription(workspaceId, { plan_code: plan, status });
      setEditing(false);
      onRefresh();
    } catch { alert('Failed to update'); }
    finally { setSaving(false); }
  }

  async function handleExtend(days: number) {
    if (!workspaceId) return;
    setExtendOpen(false);
    setSaving(true);
    try { await adminExtendTrial(workspaceId, days); onRefresh(); } catch { alert('Failed'); }
    finally { setSaving(false); }
  }

  return (
    <Section
      title="Subscription"
      icon={<CreditCard className="h-4 w-4 text-green-500" />}
      action={
        subscription && workspaceId ? (
          <div className="flex items-center gap-1">
            {subscription.status === 'trialing' && (
              <div className="relative">
                <button
                  onClick={(e) => { e.stopPropagation(); setExtendOpen(!extendOpen); }}
                  className="text-xs text-amber-600 hover:text-amber-700 dark:text-amber-400 font-medium flex items-center gap-1"
                >
                  <CalendarPlus className="h-3 w-3" /> Extend
                </button>
                {extendOpen && (
                  <div className="absolute right-0 top-full z-20 mt-1 w-28 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-900" onClick={(e) => e.stopPropagation()}>
                    {[7, 14, 30].map((d) => (
                      <button key={d} onClick={() => handleExtend(d)} className="block w-full px-3 py-1.5 text-left text-xs text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800">+{d} days</button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {!editing ? (
              <button onClick={() => setEditing(true)} className="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium flex items-center gap-1">
                <Pencil className="h-3 w-3" /> Edit
              </button>
            ) : (
              <button onClick={handleSave} disabled={saving} className="text-xs text-green-600 hover:text-green-700 dark:text-green-400 font-medium flex items-center gap-1">
                {saving ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Save
              </button>
            )}
          </div>
        ) : undefined
      }
    >
      {subscription ? (
        <div className="space-y-2.5">
          {editing ? (
            <>
              <div>
                <label className="text-[10px] font-medium text-gray-500 uppercase">Plan</label>
                <select value={plan} onChange={(e) => setPlan(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white">
                  <option value="trial">Trial</option>
                  <option value="starter">Starter</option>
                  <option value="pro">Pro</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] font-medium text-gray-500 uppercase">Status</label>
                <select value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white">
                  <option value="trialing">Trialing</option>
                  <option value="active">Active</option>
                  <option value="canceled">Canceled</option>
                  <option value="expired">Expired</option>
                </select>
              </div>
              <button onClick={() => setEditing(false)} className="text-xs text-gray-400 hover:text-gray-600">Cancel</button>
            </>
          ) : (
            <>
              <DetailRow label="Plan" value={<span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${planBadge(subscription.plan_code)}`}>{subscription.plan_code}</span>} />
              <DetailRow label="Status" value={<span className={`font-medium ${STATUS_COLORS[subscription.status] || ''}`}>{subscription.status}</span>} />
              {subscription.trial_ends_at && (
                <DetailRow label="Trial Ends" value={new Date(subscription.trial_ends_at).toLocaleDateString()} />
              )}
              {subscription.trial_days_left !== null && subscription.status === 'trialing' && (
                <DetailRow label="Days Left" value={
                  <span className={`font-bold ${subscription.trial_days_left <= 3 ? 'text-red-600 dark:text-red-400' : subscription.trial_days_left <= 7 ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'}`}>
                    {subscription.trial_days_left}
                  </span>
                } />
              )}
              {subscription.current_period_end && (
                <DetailRow label="Period Ends" value={new Date(subscription.current_period_end).toLocaleDateString()} />
              )}
            </>
          )}
        </div>
      ) : <p className="text-sm text-gray-400">No subscription</p>}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Reusable Components
// ---------------------------------------------------------------------------

function Section({ title, icon, children, action }: { title: string; icon: React.ReactNode; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">{icon}{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

function InfoCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center gap-2 text-gray-400 mb-2">{icon}<span className="text-[11px] font-medium uppercase tracking-wider">{label}</span></div>
      <div>{value}</div>
      {sub && <div className="mt-1">{sub}</div>}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-gray-900 dark:text-white">{value}</span>
    </div>
  );
}

function AppCard({ app }: { app: { app_id: number; name: string; icon_url: string | null; developer: string | null; added_at: string | null } }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-100 p-2.5 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition">
      {app.icon_url ? (
        <img src={app.icon_url} alt="" className="h-9 w-9 rounded-lg flex-shrink-0" />
      ) : (
        <div className="h-9 w-9 rounded-lg bg-gray-200 dark:bg-gray-700 flex-shrink-0" />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{app.name}</p>
        <p className="text-[11px] text-gray-400 truncate">{app.developer || '\u2014'}</p>
      </div>
      {app.added_at && (
        <span className="text-[10px] text-gray-400 flex-shrink-0">{timeAgo(app.added_at)}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reset Password Modal
// ---------------------------------------------------------------------------

function ResetPasswordModal({ userId, email, onClose, onDone }: { userId: number; email: string; onClose: () => void; onDone: () => void }) {
  const [pw, setPw] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (pw.length < 8) { setError('Min 8 characters'); return; }
    setSaving(true);
    try { await adminResetPassword(userId, pw); onDone(); } catch (err: unknown) { setError(err instanceof Error ? err.message : 'Failed'); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Reset Password</h3>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"><X className="h-5 w-5" /></button>
        </div>
        <p className="text-sm text-gray-500 mb-4">New password for <span className="font-medium text-gray-700 dark:text-gray-300">{email}</span></p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input ref={ref} type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Min 8 characters" className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white" required minLength={8} />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800 transition">Cancel</button>
            <button type="submit" disabled={saving} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition">
              {saving && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
              Reset
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatAdminDetails(action: string, details: Record<string, unknown>): string {
  if (action === 'user.update' && details.changes) return JSON.stringify(details.changes);
  if (action === 'user.reset_password') return 'Password was reset';
  if (action === 'user.impersonate') return 'Admin logged in as this user';
  if (action === 'subscription.update') {
    const parts: string[] = [];
    if (details.plan_code) parts.push(`plan: ${details.plan_code}`);
    if (details.status) parts.push(`status: ${details.status}`);
    return parts.join(', ');
  }
  if (action === 'trial.extend') return `Extended by ${details.days || '?'} days`;
  return JSON.stringify(details);
}
