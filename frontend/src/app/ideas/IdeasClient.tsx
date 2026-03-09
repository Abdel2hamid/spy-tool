'use client';

import { useState, useEffect, useCallback } from 'react';
import { AppIdea, AppIdeaListResponse, getIdeas, generateIdeas } from '@/lib/api';
import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import {
  Lightbulb, Sparkles, RefreshCw, Package, Key,
  Globe, Zap, TrendingUp, Search,
} from 'lucide-react';

// ─── Pattern config ────────────────────────────────────────────────────────

const PATTERNS: Record<string, {
  label: string;
  icon: React.ElementType;
  border: string;
  badge: string;
  glow: string;
  iconBg: string;
}> = {
  feature_gap: {
    label: 'Feature Gap',
    icon: Zap,
    border: 'border-l-indigo-500',
    badge: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300',
    glow: 'from-indigo-50 to-transparent dark:from-indigo-950/20',
    iconBg: 'bg-indigo-100 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400',
  },
  weak_market: {
    label: 'Weak Market',
    icon: Globe,
    border: 'border-l-rose-500',
    badge: 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300',
    glow: 'from-rose-50 to-transparent dark:from-rose-950/20',
    iconBg: 'bg-rose-100 text-rose-600 dark:bg-rose-950 dark:text-rose-400',
  },
  keyword_gap: {
    label: 'Keyword Gap',
    icon: Search,
    border: 'border-l-emerald-500',
    badge: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
    glow: 'from-emerald-50 to-transparent dark:from-emerald-950/20',
    iconBg: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400',
  },
};

function patternCfg(type: string) {
  return PATTERNS[type] ?? {
    label: type,
    icon: Lightbulb,
    border: 'border-l-gray-400',
    badge: 'bg-gray-100 text-gray-600',
    glow: 'from-gray-50 to-transparent',
    iconBg: 'bg-gray-100 text-gray-600',
  };
}

// ─── Score ring ────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
  const textColor = score >= 70
    ? 'text-emerald-600 dark:text-emerald-400'
    : score >= 50
    ? 'text-amber-600 dark:text-amber-400'
    : 'text-red-600 dark:text-red-400';

  return (
    <div className="relative flex items-center justify-center w-14 h-14 flex-shrink-0">
      <svg width="56" height="56" className="-rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" stroke="currentColor"
          strokeWidth="3.5" className="text-gray-100 dark:text-gray-800" />
        <circle cx="28" cy="28" r={r} fill="none" stroke={color}
          strokeWidth="3.5" strokeDasharray={circ}
          strokeDashoffset={circ - fill} strokeLinecap="round" />
      </svg>
      <span className={`absolute text-sm font-bold ${textColor}`}>
        {Math.round(score)}
      </span>
    </div>
  );
}

// ─── Idea card ─────────────────────────────────────────────────────────────

function IdeaCard({ idea }: { idea: AppIdea }) {
  const cfg = patternCfg(idea.pattern_type);
  const PatternIcon = cfg.icon;

  return (
    <div className={`relative flex flex-col rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm hover:shadow-md transition-all duration-200 border-l-4 ${cfg.border} overflow-hidden`}>
      {/* Subtle gradient header wash */}
      <div className={`absolute top-0 inset-x-0 h-20 bg-gradient-to-b ${cfg.glow} pointer-events-none`} />

      <div className="relative p-5 flex flex-col gap-4">
        {/* Top row: badge + score */}
        <div className="flex items-start justify-between gap-3">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${cfg.badge}`}>
            <PatternIcon className="h-3 w-3" />
            {cfg.label}
          </span>
          <ScoreRing score={idea.opportunity_score} />
        </div>

        {/* Title */}
        <h3 className="font-semibold text-gray-900 dark:text-white text-[15px] leading-snug pr-2">
          {idea.idea_title}
        </h3>

        {/* Description */}
        {idea.idea_description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed line-clamp-2">
            {idea.idea_description}
          </p>
        )}

        {/* Divider */}
        <div className="border-t border-gray-100 dark:border-gray-800" />

        {/* Reasoning bullets */}
        {(idea.reasoning?.length ?? 0) > 0 && (
          <ul className="space-y-1.5">
            {(idea.reasoning ?? []).map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-600 dark:text-gray-400">
                <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-gray-300 dark:bg-gray-600" />
                {r}
              </li>
            ))}
          </ul>
        )}

        {/* Footer tags */}
        <div className="flex flex-wrap items-center gap-1.5 mt-auto pt-1">
          {idea.category && (
            <span className="inline-flex items-center gap-1 rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs text-gray-600 dark:text-gray-400 font-medium">
              <Package className="h-3 w-3 opacity-60" />
              {idea.category}
            </span>
          )}
          {idea.primary_keyword && (
            <span className="inline-flex items-center gap-1 rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs text-gray-600 dark:text-gray-400 font-medium">
              <Key className="h-3 w-3 opacity-60" />
              {idea.primary_keyword}
            </span>
          )}
          {(idea.related_app_ids?.length ?? 0) > 0 && (
            <span className="ml-auto text-xs text-gray-400 dark:text-gray-600">
              {idea.related_app_ids.length} app{idea.related_app_ids.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm animate-pulse border-l-4 border-l-gray-200 dark:border-l-gray-700">
      <div className="flex items-start justify-between mb-4">
        <div className="h-6 w-28 rounded-full bg-gray-200 dark:bg-gray-700" />
        <div className="h-14 w-14 rounded-full bg-gray-200 dark:bg-gray-700" />
      </div>
      <div className="h-4 w-4/5 rounded bg-gray-200 dark:bg-gray-700 mb-2" />
      <div className="h-4 w-2/3 rounded bg-gray-200 dark:bg-gray-700 mb-4" />
      <div className="border-t border-gray-100 dark:border-gray-800 mb-4" />
      <div className="space-y-2">
        <div className="h-3 w-full rounded bg-gray-100 dark:bg-gray-800" />
        <div className="h-3 w-5/6 rounded bg-gray-100 dark:bg-gray-800" />
        <div className="h-3 w-3/4 rounded bg-gray-100 dark:bg-gray-800" />
      </div>
    </div>
  );
}

// ─── Constants ────────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { label: 'Score', value: 'opportunity_score', icon: TrendingUp },
  { label: 'Category', value: 'category', icon: Package },
  { label: 'Keyword', value: 'primary_keyword', icon: Key },
];

const FILTER_OPTIONS = [
  { label: 'All', value: '', icon: Sparkles },
  { label: 'Feature Gap', value: 'feature_gap', icon: Zap },
  { label: 'Weak Market', value: 'weak_market', icon: Globe },
  { label: 'Keyword Gap', value: 'keyword_gap', icon: Search },
];

// ─── Main component ────────────────────────────────────────────────────────

export default function IdeasClient() {
  const [data, setData] = useState<AppIdeaListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sortBy, setSortBy] = useState('opportunity_score');
  const [patternFilter, setPatternFilter] = useState('');
  const [error, setError] = useState<string | null>(null);

  const fetchIdeas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getIdeas({
        sort_by: sortBy,
        sort_order: 'desc',
        pattern_type: patternFilter || undefined,
        limit: 60,
      });
      setData(result);
    } catch {
      setError('Failed to load ideas. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, [sortBy, patternFilter]);

  useEffect(() => { fetchIdeas(); }, [fetchIdeas]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateIdeas();
      setData(result);
    } catch {
      setError('Generation failed. Check backend logs.');
    } finally {
      setGenerating(false);
    }
  };

  const ideas = data?.ideas ?? [];
  const counts = {
    feature_gap: ideas.filter(i => i.pattern_type === 'feature_gap').length,
    weak_market: ideas.filter(i => i.pattern_type === 'weak_market').length,
    keyword_gap: ideas.filter(i => i.pattern_type === 'keyword_gap').length,
  };

  return (
    <ErrorBoundary>
    <AppShell>
      <div className="space-y-6">

        {/* ── Hero header ──────────────────────────────────────────────── */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-violet-600 to-purple-700 p-6 shadow-lg">
          <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
          <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
                <Lightbulb className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">AI Opportunities</h1>
                <p className="mt-0.5 text-sm text-indigo-200">
                  App ideas surfaced from feature gaps, weak markets & keyword signals
                </p>
              </div>
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="inline-flex items-center gap-2 rounded-xl bg-white/20 hover:bg-white/30 border border-white/30 px-5 py-2.5 text-sm font-semibold text-white backdrop-blur-sm transition-all disabled:opacity-60 shadow-sm"
            >
              <RefreshCw className={`h-4 w-4 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Analyzing signals…' : 'Generate Ideas'}
            </button>
          </div>

          {/* Stats strip inside hero */}
          {data && (
            <div className="relative mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Total Ideas', value: data.total, color: 'text-white' },
                { label: 'Feature Gaps', value: counts.feature_gap, color: 'text-indigo-200' },
                { label: 'Weak Markets', value: counts.weak_market, color: 'text-rose-300' },
                { label: 'Keyword Gaps', value: counts.keyword_gap, color: 'text-emerald-300' },
              ].map((s) => (
                <div key={s.label} className="rounded-xl bg-white/10 px-4 py-3 backdrop-blur-sm border border-white/10">
                  <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                  <p className="text-xs text-indigo-200 mt-0.5">{s.label}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Error ────────────────────────────────────────────────────── */}
        {error && (
          <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-700 dark:text-red-400">
            {error}
          </div>
        )}

        {/* ── Controls bar ─────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          {/* Pattern filter tabs */}
          <div className="flex items-center gap-1 rounded-xl bg-gray-100 dark:bg-gray-800/60 p-1">
            {FILTER_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              const active = patternFilter === opt.value;
              return (
                <button
                  key={opt.value}
                  onClick={() => setPatternFilter(opt.value)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                    active
                      ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {opt.label}
                </button>
              );
            })}
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2 sm:ml-auto">
            <span className="text-xs text-gray-500 dark:text-gray-400">Sort by</span>
            <div className="flex items-center gap-1 rounded-xl bg-gray-100 dark:bg-gray-800/60 p-1">
              {SORT_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const active = sortBy === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setSortBy(opt.value)}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                      active
                        ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm'
                        : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── Last generated note ──────────────────────────────────────── */}
        {data?.last_generated && (
          <p className="text-xs text-gray-400 dark:text-gray-600 -mt-2">
            Last generated: {new Date(data.last_generated).toLocaleString()}
          </p>
        )}

        {/* ── Grid ─────────────────────────────────────────────────────── */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : ideas.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-800 py-20 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 dark:bg-gray-800 mb-4">
              <Lightbulb className="h-8 w-8 text-gray-400 dark:text-gray-600" />
            </div>
            <p className="font-semibold text-gray-700 dark:text-gray-300">No ideas yet</p>
            <p className="text-sm text-gray-400 dark:text-gray-600 mt-1 max-w-xs">
              Click <strong>Generate Ideas</strong> to analyze signals from your tracked apps
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {ideas.map((idea) => <IdeaCard key={idea.id} idea={idea} />)}
          </div>
        )}
      </div>
    </AppShell>
    </ErrorBoundary>
  );
}
