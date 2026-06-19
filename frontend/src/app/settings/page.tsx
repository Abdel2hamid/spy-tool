'use client';

export const dynamic = 'force-dynamic';

import { useState, useEffect } from 'react';
import { AppShell } from '@/components';
import { useAuth } from '@/lib/auth';
import {
  getUsageSummary,
  updateProfile,
  changePassword,
  createStripeCheckout,
  createBillingPortal,
  UsageSummary,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  User,
  Shield,
  Lock,
  CreditCard,
  BarChart2,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Calendar,
  Mail,
  Building2,
  ChevronRight,
  ExternalLink,
  Loader2,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Tab = 'general' | 'account' | 'privacy' | 'billing' | 'usage';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'general', label: 'General', icon: User },
  { id: 'account', label: 'Account', icon: Shield },
  { id: 'privacy', label: 'Privacy', icon: Lock },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'usage', label: 'Usage', icon: BarChart2 },
];

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

function SectionCard({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900',
        className,
      )}
    >
      <div className="mb-5">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white">{title}</h3>
        {description && (
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">{description}</p>
        )}
      </div>
      {children}
    </div>
  );
}

function FormInput({
  label,
  value,
  onChange,
  type = 'text',
  readOnly = false,
  placeholder,
  hint,
  suffix,
}: {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  type?: string;
  readOnly?: boolean;
  placeholder?: string;
  hint?: string;
  suffix?: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
        {label}
      </label>
      <div className="relative mt-1.5">
        <input
          type={type}
          value={value}
          onChange={onChange ? (e) => onChange(e.target.value) : undefined}
          readOnly={readOnly}
          placeholder={placeholder}
          className={cn(
            'w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1',
            readOnly
              ? 'border-gray-200 bg-gray-50 text-gray-500 dark:border-gray-700 dark:bg-gray-800/50 dark:text-gray-400'
              : 'border-gray-300 bg-white text-gray-900 focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500',
            suffix ? 'pr-10' : '',
          )}
        />
        {suffix && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3">{suffix}</div>
        )}
      </div>
      {hint && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{hint}</p>}
    </div>
  );
}

function InlineAlert({
  type,
  message,
}: {
  type: 'success' | 'error';
  message: string;
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm',
        type === 'success'
          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
          : 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400',
      )}
    >
      {type === 'success' ? (
        <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
      ) : (
        <AlertTriangle className="h-4 w-4 flex-shrink-0" />
      )}
      {message}
    </div>
  );
}

function Badge({
  label,
  color = 'gray',
}: {
  label: string;
  color?: 'gray' | 'green' | 'indigo' | 'amber' | 'violet';
}) {
  const colors = {
    gray: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400',
    indigo: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-400',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400',
    violet: 'bg-violet-100 text-violet-700 dark:bg-violet-950/50 dark:text-violet-400',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize',
        colors[color],
      )}
    >
      {label}
    </span>
  );
}

function SaveButton({
  onClick,
  loading,
  label = 'Save changes',
}: {
  onClick: () => void;
  loading: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      {label}
    </button>
  );
}

function PlaceholderAction({
  label,
  description,
  variant = 'default',
}: {
  label: string;
  description?: string;
  variant?: 'default' | 'danger';
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="min-w-0">
        <p className="text-sm font-medium text-gray-900 dark:text-white">{label}</p>
        {description && (
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}
      </div>
      <button
        disabled
        className={cn(
          'flex-shrink-0 rounded-lg border px-3 py-1.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50',
          variant === 'danger'
            ? 'border-red-200 text-red-600 dark:border-red-900 dark:text-red-400'
            : 'border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-400',
        )}
      >
        Coming soon
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// General tab
// ---------------------------------------------------------------------------

function GeneralSection({
  token,
  initialName,
  initialEmail,
  initialWorkspace,
}: {
  token: string;
  initialName: string;
  initialEmail: string;
  initialWorkspace: string;
}) {
  const [fullName, setFullName] = useState(initialName);
  const [wsName, setWsName] = useState(initialWorkspace);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleSaveProfile = async () => {
    setProfileSaving(true);
    setProfileMsg(null);
    try {
      await updateProfile(token, { full_name: fullName, workspace_name: wsName });
      setProfileMsg({ type: 'success', text: 'Profile saved successfully.' });
    } catch (e: unknown) {
      setProfileMsg({ type: 'error', text: (e instanceof Error ? e.message : 'Failed to save profile.') });
    } finally {
      setProfileSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPw !== confirmPw) {
      setPwMsg({ type: 'error', text: 'New passwords do not match.' });
      return;
    }
    if (newPw.length < 8) {
      setPwMsg({ type: 'error', text: 'Password must be at least 8 characters.' });
      return;
    }
    if (newPw.length > 72) {
      setPwMsg({ type: 'error', text: 'Password must be at most 72 characters.' });
      return;
    }
    const hasUpper = /[A-Z]/.test(newPw);
    const hasLower = /[a-z]/.test(newPw);
    const hasDigit = /[0-9]/.test(newPw);
    if (!hasUpper || !hasLower || !hasDigit) {
      setPwMsg({ type: 'error', text: 'Password must contain uppercase, lowercase, and a digit.' });
      return;
    }
    setPwSaving(true);
    setPwMsg(null);
    try {
      await changePassword(token, { current_password: currentPw, new_password: newPw });
      setPwMsg({ type: 'success', text: 'Password changed successfully.' });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (e: unknown) {
      setPwMsg({ type: 'error', text: (e instanceof Error ? e.message : 'Failed to change password.') });
    } finally {
      setPwSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Profile */}
      <SectionCard title="Profile" description="Your public-facing name and email address.">
        <div className="space-y-4">
          <FormInput
            label="Full name"
            value={fullName}
            onChange={setFullName}
            placeholder="Your name"
          />
          <FormInput
            label="Email address"
            value={initialEmail}
            readOnly
            type="email"
            hint="Email cannot be changed. Contact support if needed."
            suffix={<Mail className="h-4 w-4 text-gray-400" />}
          />
        </div>
        <div className="mt-5 flex items-center gap-3">
          <SaveButton onClick={handleSaveProfile} loading={profileSaving} />
          {profileMsg && <InlineAlert type={profileMsg.type} message={profileMsg.text} />}
        </div>
      </SectionCard>

      {/* Workspace */}
      <SectionCard title="Workspace" description="Settings for your workspace shared across your team.">
        <FormInput
          label="Workspace name"
          value={wsName}
          onChange={setWsName}
          placeholder="My Workspace"
          suffix={<Building2 className="h-4 w-4 text-gray-400" />}
        />
        <div className="mt-5 flex items-center gap-3">
          <SaveButton onClick={handleSaveProfile} loading={profileSaving} label="Save workspace" />
          {profileMsg && profileMsg.type === 'success' && (
            <InlineAlert type="success" message="Saved." />
          )}
        </div>
      </SectionCard>

      {/* Change password */}
      <SectionCard title="Change password" description="Use a strong password you don't use elsewhere.">
        <div className="space-y-4">
          <FormInput
            label="Current password"
            value={currentPw}
            onChange={setCurrentPw}
            type={showCurrent ? 'text' : 'password'}
            placeholder="••••••••"
            suffix={
              <button
                type="button"
                onClick={() => setShowCurrent((v) => !v)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            }
          />
          <FormInput
            label="New password"
            value={newPw}
            onChange={setNewPw}
            type={showNew ? 'text' : 'password'}
            placeholder="••••••••"
            hint="8–72 characters. Must include uppercase, lowercase, and a digit."
            suffix={
              <button
                type="button"
                onClick={() => setShowNew((v) => !v)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            }
          />
          <FormInput
            label="Confirm new password"
            value={confirmPw}
            onChange={setConfirmPw}
            type="password"
            placeholder="••••••••"
          />
        </div>
        <div className="mt-5 flex items-center gap-3">
          <SaveButton onClick={handleChangePassword} loading={pwSaving} label="Change password" />
          {pwMsg && <InlineAlert type={pwMsg.type} message={pwMsg.text} />}
        </div>
      </SectionCard>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Account tab
// ---------------------------------------------------------------------------

function AccountSection({
  email,
  role,
  joinedAt,
}: {
  email: string;
  role: string;
  joinedAt: string;
}) {
  const joined = joinedAt
    ? new Date(joinedAt).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '—';

  const roleBadge: 'indigo' | 'violet' | 'gray' =
    role === 'owner' ? 'indigo' : role === 'admin' ? 'violet' : 'gray';

  return (
    <div className="space-y-6">
      <SectionCard title="Account overview" description="Your account details and membership information.">
        <div className="divide-y divide-gray-100 dark:divide-gray-800">
          {[
            {
              icon: CheckCircle2,
              label: 'Account status',
              value: <Badge label="Active" color="green" />,
            },
            {
              icon: Shield,
              label: 'Membership role',
              value: <Badge label={role} color={roleBadge} />,
            },
            {
              icon: Mail,
              label: 'Email',
              value: <span className="text-sm text-gray-700 dark:text-gray-300">{email}</span>,
            },
            {
              icon: Calendar,
              label: 'Member since',
              value: <span className="text-sm text-gray-700 dark:text-gray-300">{joined}</span>,
            },
          ].map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-center justify-between py-3.5">
              <div className="flex items-center gap-2.5">
                <Icon className="h-4 w-4 text-gray-400" />
                <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>
              </div>
              {value}
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Danger zone */}
      <div className="rounded-xl border border-red-200 bg-white p-6 dark:border-red-900/50 dark:bg-gray-900">
        <div className="mb-5 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-500" />
          <h3 className="text-base font-semibold text-red-700 dark:text-red-400">Danger zone</h3>
        </div>
        <div className="space-y-4">
          <PlaceholderAction
            label="Leave workspace"
            description="Remove yourself from this workspace. You will lose access to all workspace data."
            variant="danger"
          />
          <div className="border-t border-gray-100 pt-4 dark:border-gray-800" />
          <PlaceholderAction
            label="Delete account"
            description="Permanently delete your account and all associated data. This action cannot be undone."
            variant="danger"
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Privacy tab
// ---------------------------------------------------------------------------

function PrivacySection() {
  return (
    <div className="space-y-6">
      <SectionCard
        title="Active sessions"
        description="Devices and browsers currently signed into your account."
      >
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                Current session
              </p>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                This device &mdash; signed in via JWT token
              </p>
            </div>
            <Badge label="Active" color="green" />
          </div>
        </div>
        <div className="mt-4">
          <PlaceholderAction
            label="Revoke all other sessions"
            description="Sign out from all other devices immediately."
          />
        </div>
      </SectionCard>

      <SectionCard title="Your data" description="Control how your data is stored and used.">
        <div className="space-y-4">
          <PlaceholderAction
            label="Export your data"
            description="Download a copy of all your workspace data in JSON format."
          />
          <div className="border-t border-gray-100 dark:border-gray-800" />
          <PlaceholderAction
            label="Delete all data"
            description="Permanently erase all data associated with your workspace."
            variant="danger"
          />
        </div>
      </SectionCard>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Billing tab
// ---------------------------------------------------------------------------

const PLAN_LABELS: Record<string, { label: string; color: 'gray' | 'indigo' | 'violet' | 'amber' }> = {
  free: { label: 'Free', color: 'gray' },
  trial: { label: 'Trial', color: 'amber' },
  starter: { label: 'Starter', color: 'indigo' },
  pro: { label: 'Pro', color: 'violet' },
  enterprise: { label: 'Enterprise', color: 'violet' },
};

function BillingSection({
  token,
  planCode,
  status,
  isTrialing,
  trialDaysLeft,
  trialEndsAt,
}: {
  token: string;
  planCode: string;
  status: string;
  isTrialing: boolean;
  trialDaysLeft: number | null;
  trialEndsAt: string | null;
}) {
  const plan = PLAN_LABELS[planCode] ?? { label: planCode, color: 'gray' as const };
  const isPro = planCode === 'pro' || planCode === 'enterprise';
  const hasPaidSub = isPro && (status === 'active' || status === 'trialing');

  const [upgradeLoading, setUpgradeLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const [billingError, setBillingError] = useState<string | null>(null);

  const statusColor =
    status === 'active' ? 'green' : status === 'trialing' ? 'amber' : 'gray';

  const trialEnd = trialEndsAt
    ? new Date(trialEndsAt).toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      })
    : null;

  const handleUpgrade = async () => {
    setUpgradeLoading(true);
    setBillingError(null);
    try {
      const { checkout_url } = await createStripeCheckout(token, 'pro');
      if (checkout_url && checkout_url.startsWith('https://checkout.stripe.com/')) {
        window.location.href = checkout_url;
      } else {
        setBillingError('Invalid checkout URL received.');
      }
    } catch (e: unknown) {
      setBillingError(e instanceof Error ? e.message : 'Failed to start checkout.');
    } finally {
      setUpgradeLoading(false);
    }
  };

  const handleBillingPortal = async () => {
    setPortalLoading(true);
    setBillingError(null);
    try {
      const { portal_url } = await createBillingPortal(token);
      if (portal_url && portal_url.startsWith('https://')) {
        window.location.href = portal_url;
      } else {
        setBillingError('Invalid billing portal URL received.');
      }
    } catch (e: unknown) {
      setBillingError(e instanceof Error ? e.message : 'Failed to open billing portal.');
    } finally {
      setPortalLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {billingError && <InlineAlert type="error" message={billingError} />}

      {/* Current plan */}
      <SectionCard title="Current plan" description="Your subscription and billing details.">
        <div className="divide-y divide-gray-100 dark:divide-gray-800">
          <div className="flex items-center justify-between py-3.5">
            <span className="text-sm text-gray-600 dark:text-gray-400">Plan</span>
            <Badge label={plan.label} color={plan.color} />
          </div>
          <div className="flex items-center justify-between py-3.5">
            <span className="text-sm text-gray-600 dark:text-gray-400">Status</span>
            <Badge label={status} color={statusColor} />
          </div>
          {isTrialing && trialDaysLeft !== null && (
            <div className="flex items-center justify-between py-3.5">
              <span className="text-sm text-gray-600 dark:text-gray-400">Trial ends</span>
              <div className="text-right">
                <span className="text-sm font-medium text-gray-900 dark:text-white">
                  {trialDaysLeft} day{trialDaysLeft !== 1 ? 's' : ''} left
                </span>
                {trialEnd && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">{trialEnd}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </SectionCard>

      {/* Upgrade CTA */}
      {!isPro && (
        <div className="relative overflow-hidden rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-violet-50 p-6 dark:border-indigo-900/50 dark:from-indigo-950/40 dark:to-violet-950/40">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                <h3 className="text-sm font-semibold text-indigo-900 dark:text-indigo-300">
                  Upgrade to Pro
                </h3>
              </div>
              <p className="mt-1.5 text-sm text-indigo-700 dark:text-indigo-400">
                Unlimited app tracking, keyword refreshes, AI requests, and exports.
              </p>
              <ul className="mt-3 space-y-1.5">
                {[
                  'Unlimited app imports',
                  'Unlimited keyword refreshes',
                  'Unlimited AI idea requests',
                  'CSV / JSON data exports',
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2 text-xs text-indigo-700 dark:text-indigo-400">
                    <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="mt-5">
            <button
              onClick={handleUpgrade}
              disabled={upgradeLoading}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              {upgradeLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Upgrade now
              <ChevronRight className="h-4 w-4" />
            </button>
            <p className="mt-2 text-xs text-indigo-500 dark:text-indigo-500">
              Secure checkout powered by Stripe.
            </p>
          </div>
        </div>
      )}

      {/* Billing management */}
      <SectionCard
        title="Billing management"
        description="Invoices, payment methods, and subscription management."
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-900 dark:text-white">Manage billing portal</p>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                View invoices, update payment method, and manage your subscription via Stripe.
              </p>
            </div>
            <button
              onClick={handleBillingPortal}
              disabled={portalLoading || !hasPaidSub}
              className="flex-shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
            >
              {portalLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ExternalLink className="h-3 w-3" />}
              Open portal
            </button>
          </div>
        </div>
        <p className="mt-4 text-xs text-gray-400 dark:text-gray-500">
          {hasPaidSub
            ? 'Powered by Stripe — manage invoices, payment methods, and cancellation from the portal.'
            : 'Billing portal is available after upgrading to a paid plan.'}
        </p>
      </SectionCard>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Usage tab
// ---------------------------------------------------------------------------

function UsageMeterRow({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number | null;
}) {
  const pct = limit === null ? 0 : Math.min(100, (used / limit) * 100);
  const isUnlimited = limit === null;
  const isAtLimit = !isUnlimited && used >= limit;
  const isNearLimit = !isUnlimited && pct >= 80;

  const barColor = isAtLimit
    ? 'bg-red-500'
    : isNearLimit
    ? 'bg-amber-500'
    : 'bg-indigo-500';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700 dark:text-gray-300">{label}</span>
        <span
          className={cn(
            'text-xs font-medium',
            isAtLimit
              ? 'text-red-600 dark:text-red-400'
              : isNearLimit
              ? 'text-amber-600 dark:text-amber-400'
              : 'text-gray-500 dark:text-gray-400',
          )}
        >
          {isUnlimited ? (
            <span className="text-emerald-600 dark:text-emerald-400">Unlimited</span>
          ) : (
            `${used.toLocaleString()} / ${limit.toLocaleString()}`
          )}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        {!isUnlimited && (
          <div
            className={cn('h-full rounded-full transition-all', barColor)}
            style={{ width: `${pct}%` }}
          />
        )}
        {isUnlimited && (
          <div className="h-full w-full rounded-full bg-emerald-400/30" />
        )}
      </div>
    </div>
  );
}

function UsageSection({ token }: { token: string }) {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getUsageSummary(token).then((s) => {
      setSummary(s);
      setLoading(false);
    });
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (!summary) return null;

  const { plan, month, usage, limits } = summary;
  const planMeta = PLAN_LABELS[plan] ?? { label: plan, color: 'gray' as const };

  const monthLabel = month
    ? new Date(month + '-01').toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : 'Current month';

  const metrics: { label: string; key: keyof typeof usage }[] = [
    { label: 'App imports', key: 'app_imports' },
    { label: 'Keyword refreshes', key: 'keyword_refreshes' },
    { label: 'AI requests', key: 'ai_requests' },
    { label: 'Exports', key: 'exports' },
  ];

  return (
    <div className="space-y-6">
      <SectionCard
        title={`Usage — ${monthLabel}`}
        description="Monthly usage counters reset on the 1st of each month."
      >
        <div className="mb-4 flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">Current plan</span>
          <Badge label={planMeta.label} color={planMeta.color} />
        </div>
        <div className="space-y-5">
          {metrics.map(({ label, key }) => (
            <UsageMeterRow
              key={key}
              label={label}
              used={usage[key]}
              limit={limits[key]}
            />
          ))}
        </div>
      </SectionCard>

      {plan === 'free' && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
          <div className="flex items-start gap-3">
            <Zap className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
            <div>
              <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
                You&apos;re on the Free plan
              </p>
              <p className="mt-0.5 text-xs text-amber-600 dark:text-amber-400">
                Start a trial or upgrade to Pro for higher limits and full access.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main settings component
// ---------------------------------------------------------------------------

function SettingsContent() {
  const [activeTab, setActiveTab] = useState<Tab>('general');
  const { user, workspace, token } = useAuth();

  // Derived
  const sub = workspace?.subscription ?? null;
  const planCode = sub?.plan_code ?? 'free';
  const subStatus = sub?.status ?? 'inactive';

  if (!token || !user || !workspace) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Manage your account, workspace, and billing preferences.
          </p>
        </div>

        {/* Layout */}
        <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
          {/* Sidebar nav */}
          <nav className="flex flex-row gap-1 overflow-x-auto lg:w-52 lg:flex-shrink-0 lg:flex-col lg:overflow-visible">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors whitespace-nowrap',
                  activeTab === id
                    ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white',
                )}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                {label}
              </button>
            ))}
          </nav>

          {/* Tab content */}
          <div className="min-w-0 flex-1">
            {activeTab === 'general' && (
              <GeneralSection
                token={token}
                initialName={user.full_name ?? ''}
                initialEmail={user.email}
                initialWorkspace={workspace.name}
              />
            )}
            {activeTab === 'account' && (
              <AccountSection
                email={user.email}
                role={workspace.role}
                joinedAt={user.created_at}
              />
            )}
            {activeTab === 'privacy' && <PrivacySection />}
            {activeTab === 'billing' && (
              <BillingSection
                token={token}
                planCode={planCode}
                status={subStatus}
                isTrialing={sub?.is_trialing ?? false}
                trialDaysLeft={sub?.trial_days_left ?? null}
                trialEndsAt={sub?.trial_ends_at ?? null}
              />
            )}
            {activeTab === 'usage' && <UsageSection token={token} />}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default function SettingsPage() {
  return <SettingsContent />;
}
