'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getCampaignTrackingList,
  CampaignTrackingListItem,
  CampaignTrackingListResponse,
} from '@/lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const EVENT_TYPE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  paid_push:        { label: 'Paid Push',        color: 'text-red-700 dark:text-red-400',    bg: 'bg-red-50 dark:bg-red-950/40'    },
  organic_breakout: { label: 'Organic Breakout', color: 'text-green-700 dark:text-green-400', bg: 'bg-green-50 dark:bg-green-950/40' },
  mixed:            { label: 'Mixed',             color: 'text-amber-700 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/40' },
  momentum_surge:   { label: 'Momentum Surge',   color: 'text-blue-700 dark:text-blue-400',   bg: 'bg-blue-50 dark:bg-blue-950/40'   },
  campaign_cooling: { label: 'Cooling',           color: 'text-gray-600 dark:text-gray-400',   bg: 'bg-gray-50 dark:bg-gray-800/40'   },
  unknown_unusual:  { label: 'Unusual',           color: 'text-purple-700 dark:text-purple-400',bg: 'bg-purple-50 dark:bg-purple-950/40'},
};

function EventBadge({ type }: { type: string }) {
  const meta = EVENT_TYPE_LABELS[type] ?? { label: type, color: 'text-gray-600', bg: 'bg-gray-100' };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${meta.bg} ${meta.color}`}>
      {meta.label}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 70 ? 'bg-green-500' :
    pct >= 40 ? 'bg-amber-500' :
    'bg-gray-400';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-gray-200 dark:bg-gray-700">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500">{pct}%</span>
    </div>
  );
}

function AppIcon({ src, name }: { src: string | null; name: string }) {
  if (!src) {
    return (
      <div className="h-9 w-9 flex-shrink-0 rounded-xl bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center">
        <span className="text-xs font-bold text-white">{name[0]?.toUpperCase()}</span>
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={name} className="h-9 w-9 flex-shrink-0 rounded-xl object-cover" />
  );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

const EVENT_TYPES = ['all', 'paid_push', 'organic_breakout', 'mixed', 'momentum_surge', 'campaign_cooling', 'unknown_unusual'];

interface Filters {
  event_type: string;
  active_only: boolean;
  min_confidence: number;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CampaignsClient() {
  const [data, setData] = useState<CampaignTrackingListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>({
    event_type: 'all',
    active_only: true,
    min_confidence: 0.3,
  });
  const [skip, setSkip] = useState(0);
  const limit = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getCampaignTrackingList({
        event_type: filters.event_type !== 'all' ? filters.event_type : undefined,
        active_only: filters.active_only,
        min_confidence: filters.min_confidence,
        skip,
        limit,
      });
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [filters, skip]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const applyFilter = (patch: Partial<Filters>) => {
    setFilters(f => ({ ...f, ...patch }));
    setSkip(0);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Campaign Tracking</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Growth signal detection — paid pushes, organic breakouts, and momentum surges.
        </p>
      </div>

      {/* Summary chips */}
      {data?.by_type && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.by_type).map(([type, count]) => {
            const meta = EVENT_TYPE_LABELS[type];
            if (!meta) return null;
            return (
              <button
                key={type}
                onClick={() => applyFilter({ event_type: type })}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${meta.bg} ${meta.color} cursor-pointer hover:opacity-80 transition`}
              >
                {meta.label}
                <span className="rounded-full bg-white/30 px-1.5 py-0.5">{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
        {/* Event type tabs */}
        <div className="flex flex-wrap gap-1">
          {EVENT_TYPES.map(t => (
            <button
              key={t}
              onClick={() => applyFilter({ event_type: t })}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                filters.event_type === t
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300'
              }`}
            >
              {t === 'all' ? 'All' : (EVENT_TYPE_LABELS[t]?.label ?? t)}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
            <input
              type="checkbox"
              checked={filters.active_only}
              onChange={e => applyFilter({ active_only: e.target.checked })}
              className="rounded border-gray-300"
            />
            Active only
          </label>

          <select
            value={filters.min_confidence}
            onChange={e => applyFilter({ min_confidence: Number(e.target.value) })}
            className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          >
            <option value={0.0}>Any confidence</option>
            <option value={0.3}>≥30% confidence</option>
            <option value={0.5}>≥50% confidence</option>
            <option value={0.7}>≥70% confidence</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
        {loading ? (
          <div className="space-y-0 divide-y divide-gray-100 dark:divide-gray-800">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4 animate-pulse">
                <div className="h-9 w-9 flex-shrink-0 rounded-xl bg-gray-200 dark:bg-gray-700" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-40 rounded bg-gray-200 dark:bg-gray-700" />
                  <div className="h-2.5 w-64 rounded bg-gray-100 dark:bg-gray-800" />
                </div>
                <div className="h-5 w-24 rounded-full bg-gray-200 dark:bg-gray-700" />
                <div className="h-2 w-20 rounded bg-gray-200 dark:bg-gray-700" />
              </div>
            ))}
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="text-4xl mb-3">📊</div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">No growth events detected yet</p>
            <p className="mt-1 text-xs text-gray-500">
              The campaign detection job runs every 2 hours after the blowing-up scorer.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {data.items.map((item) => (
              <CampaignRow key={`${item.app_db_id}-${item.detected_at}`} item={item} />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total > limit && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {skip + 1}–{Math.min(skip + limit, data.total)} of {data.total}
          </p>
          <div className="flex gap-2">
            <button
              disabled={skip === 0}
              onClick={() => setSkip(Math.max(0, skip - limit))}
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
            >
              Previous
            </button>
            <button
              disabled={skip + limit >= data.total}
              onClick={() => setSkip(skip + limit)}
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium disabled:opacity-40 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CampaignRow({ item }: { item: CampaignTrackingListItem }) {
  const detected = new Date(item.detected_at);
  const started = item.started_at_estimate ? new Date(item.started_at_estimate) : null;
  const daysSinceStart = started
    ? Math.floor((Date.now() - started.getTime()) / 86_400_000)
    : null;

  return (
    <div className="flex items-start gap-4 p-4 hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition">
      <AppIcon src={item.icon_url} name={item.name} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-gray-900 dark:text-white truncate">{item.name}</span>
          {item.current_rank && (
            <span className="text-xs text-gray-400">#{item.current_rank}</span>
          )}
          {item.primary_category && (
            <span className="text-xs text-gray-400">· {item.primary_category}</span>
          )}
        </div>
        {item.explanation && (
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{item.explanation}</p>
        )}
        <div className="mt-1 flex items-center gap-3 text-[11px] text-gray-400">
          <span>Detected {detected.toLocaleDateString()}</span>
          {daysSinceStart !== null && (
            <span>· Started ~{daysSinceStart}d ago</span>
          )}
          {item.blowing_up_score != null && (
            <span>· BU score {item.blowing_up_score.toFixed(0)}</span>
          )}
        </div>
      </div>

      <div className="flex flex-col items-end gap-2 flex-shrink-0">
        <EventBadge type={item.event_type} />
        <ConfidenceBar value={item.confidence} />
      </div>
    </div>
  );
}
