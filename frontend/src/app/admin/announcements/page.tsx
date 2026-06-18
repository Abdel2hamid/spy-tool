'use client';

import { useState, useEffect, useCallback } from 'react';
import { AdminShell } from '@/components/AdminShell';
import {
  adminGetAnnouncements,
  adminCreateAnnouncement,
  adminUpdateAnnouncement,
  adminDeleteAnnouncement,
  AdminAnnouncement,
} from '@/lib/api';
import {
  RefreshCw,
  Plus,
  Trash2,
  X,
  Megaphone,
  Info,
  AlertTriangle,
  CheckCircle,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';

function typeBadge(type: string): { className: string; label: string } {
  switch (type) {
    case 'warning':
      return {
        className:
          'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
        label: 'Warning',
      };
    case 'success':
      return {
        className:
          'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
        label: 'Success',
      };
    default:
      return {
        className:
          'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
        label: 'Info',
      };
  }
}

function TypeIcon({ type }: { type: string }) {
  switch (type) {
    case 'warning':
      return <AlertTriangle className="h-5 w-5 text-amber-500" />;
    case 'success':
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    default:
      return <Info className="h-5 w-5 text-blue-500" />;
  }
}

export default function AdminAnnouncementsPage() {
  const [announcements, setAnnouncements] = useState<AdminAnnouncement[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    adminGetAnnouncements()
      .then((d) => setAnnouncements(d.announcements))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleToggle(a: AdminAnnouncement) {
    setTogglingId(a.id);
    try {
      await adminUpdateAnnouncement(a.id, { is_active: !a.is_active });
      load();
    } catch {
      // ignore
    } finally {
      setTogglingId(null);
    }
  }

  async function handleDelete(a: AdminAnnouncement) {
    if (
      !confirm(
        `Delete announcement "${a.title}"? This cannot be undone.`,
      )
    )
      return;
    setDeletingId(a.id);
    try {
      await adminDeleteAnnouncement(a.id);
      load();
    } catch {
      // ignore
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <AdminShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Announcements
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Manage platform-wide announcements
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition"
            >
              <Plus className="h-4 w-4" />
              New Announcement
            </button>
          </div>
        </div>

        {/* Announcement Cards */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : announcements.length === 0 ? (
          <div className="rounded-xl border border-gray-200 bg-white py-16 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex flex-col items-center text-gray-400">
              <Megaphone className="h-8 w-8 mb-2" />
              <p className="text-sm">No announcements yet</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {announcements.map((a) => {
              const badge = typeBadge(a.type);
              return (
                <div
                  key={a.id}
                  className={`rounded-xl border bg-white p-5 transition dark:bg-gray-900 ${
                    a.is_active
                      ? 'border-gray-200 dark:border-gray-800'
                      : 'border-dashed border-gray-300 opacity-60 dark:border-gray-700'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className="mt-0.5 flex-shrink-0">
                      <TypeIcon type={a.type} />
                    </div>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                          {a.title}
                        </h3>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                        {!a.is_active && (
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wide dark:bg-gray-800 dark:text-gray-400">
                            Inactive
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-3">
                        {a.message}
                      </p>
                      <p className="mt-2 text-xs text-gray-400">
                        Created{' '}
                        {a.created_at
                          ? new Date(a.created_at).toLocaleDateString(
                              undefined,
                              {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              },
                            )
                          : '\u2014'}
                      </p>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-shrink-0 items-center gap-2">
                      <button
                        onClick={() => handleToggle(a)}
                        disabled={togglingId === a.id}
                        title={
                          a.is_active ? 'Deactivate' : 'Activate'
                        }
                        className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300 transition"
                      >
                        {togglingId === a.id ? (
                          <RefreshCw className="h-5 w-5 animate-spin" />
                        ) : a.is_active ? (
                          <ToggleRight className="h-5 w-5 text-green-500" />
                        ) : (
                          <ToggleLeft className="h-5 w-5" />
                        )}
                      </button>
                      <button
                        onClick={() => handleDelete(a)}
                        disabled={deletingId === a.id}
                        title="Delete announcement"
                        className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400 transition"
                      >
                        {deletingId === a.id ? (
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Create Modal */}
        {showCreate && (
          <CreateAnnouncementModal
            onClose={() => setShowCreate(false)}
            onCreated={() => {
              setShowCreate(false);
              load();
            }}
          />
        )}
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Create Announcement Modal
// ---------------------------------------------------------------------------

function CreateAnnouncementModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [type, setType] = useState('info');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!title.trim() || !message.trim()) {
      setError('Title and message are required');
      return;
    }
    setSaving(true);
    try {
      await adminCreateAnnouncement({
        title: title.trim(),
        message: message.trim(),
        type,
      });
      onCreated();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to create announcement',
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            New Announcement
          </h3>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
              Title *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Announcement title"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
              Message *
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Write your announcement message..."
              rows={4}
              className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
              Type
            </label>
            <div className="flex gap-2">
              {(['info', 'warning', 'success'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition ${
                    type === t
                      ? t === 'info'
                        ? 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-300'
                        : t === 'warning'
                          ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300'
                          : 'border-green-300 bg-green-50 text-green-700 dark:border-green-700 dark:bg-green-950 dark:text-green-300'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800'
                  }`}
                >
                  {t === 'info' && <Info className="h-3.5 w-3.5" />}
                  {t === 'warning' && (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  )}
                  {t === 'success' && (
                    <CheckCircle className="h-3.5 w-3.5" />
                  )}
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/50 dark:text-red-400">
              {error}
            </div>
          )}

          <div className="flex gap-2 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
              Create Announcement
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
