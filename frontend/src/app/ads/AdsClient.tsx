'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getAdIntelligenceList,
  AdIntelligenceListItem,
  AdIntelligenceListResponse,
} from '@/lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NETWORK_LABELS: Record<string, { label: string; color: string }> = {
  apple_search_ads: { label: 'Apple Search Ads', color: 'bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300' },
  meta:             { label: 'Meta',              color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300' },
  google_uac:       { label: 'Google UAC',        color: 'bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-300' },
};

function NetworkBadge({ network }: { network: string }) {
  const meta = NETWORK_LABELS[network] ?? { label: network, color: 'bg-gray-100 text-gray-600' };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${meta.color}`}>
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
      <div className="h-1.5 w-16 rounded-full bg-gray-200 dark:bg-gray-700">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500">{pct}%</span>
    </div>
  );
}

function AppIcon({ src, name }: { src: string | null; name: string }) {
  if (!src) {
    return (
      <div className="h-9 w-9 flex-shrink-0 rounded-xl bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center">
        <span className="text-xs font-bold text-white">{name[0]?.toUpperCase()}</span>
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={name} className="h-9 w-9 flex-shrink-0 rounded-xl object-cover" />;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const NETWORKS = ['all', 'apple_search_ads', 'meta', 'google_uac'];

export default function AdsClient() {
  const [data, setData] = useState<AdIntelligenceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [network, setNetwork] = useState('all');
  const [activeOnly, setActiveOnly] = useState(true);
  const [skip, setSkip] = useState(0);
  const limit = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getAdIntelligenceList({
        network: network !== 'all' ? network : undefined,
        active_only: activeOnly,
        skip,
        limit,
      });
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [network, activeOnly, skip]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const applyNetwork = (n: string) => { setNetwork(n); setSkip(0); };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Ad Intelligence</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Apps with detected advertising activity — campaigns and creatives by network.
        </p>
      </div>

      {/* Stats row */}
      {data && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Apps with Ads</p>
            <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{data.active_count}</p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Showing</p>
            <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{data.total}</p>
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
        <div className="flex gap-1">
          {NETWORKS.map(n => (
            <button
              key={n}
              onClick={() => applyNetwork(n)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                network === n
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300'
              }`}
            >
              {n === 'all' ? 'All Networks' : (NETWORK_LABELS[n]?.label ?? n)}
            </button>
          ))}
        </div>
        <div className="ml-auto">
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={e => { setActiveOnly(e.target.checked); setSkip(0); }}
              className="rounded border-gray-300"
            />
            Active only
          </label>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
        {loading ? (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4 animate-pulse">
                <div className="h-9 w-9 flex-shrink-0 rounded-xl bg-gray-200 dark:bg-gray-700" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-40 rounded bg-gray-200 dark:bg-gray-700" />
                  <div className="h-2.5 w-56 rounded bg-gray-100 dark:bg-gray-800" />
                </div>
                <div className="flex gap-1.5">
                  <div className="h-5 w-20 rounded-full bg-gray-200 dark:bg-gray-700" />
                  <div className="h-5 w-16 rounded-full bg-gray-200 dark:bg-gray-700" />
                </div>
              </div>
            ))}
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="text-4xl mb-3">📢</div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">No ad intelligence data yet</p>
            <p className="mt-1 text-xs text-gray-500">
              The ad intelligence job runs every 6 hours for candidate apps showing momentum.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {data.items.map(item => (
              <AdRow key={item.app_db_id} item={item} />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total > limit && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            {skip + 1}–{Math.min(skip + limit, data.total)} of {data.total}
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

function AdRow({ item }: { item: AdIntelligenceListItem }) {
  const lastSeen = item.last_ad_seen ? new Date(item.last_ad_seen) : null;
  const firstSeen = item.first_ad_seen ? new Date(item.first_ad_seen) : null;
  const runDays = firstSeen && lastSeen
    ? Math.floor((lastSeen.getTime() - firstSeen.getTime()) / 86_400_000)
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
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {item.networks.map(n => <NetworkBadge key={n} network={n} />)}
        </div>
        <div className="mt-1 flex items-center gap-3 text-[11px] text-gray-400">
          <span>{item.active_campaigns} campaign{item.active_campaigns !== 1 ? 's' : ''}</span>
          <span>· {item.active_creatives} creative{item.active_creatives !== 1 ? 's' : ''}</span>
          {runDays !== null && runDays > 0 && <span>· Running {runDays}d</span>}
          {lastSeen && <span>· Last seen {lastSeen.toLocaleDateString()}</span>}
        </div>
      </div>

      <div className="flex-shrink-0">
        <ConfidenceBar value={item.max_confidence} />
      </div>
    </div>
  );
}
