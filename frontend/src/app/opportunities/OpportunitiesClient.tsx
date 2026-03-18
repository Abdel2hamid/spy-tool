'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { OpportunityOfDayCard } from '@/components/OpportunityOfDayCard';
import { WeeklyOpportunitiesCard } from '@/components/WeeklyOpportunitiesCard';
import { SimpleChart } from '@/components/Charts';
import {
  OpportunityOfDayWrapper,
  WeeklyOpportunitiesResponse,
  KeywordOpportunity,
  AppIdea,
  AppIdeaListResponse,
  NicheRadarItem,
  getOpportunityOfDay,
  getWeeklyOpportunities,
  getKeywordOpportunities,
  getIdeas,
  generateIdeas,
  getNicheRadar,
} from '@/lib/api';
import {
  Target,
  Search,
  BarChart3,
  Lightbulb,
  Radar,
  RefreshCw,
  Sparkles,
  Package,
  Key,
  Zap,
  Globe,
  TrendingUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type TabId = 'keywords' | 'ideas' | 'niches';

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'keywords', label: 'Keyword Opportunities', icon: Search },
  { id: 'ideas',    label: 'App Ideas',            icon: Lightbulb },
  { id: 'niches',   label: 'Niche Radar',          icon: Radar },
];

// ---------------------------------------------------------------------------
// ── TAB 1: Keyword Opportunities ─────────────────────────────────────────
// ---------------------------------------------------------------------------

function KeywordsTab() {
  const [opportunity, setOpportunity] = useState<OpportunityOfDayWrapper | null>(null);
  const [weeklyOpps, setWeeklyOpps]   = useState<WeeklyOpportunitiesResponse | null>(null);
  const [keywordOpps, setKeywordOpps]   = useState<KeywordOpportunity[]>([]);
  const [loading, setLoading]            = useState(true);

  useEffect(() => {
    Promise.all([
      getOpportunityOfDay().catch(() => null),
      getWeeklyOpportunities().catch(() => null),
      getKeywordOpportunities().then(r => Array.isArray(r) ? r : []).catch(() => []),
    ]).then(([opp, weekly, kwOpps]) => {
      setOpportunity(opp);
      setWeeklyOpps(weekly);
      setKeywordOpps(kwOpps);
      setLoading(false);
    });
  }, []);

  const chartData = keywordOpps.map((kw) => ({
    name: (kw.keyword || '').slice(0, 12),
    score: kw.opportunity_score || 0,
    difficulty: kw.difficulty || 0,
  }));

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-48 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
          <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top 5 Opportunities This Week */}
      {weeklyOpps?.status === 'success' && weeklyOpps.items.length > 0 ? (
        <WeeklyOpportunitiesCard
          items={weeklyOpps.items}
          weekStartDate={weeklyOpps.week_start_date}
        />
      ) : null}

      {/* Opportunity of the Day */}
      {opportunity?.status === 'success' && opportunity.item ? (
        <OpportunityOfDayCard opportunity={opportunity.item} />
      ) : opportunity && (
        <div className="rounded-2xl border border-dashed border-gray-200 dark:border-gray-700 p-6 text-center text-sm text-gray-500 dark:text-gray-400">
          {opportunity.message ?? 'Not enough signals yet. Keep tracking apps to generate an opportunity.'}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top 5 */}
        <div className="card p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="section-heading">Top Keyword Opportunities</h3>
            <Search className="h-4 w-4 text-gray-400" />
          </div>
          <div className="space-y-3">
            {keywordOpps.slice(0, 5).map((kw, i) => (
              <div
                key={kw.keyword || i}
                className="flex items-center justify-between rounded-lg bg-gray-50 p-3 dark:bg-gray-800"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400">
                    {i + 1}
                  </span>
                  <span className="font-medium text-gray-900 dark:text-white">{kw.keyword || 'N/A'}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-500 dark:text-gray-400">
                    {(kw.search_volume || 0).toLocaleString()} vol
                  </span>
                  <span
                    className={cn(
                      'font-semibold',
                      (kw.opportunity_score || 0) > 60
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : (kw.opportunity_score || 0) > 40
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-gray-500 dark:text-gray-400',
                    )}
                  >
                    {(kw.opportunity_score || 0).toFixed(0)}
                  </span>
                </div>
              </div>
            ))}
            {keywordOpps.length === 0 && (
              <div className="flex h-32 flex-col items-center justify-center gap-2 text-center">
                <Search className="h-8 w-8 text-gray-300 dark:text-gray-600" />
                <p className="text-sm text-gray-400 dark:text-gray-500">No keyword opportunities yet</p>
                <p className="text-xs text-gray-300 dark:text-gray-600">Run the keyword pipeline to populate</p>
              </div>
            )}
          </div>
        </div>

        {/* Score distribution */}
        <div className="card p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="section-heading">Score Distribution</h3>
            <BarChart3 className="h-4 w-4 text-gray-400" />
          </div>
          {chartData.length > 0 ? (
            <SimpleChart
              data={chartData}
              dataKey="score"
              xAxisKey="name"
              type="bar"
              color="#10b981"
              height={220}
            />
          ) : (
            <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
              <BarChart3 className="h-8 w-8 text-gray-300 dark:text-gray-600" />
              <p className="text-sm text-gray-400 dark:text-gray-500">No data available</p>
            </div>
          )}
        </div>
      </div>

      {/* Full table */}
      {keywordOpps.length > 0 && (
        <div className="card overflow-hidden">
          <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-800">
            <h3 className="section-heading">All Keyword Opportunities</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th className="text-right">Search Volume</th>
                  <th className="text-right">Difficulty</th>
                  <th className="text-right">Trend</th>
                  <th className="text-right">Score</th>
                  <th className="text-right">Apps</th>
                </tr>
              </thead>
              <tbody>
                {keywordOpps.map((kw) => (
                  <tr key={kw.keyword}>
                    <td className="font-medium text-gray-900 dark:text-white">{kw.keyword || 'N/A'}</td>
                    <td className="text-right text-gray-600 dark:text-gray-300">
                      {(kw.search_volume || 0).toLocaleString()}
                    </td>
                    <td className="text-right">
                      <span
                        className={cn(
                          'pill',
                          (kw.difficulty || 0) < 40
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
                            : (kw.difficulty || 0) < 70
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
                            : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400',
                        )}
                      >
                        {(kw.difficulty || 0).toFixed(0)}
                      </span>
                    </td>
                    <td className="text-right">
                      <span
                        className={cn(
                          'text-sm font-medium',
                          (kw.trend || 0) > 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-red-600 dark:text-red-400',
                        )}
                      >
                        {(kw.trend || 0) > 0 ? '+' : ''}{(kw.trend || 0).toFixed(1)}
                      </span>
                    </td>
                    <td className="text-right font-semibold text-gray-900 dark:text-white">
                      {(kw.opportunity_score || 0).toFixed(0)}
                    </td>
                    <td className="text-right text-gray-600 dark:text-gray-300">{kw.current_apps || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ── TAB 2: App Ideas ─────────────────────────────────────────────────────
// ---------------------------------------------------------------------------

const IDEA_PATTERNS: Record<string, {
  label: string; icon: React.ElementType; border: string; badge: string; glow: string; iconBg: string;
}> = {
  feature_gap: {
    label: 'Feature Gap', icon: Zap,
    border: 'border-l-indigo-500', badge: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300',
    glow: 'from-indigo-50 to-transparent dark:from-indigo-950/20', iconBg: 'bg-indigo-100 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400',
  },
  weak_market: {
    label: 'Weak Market', icon: Globe,
    border: 'border-l-rose-500', badge: 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300',
    glow: 'from-rose-50 to-transparent dark:from-rose-950/20', iconBg: 'bg-rose-100 text-rose-600 dark:bg-rose-950 dark:text-rose-400',
  },
  keyword_gap: {
    label: 'Keyword Gap', icon: Search,
    border: 'border-l-emerald-500', badge: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
    glow: 'from-emerald-50 to-transparent dark:from-emerald-950/20', iconBg: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400',
  },
};

function ScoreRing({ score }: { score: number }) {
  const r = 22, circ = 2 * Math.PI * r, fill = (score / 100) * circ;
  const color = score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
  const textColor = score >= 70 ? 'text-emerald-600 dark:text-emerald-400' : score >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400';
  return (
    <div className="relative flex h-14 w-14 flex-shrink-0 items-center justify-center">
      <svg width="56" height="56" className="-rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" stroke="currentColor" strokeWidth="3.5" className="text-gray-100 dark:text-gray-800" />
        <circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="3.5" strokeDasharray={circ} strokeDashoffset={circ - fill} strokeLinecap="round" />
      </svg>
      <span className={`absolute text-sm font-bold ${textColor}`}>{Math.round(score)}</span>
    </div>
  );
}

function IdeaCard({ idea }: { idea: AppIdea }) {
  const cfg = IDEA_PATTERNS[idea.pattern_type] ?? {
    label: idea.pattern_type, icon: Lightbulb,
    border: 'border-l-gray-400', badge: 'bg-gray-100 text-gray-600',
    glow: 'from-gray-50 to-transparent', iconBg: 'bg-gray-100 text-gray-600',
  };
  const PatternIcon = cfg.icon;
  return (
    <div className={`relative flex flex-col rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm hover:shadow-md transition-all border-l-4 ${cfg.border} overflow-hidden`}>
      <div className={`absolute inset-x-0 top-0 h-20 bg-gradient-to-b ${cfg.glow} pointer-events-none`} />
      <div className="relative flex flex-col gap-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${cfg.badge}`}>
            <PatternIcon className="h-3 w-3" />
            {cfg.label}
          </span>
          <ScoreRing score={idea.opportunity_score} />
        </div>
        <h3 className="pr-2 text-[15px] font-semibold leading-snug text-gray-900 dark:text-white">{idea.idea_title}</h3>
        {idea.idea_description && (
          <p className="line-clamp-2 text-xs leading-relaxed text-gray-500 dark:text-gray-400">{idea.idea_description}</p>
        )}
        <div className="border-t border-gray-100 dark:border-gray-800" />
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
        <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
          {idea.category && (
            <span className="inline-flex items-center gap-1 rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-400">
              <Package className="h-3 w-3 opacity-60" /> {idea.category}
            </span>
          )}
          {idea.primary_keyword && (
            <span className="inline-flex items-center gap-1 rounded-md bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-400">
              <Key className="h-3 w-3 opacity-60" /> {idea.primary_keyword}
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

const IDEA_FILTER_OPTIONS = [
  { label: 'All', value: '', icon: Sparkles },
  { label: 'Feature Gap', value: 'feature_gap', icon: Zap },
  { label: 'Weak Market', value: 'weak_market', icon: Globe },
  { label: 'Keyword Gap', value: 'keyword_gap', icon: Search },
];

const IDEA_SORT_OPTIONS = [
  { label: 'Score', value: 'opportunity_score', icon: TrendingUp },
  { label: 'Category', value: 'category', icon: Package },
  { label: 'Keyword', value: 'primary_keyword', icon: Key },
];

function IdeasTab() {
  const [data, setData]           = useState<AppIdeaListResponse | null>(null);
  const [loading, setLoading]     = useState(true);
  const [generating, setGen]      = useState(false);
  const [sortBy, setSortBy]       = useState('opportunity_score');
  const [filter, setFilter]       = useState('');
  const [error, setError]         = useState<string | null>(null);

  const fetchIdeas = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const result = await getIdeas({ sort_by: sortBy, sort_order: 'desc', pattern_type: filter || undefined, limit: 60 });
      setData(result);
    } catch { setError('Failed to load ideas.'); }
    finally { setLoading(false); }
  }, [sortBy, filter]);

  useEffect(() => { fetchIdeas(); }, [fetchIdeas]);

  const handleGenerate = async () => {
    setGen(true); setError(null);
    try { const result = await generateIdeas(); setData(result); }
    catch { setError('Generation failed. Check backend logs.'); }
    finally { setGen(false); }
  };

  const ideas = data?.ideas ?? [];
  const counts = {
    feature_gap: ideas.filter(i => i.pattern_type === 'feature_gap').length,
    weak_market: ideas.filter(i => i.pattern_type === 'weak_market').length,
    keyword_gap: ideas.filter(i => i.pattern_type === 'keyword_gap').length,
  };

  return (
    <div className="space-y-6">
      {/* Hero header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-violet-600 to-purple-700 p-6 shadow-lg">
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
              <Lightbulb className="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">App Ideas</h2>
              <p className="mt-0.5 text-sm text-indigo-200">
                Surfaced from feature gaps, weak markets & keyword signals
              </p>
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-xl border border-white/30 bg-white/20 px-5 py-2.5 text-sm font-semibold text-white backdrop-blur-sm transition-all hover:bg-white/30 disabled:opacity-60"
          >
            <RefreshCw className={cn('h-4 w-4', generating && 'animate-spin')} />
            {generating ? 'Analyzing…' : 'Generate Ideas'}
          </button>
        </div>
        {data && (
          <div className="relative mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: 'Total Ideas', value: data.total, color: 'text-white' },
              { label: 'Feature Gaps', value: counts.feature_gap, color: 'text-indigo-200' },
              { label: 'Weak Markets', value: counts.weak_market, color: 'text-rose-300' },
              { label: 'Keyword Gaps', value: counts.keyword_gap, color: 'text-emerald-300' },
            ].map(s => (
              <div key={s.label} className="rounded-xl border border-white/10 bg-white/10 px-4 py-3 backdrop-blur-sm">
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="mt-0.5 text-xs text-indigo-200">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800/60">
          {IDEA_FILTER_OPTIONS.map(opt => {
            const Icon = opt.icon;
            const active = filter === opt.value;
            return (
              <button key={opt.value} onClick={() => setFilter(opt.value)}
                className={cn('inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all',
                  active ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-900 dark:text-white'
                         : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                )}>
                <Icon className="h-3.5 w-3.5" />{opt.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2 sm:ml-auto">
          <span className="text-xs text-gray-500 dark:text-gray-400">Sort by</span>
          <div className="flex items-center gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800/60">
            {IDEA_SORT_OPTIONS.map(opt => {
              const Icon = opt.icon;
              const active = sortBy === opt.value;
              return (
                <button key={opt.value} onClick={() => setSortBy(opt.value)}
                  className={cn('inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all',
                    active ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-900 dark:text-white'
                           : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                  )}>
                  <Icon className="h-3.5 w-3.5" />{opt.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {data?.last_generated && (
        <p className="-mt-2 text-xs text-gray-400 dark:text-gray-600">
          Last generated: {new Date(data.last_generated).toLocaleString()}
        </p>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-52 animate-pulse rounded-xl border border-l-4 border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900" />
          ))}
        </div>
      ) : ideas.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 py-16 text-center dark:border-gray-800">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 dark:bg-gray-800">
            <Lightbulb className="h-8 w-8 text-gray-400 dark:text-gray-600" />
          </div>
          <p className="font-semibold text-gray-700 dark:text-gray-300">No ideas yet</p>
          <p className="mt-1 max-w-xs text-sm text-gray-400 dark:text-gray-600">
            Click <strong>Generate Ideas</strong> to analyse signals from your tracked apps
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {ideas.map(idea => <IdeaCard key={idea.id} idea={idea} />)}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ── TAB 3: Niche Radar ────────────────────────────────────────────────────
// ---------------------------------------------------------------------------

const SIGNAL_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  keyword_growth:   { label: 'Keyword Growth',   color: 'text-emerald-700 dark:text-emerald-400', bg: 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-800' },
  ranking_momentum: { label: 'Ranking Momentum', color: 'text-blue-700 dark:text-blue-400',      bg: 'bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800' },
  feature_gap:      { label: 'Feature Gap',       color: 'text-indigo-700 dark:text-indigo-400',  bg: 'bg-indigo-50 border-indigo-200 dark:bg-indigo-950/30 dark:border-indigo-800' },
};

function NicheScoreCircle({ score }: { score: number }) {
  const color  = score >= 70 ? 'text-emerald-600 dark:text-emerald-400' : score >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-red-500 dark:text-red-400';
  const ring   = score >= 70 ? 'border-emerald-500' : score >= 50 ? 'border-amber-500' : 'border-red-400';
  return (
    <div className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full border-2 ${ring}`}>
      <span className={`text-sm font-bold ${color}`}>{score}</span>
    </div>
  );
}

function NicheCard({ niche }: { niche: NicheRadarItem }) {
  const cfg = SIGNAL_CONFIG[niche.signal_type] ?? { label: niche.signal_type, color: 'text-gray-700', bg: 'bg-gray-50 border-gray-200' };
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-start justify-between gap-3">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${cfg.bg} ${cfg.color}`}>
          {cfg.label}
        </span>
        <NicheScoreCircle score={niche.niche_score} />
      </div>
      <h3 className="text-base font-semibold leading-snug text-gray-900 dark:text-white">{niche.niche_name}</h3>
      <p className="text-sm leading-relaxed text-gray-600 dark:text-gray-400">{niche.description}</p>
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {(niche.keywords ?? []).slice(0, 3).map(kw => (
          <span key={kw} className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">{kw}</span>
        ))}
        {niche.app_count > 0 && (
          <span className="ml-auto text-xs text-gray-400">{niche.app_count} app{niche.app_count !== 1 ? 's' : ''}</span>
        )}
      </div>
    </div>
  );
}

const NICHE_FILTERS: Record<string, string> = {
  all: 'All Signals', keyword_growth: 'Keyword Growth', ranking_momentum: 'Ranking Momentum', feature_gap: 'Feature Gaps',
};

function NichesTab() {
  const [niches, setNiches]       = useState<NicheRadarItem[]>([]);
  const [loading, setLoading]     = useState(true);
  const [failed, setFailed]       = useState(false);
  const [scannedAt, setScanned]   = useState<string | null>(null);
  const [filter, setFilter]       = useState('all');

  const load = async () => {
    setLoading(true); setFailed(false);
    try {
      const data = await getNicheRadar(30);
      const items: NicheRadarItem[] = (Array.isArray(data?.niches) ? data.niches : []).map((n: NicheRadarItem) => ({
        niche_name: n.niche_name ?? 'Unknown', niche_score: Number(n.niche_score) || 0,
        signal_type: n.signal_type ?? 'keyword_growth', description: n.description ?? '',
        keywords: Array.isArray(n.keywords) ? n.keywords : [],
        app_count: Number(n.app_count) || 0, trend: Number(n.trend) || 0,
        search_volume: Number(n.search_volume) || 0, difficulty: Number(n.difficulty) || 0,
        detected_at: n.detected_at ?? '',
      }));
      setNiches(items);
      setScanned(data?.scanned_at ?? null);
    } catch { setNiches([]); setFailed(true); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const filtered = filter === 'all' ? niches : niches.filter(n => n.signal_type === filter);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-600">
            <Radar className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Niche Radar</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Emerging micro-niches from keyword, ranking, and review signals
            </p>
          </div>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 self-start rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300">
          <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      {!loading && niches.length > 0 && (
        <div className="flex flex-wrap gap-3">
          <div className="card px-4 py-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Total Niches</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">{niches.length}</p>
          </div>
          <div className="card px-4 py-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">High Score (≥70)</p>
            <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
              {niches.filter(n => n.niche_score >= 70).length}
            </p>
          </div>
          {scannedAt && (
            <div className="card px-4 py-3">
              <p className="text-xs text-gray-500 dark:text-gray-400">Last Scanned</p>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {new Date(scannedAt).toLocaleTimeString()}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Filter pills */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(NICHE_FILTERS).map(([key, label]) => (
          <button key={key} onClick={() => setFilter(key)}
            className={cn('rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
              filter === key
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400'
            )}>
            {label}
            {key !== 'all' && (
              <span className="ml-1.5 text-xs opacity-70">
                {niches.filter(n => n.signal_type === key).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center dark:border-gray-700">
          <Radar className="mx-auto mb-3 h-10 w-10 text-gray-400 dark:text-gray-600" />
          <p className="text-gray-500 dark:text-gray-400">
            {failed
              ? 'Niche data not available yet — bootstrap the app and run scoring to generate signals.'
              : niches.length === 0
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
  );
}

// ---------------------------------------------------------------------------
// ── Main component ────────────────────────────────────────────────────────
// ---------------------------------------------------------------------------

function OpportunitiesInner() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const pathname     = usePathname();

  const tabFromUrl = (searchParams.get('tab') as TabId | null) ?? 'keywords';
  const activeTab  = TABS.some(t => t.id === tabFromUrl) ? tabFromUrl : 'keywords';

  const setTab = (id: TabId) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', id);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900 dark:text-white">
            <Target className="h-6 w-6 text-indigo-500" />
            Opportunities
          </h1>
          <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
            Keyword gaps, feature-gap app ideas, and emerging niche signals — all in one place
          </p>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 rounded-xl border border-gray-200 bg-gray-50 p-1 w-fit dark:border-gray-700 dark:bg-gray-800/50">
          {TABS.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setTab(tab.id)}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-all',
                  activeTab === tab.id
                    ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {activeTab === 'keywords' && <KeywordsTab />}
        {activeTab === 'ideas'    && <IdeasTab />}
        {activeTab === 'niches'   && <NichesTab />}
      </div>
    </AppShell>
  );
}

export default function OpportunitiesClient() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<AppShell><div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" /></AppShell>}>
        <OpportunitiesInner />
      </Suspense>
    </ErrorBoundary>
  );
}
