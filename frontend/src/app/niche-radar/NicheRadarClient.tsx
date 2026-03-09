'use client';

import { useState, useEffect } from 'react';
import { AppShell } from '@/components/AppShell';
import { getNicheRadar, NicheRadarItem } from '@/lib/api';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Radar, TrendingUp, Zap, Search, RefreshCw } from 'lucide-react';

const SIGNAL_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  keyword_growth: { label: 'Keyword Growth', color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200' },
  ranking_momentum: { label: 'Ranking Momentum', color: 'text-blue-700', bg: 'bg-blue-50 border-blue-200' },
  feature_gap: { label: 'Feature Gap', color: 'text-indigo-700', bg: 'bg-indigo-50 border-indigo-200' },
};

function ScoreCircle({ score }: { score: number }) {
  const color = score >= 70 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : 'text-red-500';
  const ring = score >= 70 ? 'border-emerald-500' : score >= 50 ? 'border-amber-500' : 'border-red-400';
  return (
    <div className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full border-2 ${ring}`}>
      <span className={`text-sm font-bold ${color}`}>{score}</span>
    </div>
  );
}

function SignalIcon({ type }: { type: string }) {
  if (type === 'keyword_growth') return <Search className="h-3.5 w-3.5" />;
  if (type === 'ranking_momentum') return <TrendingUp className="h-3.5 w-3.5" />;
  return <Zap className="h-3.5 w-3.5" />;
}

function NicheCard({ niche }: { niche: NicheRadarItem }) {
  const cfg = SIGNAL_CONFIG[niche.signal_type] ?? { label: niche.signal_type, color: 'text-gray-700', bg: 'bg-gray-50 border-gray-200' };
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${cfg.bg} ${cfg.color}`}>
            <SignalIcon type={niche.signal_type} />
            {cfg.label}
          </span>
        </div>
        <ScoreCircle score={niche.niche_score} />
      </div>

      <h3 className="text-base font-semibold text-gray-900 dark:text-white leading-snug">
        {niche.niche_name}
      </h3>

      <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
        {niche.description}
      </p>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        {(niche.keywords ?? []).slice(0, 3).map((kw) => (
          <span
            key={kw}
            className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400"
          >
            {kw}
          </span>
        ))}
        {niche.app_count > 0 && (
          <span className="ml-auto text-xs text-gray-400">
            {niche.app_count} app{niche.app_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>
    </div>
  );
}

const FILTER_LABELS: Record<string, string> = {
  all: 'All Signals',
  keyword_growth: 'Keyword Growth',
  ranking_momentum: 'Ranking Momentum',
  feature_gap: 'Feature Gaps',
};

export default function NicheRadarClient() {
  const [niches, setNiches] = useState<NicheRadarItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scannedAt, setScannedAt] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getNicheRadar(30);
      setNiches(Array.isArray(data?.niches) ? data.niches : []);
      setScannedAt(data?.scanned_at ?? null);
    } catch (e) {
      setError('Failed to load niche radar data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = filter === 'all' ? niches : niches.filter((n) => n.signal_type === filter);

  return (
    <ErrorBoundary>
    <AppShell>
      <div className="space-y-6 p-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-600">
              <Radar className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Niche Radar</h1>
              <p className="text-sm text-gray-500">
                Emerging App Store micro-niches detected from keyword, ranking, and review signals
              </p>
            </div>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Stats row */}
        {!loading && niches.length > 0 && (
          <div className="flex flex-wrap gap-4">
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
              <p className="text-xs text-gray-500">Total Niches</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">{niches.length}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
              <p className="text-xs text-gray-500">High Score (≥70)</p>
              <p className="text-xl font-bold text-emerald-600">{niches.filter(n => n.niche_score >= 70).length}</p>
            </div>
            {scannedAt && (
              <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
                <p className="text-xs text-gray-500">Last Scanned</p>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {new Date(scannedAt).toLocaleTimeString()}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Filter pills */}
        <div className="flex flex-wrap gap-2">
          {Object.entries(FILTER_LABELS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === key
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400'
              }`}
            >
              {label}
              {key !== 'all' && (
                <span className="ml-1.5 text-xs opacity-70">
                  {niches.filter(n => n.signal_type === key).length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-48 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-600 dark:border-red-800 dark:bg-red-950/30">
            {error}
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center dark:border-gray-700">
            <Radar className="mx-auto mb-3 h-10 w-10 text-gray-400" />
            <p className="text-gray-500">
              {niches.length === 0
                ? 'No niches detected yet. Add keywords and track apps to generate signals.'
                : 'No niches match this filter.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((niche, i) => (
              <NicheCard key={`${niche.niche_name}-${i}`} niche={niche} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
    </ErrorBoundary>
  );
}
