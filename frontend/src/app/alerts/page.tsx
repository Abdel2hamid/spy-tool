'use client';

export const dynamic = 'force-dynamic';

import { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components';
import { useAuth } from '@/lib/auth';
import {
  getAlerts,
  createAlert,
  updateAlert,
  deleteAlert,
  getAlertEvents,
  markAlertEventRead,
  markAllAlertEventsRead,
  AlertItem,
  AlertEventItem,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  Bell,
  TrendingUp,
  Search,
  Zap,
  ArrowDownRight,
  Plus,
  X,
  Trash2,
  ToggleLeft,
  ToggleRight,
  CheckCheck,
  Loader2,
  ChevronDown,
  AlertTriangle,
  CheckCircle2,
  Clock,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALERT_TYPES = [
  {
    value: 'app_trending',
    label: 'App Trending',
    description: 'When a tracked app starts gaining unusual momentum',
    icon: TrendingUp,
    accent: 'emerald',
    defaultConfig: { threshold: 60 },
    configFields: [
      { key: 'app_name', label: 'App name (keyword)', type: 'text', placeholder: 'e.g. Instagram' },
      { key: 'threshold', label: 'Trending score threshold', type: 'number', placeholder: '60' },
    ],
  },
  {
    value: 'keyword_rising',
    label: 'Keyword Rising',
    description: 'When a keyword opportunity score crosses a threshold',
    icon: Search,
    accent: 'blue',
    defaultConfig: { threshold: 70 },
    configFields: [
      { key: 'keyword', label: 'Keyword to watch', type: 'text', placeholder: 'e.g. photo editor' },
      { key: 'threshold', label: 'Opportunity score threshold', type: 'number', placeholder: '70' },
    ],
  },
  {
    value: 'new_opportunity',
    label: 'New Opportunity',
    description: 'When a new high-score niche or feature gap is detected',
    icon: Zap,
    accent: 'indigo',
    defaultConfig: { min_score: 75 },
    configFields: [
      { key: 'category', label: 'Category (optional)', type: 'text', placeholder: 'e.g. Health & Fitness' },
      { key: 'min_score', label: 'Minimum opportunity score', type: 'number', placeholder: '75' },
    ],
  },
  {
    value: 'rank_drop',
    label: 'Rank Drop',
    description: 'When a tracked app drops in chart rankings',
    icon: ArrowDownRight,
    accent: 'red',
    defaultConfig: { drop_positions: 20 },
    configFields: [
      { key: 'app_name', label: 'App name (keyword)', type: 'text', placeholder: 'e.g. My App' },
      { key: 'drop_positions', label: 'Rank drop threshold (positions)', type: 'number', placeholder: '20' },
    ],
  },
] as const;

type AlertTypeValue = (typeof ALERT_TYPES)[number]['value'];

const ACCENT_MAP: Record<string, { bg: string; text: string; border: string }> = {
  emerald: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/40',
    text: 'text-emerald-600 dark:text-emerald-400',
    border: 'border-emerald-200 dark:border-emerald-800',
  },
  blue: {
    bg: 'bg-blue-50 dark:bg-blue-950/40',
    text: 'text-blue-600 dark:text-blue-400',
    border: 'border-blue-200 dark:border-blue-800',
  },
  indigo: {
    bg: 'bg-indigo-50 dark:bg-indigo-950/40',
    text: 'text-indigo-600 dark:text-indigo-400',
    border: 'border-indigo-200 dark:border-indigo-800',
  },
  red: {
    bg: 'bg-red-50 dark:bg-red-950/40',
    text: 'text-red-600 dark:text-red-400',
    border: 'border-red-200 dark:border-red-800',
  },
};

function getAlertTypeMeta(type: string) {
  return ALERT_TYPES.find((t) => t.value === type) ?? ALERT_TYPES[0];
}

// ---------------------------------------------------------------------------
// Create Alert Modal
// ---------------------------------------------------------------------------

function CreateAlertModal({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (body: { alert_type: string; name: string; config: Record<string, unknown> }) => Promise<void>;
}) {
  const [selectedType, setSelectedType] = useState<AlertTypeValue>('app_trending');
  const [name, setName] = useState('');
  const [config, setConfig] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const typeMeta = getAlertTypeMeta(selectedType);

  useEffect(() => {
    if (open) {
      setSelectedType('app_trending');
      setName('');
      setConfig({});
      setError(null);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Please enter a name for this alert.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const parsedConfig: Record<string, unknown> = {};
      for (const field of typeMeta.configFields) {
        const val = config[field.key];
        if (val) {
          parsedConfig[field.key] = field.type === 'number' ? Number(val) : val;
        }
      }
      await onCreate({ alert_type: selectedType, name: name.trim(), config: parsedConfig });
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create alert');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-900">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Create Alert</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Type selector */}
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Alert type</label>
        <div className="grid grid-cols-2 gap-2 mb-4">
          {ALERT_TYPES.map((t) => {
            const accent = ACCENT_MAP[t.accent];
            const selected = selectedType === t.value;
            return (
              <button
                key={t.value}
                onClick={() => { setSelectedType(t.value); setConfig({}); }}
                className={cn(
                  'flex items-center gap-2 rounded-lg border p-3 text-left text-sm transition-colors',
                  selected
                    ? `${accent.border} ${accent.bg} ring-1 ring-current ${accent.text}`
                    : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800',
                )}
              >
                <t.icon className={cn('h-4 w-4 flex-shrink-0', selected ? accent.text : 'text-gray-400')} />
                <span className={cn('font-medium', selected ? accent.text : 'text-gray-700 dark:text-gray-300')}>
                  {t.label}
                </span>
              </button>
            );
          })}
        </div>

        <p className="mb-4 text-xs text-gray-500 dark:text-gray-400">{typeMeta.description}</p>

        {/* Name */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Alert name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Watch Instagram trending"
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
          />
        </div>

        {/* Config fields */}
        {typeMeta.configFields.map((field) => (
          <div key={field.key} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{field.label}</label>
            <input
              type={field.type}
              value={config[field.key] ?? ''}
              onChange={(e) => setConfig((prev) => ({ ...prev, [field.key]: e.target.value }))}
              placeholder={field.placeholder}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
            />
          </div>
        ))}

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create alert
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alert Card
// ---------------------------------------------------------------------------

function AlertCard({
  alert,
  onToggle,
  onDelete,
}: {
  alert: AlertItem;
  onToggle: (id: number, active: boolean) => void;
  onDelete: (id: number) => void;
}) {
  const meta = getAlertTypeMeta(alert.alert_type);
  const accent = ACCENT_MAP[meta.accent];
  const Icon = meta.icon;

  const configEntries = Object.entries(alert.config).filter(
    ([, v]) => v !== null && v !== undefined && v !== '',
  );

  return (
    <div
      className={cn(
        'rounded-xl border bg-white p-4 transition-opacity dark:bg-gray-900',
        alert.is_active ? 'border-gray-200 dark:border-gray-800' : 'border-gray-100 opacity-60 dark:border-gray-800/50',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className={cn('flex h-9 w-9 items-center justify-center rounded-lg flex-shrink-0', accent.bg)}>
            <Icon className={cn('h-4 w-4', accent.text)} />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate">{alert.name}</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">{meta.label}</p>
            {configEntries.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {configEntries.map(([k, v]) => (
                  <span
                    key={k}
                    className="inline-flex items-center rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                  >
                    {k}: {String(v)}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {alert.unread_count > 0 && (
            <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
              {alert.unread_count}
            </span>
          )}
          <button
            onClick={() => onToggle(alert.id, !alert.is_active)}
            title={alert.is_active ? 'Pause alert' : 'Activate alert'}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
          >
            {alert.is_active ? (
              <ToggleRight className="h-5 w-5 text-emerald-500" />
            ) : (
              <ToggleLeft className="h-5 w-5" />
            )}
          </button>
          <button
            onClick={() => onDelete(alert.id)}
            title="Delete alert"
            className="rounded-md p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 dark:hover:text-red-400"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Event list
// ---------------------------------------------------------------------------

function EventRow({
  event,
  onMarkRead,
}: {
  event: AlertEventItem;
  onMarkRead: (id: number) => void;
}) {
  const meta = getAlertTypeMeta(event.alert_type ?? '');
  const accent = ACCENT_MAP[meta.accent];
  const Icon = meta.icon;
  const timeAgo = event.created_at ? formatTimeAgo(event.created_at) : '';

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border px-4 py-3 transition-colors',
        event.is_read
          ? 'border-gray-100 bg-white dark:border-gray-800/50 dark:bg-gray-900/50'
          : 'border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900',
      )}
    >
      <div className={cn('mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg flex-shrink-0', accent.bg)}>
        <Icon className={cn('h-3.5 w-3.5', accent.text)} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className={cn('text-sm font-medium truncate', event.is_read ? 'text-gray-600 dark:text-gray-400' : 'text-gray-900 dark:text-white')}>
              {event.title}
            </p>
            {event.message && (
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{event.message}</p>
            )}
            {event.alert_name && (
              <p className="mt-1 text-[10px] text-gray-400 dark:text-gray-500">
                Alert: {event.alert_name}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-[10px] text-gray-400 dark:text-gray-500 whitespace-nowrap">{timeAgo}</span>
            {!event.is_read && (
              <button
                onClick={() => onMarkRead(event.id)}
                title="Mark as read"
                className="rounded-md p-1 text-gray-400 hover:bg-emerald-50 hover:text-emerald-500 dark:hover:bg-emerald-950/30 dark:hover:text-emerald-400"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type Tab = 'rules' | 'events';

export default function AlertsPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<Tab>('rules');
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [events, setEvents] = useState<AlertEventItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [alertsRes, eventsRes] = await Promise.all([getAlerts(), getAlertEvents(50)]);
      setAlerts(alertsRes.alerts);
      setEvents(eventsRes.events);
      setUnreadCount(eventsRes.unread_count);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) load();
  }, [token, load]);

  const handleCreate = async (body: { alert_type: string; name: string; config: Record<string, unknown> }) => {
    await createAlert(body);
    await load();
  };

  const handleToggle = async (id: number, active: boolean) => {
    await updateAlert(id, { is_active: active });
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_active: active } : a)));
  };

  const handleDelete = async (id: number) => {
    await deleteAlert(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  const handleMarkRead = async (eventId: number) => {
    await markAlertEventRead(eventId);
    setEvents((prev) => prev.map((e) => (e.id === eventId ? { ...e, is_read: true } : e)));
    setUnreadCount((c) => Math.max(0, c - 1));
  };

  const handleMarkAllRead = async () => {
    await markAllAlertEventsRead();
    setEvents((prev) => prev.map((e) => ({ ...e, is_read: true })));
    setUnreadCount(0);
  };

  if (!token) {
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
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
              <Bell className="h-6 w-6 text-amber-500" />
              Alerts
              {unreadCount > 0 && (
                <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-bold text-white">
                  {unreadCount}
                </span>
              )}
            </h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              Monitor apps, keywords, and opportunities with custom alert rules
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" />
            New alert
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-1 dark:border-gray-800 dark:bg-gray-900/50">
          <button
            onClick={() => setTab('rules')}
            className={cn(
              'rounded-md px-4 py-1.5 text-sm font-medium transition-colors',
              tab === 'rules'
                ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300',
            )}
          >
            Alert Rules ({alerts.length})
          </button>
          <button
            onClick={() => setTab('events')}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium transition-colors',
              tab === 'events'
                ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300',
            )}
          >
            Notifications
            {unreadCount > 0 && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {unreadCount}
              </span>
            )}
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
          </div>
        )}

        {/* Rules tab */}
        {!loading && tab === 'rules' && (
          <div>
            {alerts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/50 p-12 text-center dark:border-gray-700 dark:bg-gray-900/30">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-950/40">
                  <Bell className="h-8 w-8 text-amber-500" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">No alerts yet</h2>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                  Create your first alert to monitor app trends, keyword rises, and new opportunities automatically.
                </p>
                <button
                  onClick={() => setShowCreate(true)}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700"
                >
                  <Plus className="h-4 w-4" />
                  Create your first alert
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <AlertCard
                    key={alert.id}
                    alert={alert}
                    onToggle={handleToggle}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            )}

            {/* Alert type reference */}
            <div className="mt-8">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Available alert types</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {ALERT_TYPES.map((t) => {
                  const accent = ACCENT_MAP[t.accent];
                  return (
                    <div
                      key={t.value}
                      className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
                    >
                      <div className={cn('mb-2 flex h-8 w-8 items-center justify-center rounded-lg', accent.bg)}>
                        <t.icon className={cn('h-4 w-4', accent.text)} />
                      </div>
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white">{t.label}</h4>
                      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{t.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Events tab */}
        {!loading && tab === 'events' && (
          <div>
            {events.length > 0 && unreadCount > 0 && (
              <div className="mb-3 flex justify-end">
                <button
                  onClick={handleMarkAllRead}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
                >
                  <CheckCheck className="h-3.5 w-3.5" />
                  Mark all as read
                </button>
              </div>
            )}
            {events.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/50 p-12 text-center dark:border-gray-700 dark:bg-gray-900/30">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100 dark:bg-gray-800">
                  <Clock className="h-7 w-7 text-gray-400" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">No notifications yet</h2>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                  When your alert rules trigger, notifications will appear here. The system checks your rules periodically.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {events.map((event) => (
                  <EventRow key={event.id} event={event} onMarkRead={handleMarkRead} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create modal */}
      <CreateAlertModal open={showCreate} onClose={() => setShowCreate(false)} onCreate={handleCreate} />
    </AppShell>
  );
}
