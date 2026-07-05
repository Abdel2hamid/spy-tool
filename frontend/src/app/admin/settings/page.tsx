'use client';

import { useEffect, useState } from 'react';
import { AdminShell } from '@/components/AdminShell';
import { useAuth } from '@/lib/auth';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  CreditCard,
  Package,
  Save,
  Eye,
  EyeOff,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-react';

// Shared resolver — reading NEXT_PUBLIC_API_URL directly broke when the env
// var is an origin without the /api/v1 suffix (every other page worked).
const API = API_BASE;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PlanConfig {
  name: string;
  price: number;
  period: string;
  app_imports: number | null;
  keyword_refreshes: number | null;
  ai_requests: number | null;
  exports: number | null;
  access_premium: boolean;
}

type PlansMap = Record<string, PlanConfig>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function useAdminFetch<T>(endpoint: string) {
  const { token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/admin${endpoint}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, endpoint]);

  return { data, loading, refetch: () => {
    if (!token) return;
    setLoading(true);
    fetch(`${API}/admin${endpoint}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }};
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function AdminSettingsPage() {
  const [tab, setTab] = useState<'payment' | 'plans'>('payment');

  return (
    <AdminShell>
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-1">Settings</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Configure payment gateways and plan pricing.
        </p>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-800">
          <button
            onClick={() => setTab('payment')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition',
              tab === 'payment'
                ? 'border-red-500 text-red-600 dark:text-red-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
            )}
          >
            <CreditCard className="w-4 h-4" />
            Payment Gateways
          </button>
          <button
            onClick={() => setTab('plans')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition',
              tab === 'plans'
                ? 'border-red-500 text-red-600 dark:text-red-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
            )}
          >
            <Package className="w-4 h-4" />
            Plans & Pricing
          </button>
        </div>

        {tab === 'payment' && <PaymentSettings />}
        {tab === 'plans' && <PlansSettings />}
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Payment Settings Tab
// ---------------------------------------------------------------------------

const STRIPE_FIELDS = [
  { key: 'stripe_publishable_key', label: 'Publishable Key', sensitive: false, placeholder: 'pk_live_...' },
  { key: 'stripe_secret_key', label: 'Secret Key', sensitive: true, placeholder: 'sk_live_...' },
  { key: 'stripe_webhook_secret', label: 'Webhook Secret', sensitive: true, placeholder: 'whsec_...' },
  { key: 'stripe_price_starter', label: 'Starter Price ID', sensitive: false, placeholder: 'price_...' },
  { key: 'stripe_price_pro', label: 'Pro Price ID', sensitive: false, placeholder: 'price_...' },
];

const PAYPAL_FIELDS = [
  { key: 'paypal_client_id', label: 'Client ID', sensitive: false, placeholder: 'A...' },
  { key: 'paypal_client_secret', label: 'Client Secret', sensitive: true, placeholder: 'E...' },
  { key: 'paypal_webhook_id', label: 'Webhook ID', sensitive: false, placeholder: '' },
  { key: 'paypal_mode', label: 'Mode', sensitive: false, placeholder: 'sandbox or live' },
];

function PaymentSettings() {
  const { token } = useAuth();
  const { data, loading } = useAdminFetch<{ settings: Record<string, string> }>('/settings/payment');
  const [form, setForm] = useState<Record<string, string>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (data?.settings) setForm(data.settings);
  }, [data]);

  async function handleSave() {
    if (!token) return;
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const res = await fetch(`${API}/admin/settings/payment`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: form }),
      });
      if (!res.ok) throw new Error('Save failed');
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner />;

  function renderFields(fields: typeof STRIPE_FIELDS, title: string, icon: string) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 mb-6">
        <div className="flex items-center gap-3 mb-5">
          <span className="text-2xl">{icon}</span>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>
        </div>
        <div className="grid gap-4">
          {fields.map((f) => (
            <div key={f.key}>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">{f.label}</label>
              <div className="relative">
                <input
                  type={f.sensitive && !showSecrets[f.key] ? 'password' : 'text'}
                  value={form[f.key] || ''}
                  onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-400 transition font-mono"
                />
                {f.sensitive && (
                  <button
                    type="button"
                    onClick={() => setShowSecrets((s) => ({ ...s, [f.key]: !s[f.key] }))}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
                  >
                    {showSecrets[f.key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      {renderFields(STRIPE_FIELDS, 'Stripe', '💳')}
      {renderFields(PAYPAL_FIELDS, 'PayPal', '🅿️')}

      {error && (
        <div className="flex items-center gap-2 mb-4 px-4 py-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Payment Settings
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-emerald-600 dark:text-emerald-400">
            <Check className="w-4 h-4" /> Saved
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plans Settings Tab
// ---------------------------------------------------------------------------

const PLAN_CODES = ['free', 'starter', 'pro', 'lifetime'] as const;

const LIMIT_FIELDS = [
  { key: 'app_imports', label: 'App Imports / month' },
  { key: 'keyword_refreshes', label: 'Keyword Refreshes / month' },
  { key: 'ai_requests', label: 'AI Requests / month' },
  { key: 'exports', label: 'Exports / month' },
];

function PlansSettings() {
  const { token } = useAuth();
  const { data, loading } = useAdminFetch<{ plans: PlansMap }>('/settings/plans');
  const [plans, setPlans] = useState<PlansMap>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (data?.plans) setPlans(data.plans);
  }, [data]);

  function updatePlan(code: string, field: string, value: string | number | boolean | null) {
    setPlans((prev) => ({
      ...prev,
      [code]: { ...prev[code], [field]: value },
    }));
  }

  async function handleSave() {
    if (!token) return;
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const res = await fetch(`${API}/admin/settings/plans`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ plans }),
      });
      if (!res.ok) throw new Error('Save failed');
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError('Failed to save plan settings.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="grid md:grid-cols-2 gap-5 mb-6">
        {PLAN_CODES.map((code) => {
          const plan = plans[code];
          if (!plan) return null;
          return (
            <div key={code} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
              {/* Plan header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <input
                    value={plan.name}
                    onChange={(e) => updatePlan(code, 'name', e.target.value)}
                    className="text-lg font-bold text-gray-900 dark:text-white bg-transparent border-none p-0 focus:outline-none focus:ring-0 w-full"
                  />
                  <span className="text-xs text-gray-400 font-mono">{code}</span>
                </div>
                <span className={cn(
                  'text-xs font-semibold px-2 py-1 rounded-full',
                  code === 'free' ? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' :
                  code === 'starter' ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300' :
                  code === 'pro' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300' :
                  'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300',
                )}>
                  {code === 'free' ? 'Free' : 'Paid'}
                </span>
              </div>

              {/* Price */}
              <div className="mb-4">
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                  Price (USD)
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">$</span>
                  <input
                    type="number"
                    min={0}
                    value={plan.price}
                    onChange={(e) => updatePlan(code, 'price', Number(e.target.value))}
                    className="w-24 px-2 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-red-500/20"
                  />
                  <span className="text-xs text-gray-400">/ {plan.period}</span>
                </div>
              </div>

              {/* Limits */}
              <div className="space-y-3">
                {LIMIT_FIELDS.map((f) => {
                  const val = (plan as unknown as Record<string, unknown>)[f.key] as number | null;
                  const isUnlimited = val === null;
                  return (
                    <div key={f.key}>
                      <label className="flex items-center justify-between text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                        {f.label}
                        <label className="flex items-center gap-1 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isUnlimited}
                            onChange={(e) => updatePlan(code, f.key, e.target.checked ? null : 0)}
                            className="rounded border-gray-300 text-red-600 focus:ring-red-500 h-3.5 w-3.5"
                          />
                          <span className="text-[10px] text-gray-400">Unlimited</span>
                        </label>
                      </label>
                      {!isUnlimited && (
                        <input
                          type="number"
                          min={0}
                          value={val ?? 0}
                          onChange={(e) => updatePlan(code, f.key, Number(e.target.value))}
                          className="w-full px-2 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-red-500/20"
                        />
                      )}
                      {isUnlimited && (
                        <div className="px-2 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                          Unlimited
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Premium access toggle */}
              <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-800">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={plan.access_premium}
                    onChange={(e) => updatePlan(code, 'access_premium', e.target.checked)}
                    className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Premium features access</span>
                </label>
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <div className="flex items-center gap-2 mb-4 px-4 py-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Plan Settings
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-sm text-emerald-600 dark:text-emerald-400">
            <Check className="w-4 h-4" /> Saved &amp; applied
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

function LoadingSpinner() {
  return (
    <div className="flex justify-center py-12">
      <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
    </div>
  );
}
