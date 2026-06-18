'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import {
  getASOScore,
  getKeywordOpportunitiesForApp,
  getReviewIntelligence,
  getFeatureGaps,
  getMyApps,
  removeMyApp,
  refreshMyApp,
  triggerKeywordExtraction,
  triggerPhase1Discovery,
  ASOScoreResponse,
  KeywordOpportunityItem,
  ReviewIntelligence,
  FeatureGapItem,
  MyAppItem,
} from '@/lib/api';
import {
  Star,
  TrendingUp,
  MessageSquare,
  Search,
  Target,
  ThumbsDown,
  ThumbsUp,
  AlertTriangle,
  Lightbulb,
  ArrowLeft,
  ExternalLink,
  Trash2,
  Crown,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/* ── Helpers ───────────────────────────────────────────────── */

function ASOScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(score, 100));
  const offset = circ - (pct / 100) * circ;
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#3b82f6' : score >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <svg width={size} height={size} className="flex-shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" className="text-gray-200 dark:text-gray-700" strokeWidth={5} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={5} strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" textAnchor="middle" dy=".35em" className="fill-gray-900 dark:fill-white text-sm font-bold">{score}</text>
    </svg>
  );
}

function BreakdownBar({ label, score }: { label: string; score: number }) {
  const color = score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-blue-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-gray-600 dark:text-gray-400">{label}</span>
        <span className="font-medium text-gray-900 dark:text-white">{score}/100</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function SectionCard({ title, icon: Icon, status, children }: {
  title: string;
  icon: typeof Star;
  status?: 'loading' | 'ready';
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div className="border-b border-gray-100 px-5 py-3 dark:border-gray-800">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <Icon className="h-4 w-4 text-indigo-500" />
          {title}
          {status === 'loading' && (
            <span className="ml-auto flex items-center gap-1.5 text-xs font-normal text-indigo-500">
              <Loader2 className="h-3 w-3 animate-spin" /> Analyzing...
            </span>
          )}
        </h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
    </div>
  );
}

const gradeColor: Record<string, string> = {
  A: 'from-emerald-500 to-emerald-600',
  B: 'from-blue-500 to-blue-600',
  C: 'from-yellow-500 to-yellow-600',
  D: 'from-orange-500 to-orange-600',
  F: 'from-red-500 to-red-600',
};
const gradeText: Record<string, string> = { A: 'Excellent', B: 'Good', C: 'Needs work', D: 'Poor', F: 'Critical' };

/* ── Main Component ────────────────────────────────────────── */

export default function MyAppDetailClient({ appId }: { appId: number }) {
  const [app, setApp] = useState<MyAppItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [removing, setRemoving] = useState(false);

  // Section data + loading states
  const [aso, setAso] = useState<ASOScoreResponse | null>(null);
  const [asoLoading, setAsoLoading] = useState(true);
  const [keywords, setKeywords] = useState<KeywordOpportunityItem[]>([]);
  const [kwLoading, setKwLoading] = useState(true);
  const [kwDiscovering, setKwDiscovering] = useState(false);
  const [reviews, setReviews] = useState<ReviewIntelligence | null>(null);
  const [revLoading, setRevLoading] = useState(true);
  const [featureGaps, setFeatureGaps] = useState<FeatureGapItem[]>([]);

  // Load app info + trigger background refresh
  useEffect(() => {
    let cancelled = false;
    async function loadApp() {
      const myApps = await getMyApps().catch(() => ({ apps: [], total: 0 }));
      const found = myApps.apps.find((a) => a.app_id === appId) || null;
      if (cancelled) return;
      if (!found) {
        setNotFound(true);
        setLoading(false);
        return;
      }
      setApp(found);
      setLoading(false);

      // Trigger full metadata refresh (scrape subtitle, screenshots, etc.)
      // This runs in background on the server
      refreshMyApp(appId).catch(() => {});
    }
    loadApp();
    return () => { cancelled = true; };
  }, [appId]);

  // Load ASO score — first immediately, then again after scrape likely completes
  useEffect(() => {
    if (!app) return;
    let cancelled = false;

    async function loadAso() {
      // First load: immediate (may have stale data)
      try {
        const data = await getASOScore(appId);
        if (!cancelled) setAso(data);
      } catch { /* ignore */ }
      if (!cancelled) setAsoLoading(false);

      // Second load: after background scrape has had time to finish
      // This refreshes the score with updated subtitle/screenshots/description
      await new Promise((r) => setTimeout(r, 8000));
      if (cancelled) return;
      try {
        const fresh = await getASOScore(appId);
        if (!cancelled) setAso(fresh);
      } catch { /* ignore */ }
    }

    loadAso();
    return () => { cancelled = true; };
  }, [app, appId]);

  // Load keywords — auto-trigger discovery if empty
  useEffect(() => {
    if (!app) return;
    let cancelled = false;

    async function loadKeywords() {
      try {
        const data = await getKeywordOpportunitiesForApp(appId, 20);
        if (cancelled) return;

        if (data.opportunities && data.opportunities.length > 0) {
          setKeywords(data.opportunities);
          setKwLoading(false);
          return;
        }

        // No keywords yet — auto-trigger discovery pipeline
        if (!data.discovering) {
          setKwDiscovering(true);
          // Extract keywords first, then run phase-1 discovery
          await triggerKeywordExtraction(appId).catch(() => {});
          // Wait briefly for extraction to finish
          await new Promise((r) => setTimeout(r, 3000));
          await triggerPhase1Discovery(appId).catch(() => {});
        } else {
          setKwDiscovering(true);
        }

        // Poll for results
        const pollUntil = Date.now() + 90_000; // 90s max
        while (!cancelled && Date.now() < pollUntil) {
          await new Promise((r) => setTimeout(r, 5000));
          const poll = await getKeywordOpportunitiesForApp(appId, 20).catch(() => null);
          if (cancelled) return;
          if (poll && poll.opportunities && poll.opportunities.length > 0) {
            setKeywords(poll.opportunities);
            break;
          }
          if (poll && !poll.discovering) break; // finished but no results
        }
      } catch { /* ignore */ }
      if (!cancelled) { setKwLoading(false); setKwDiscovering(false); }
    }

    loadKeywords();
    return () => { cancelled = true; };
  }, [app, appId]);

  // Load review intelligence — auto-trigger if empty
  useEffect(() => {
    if (!app) return;
    let cancelled = false;

    async function loadReviews() {
      try {
        // Try cached first
        let data = await getReviewIntelligence(appId, false);
        if (cancelled) return;

        if (data && data.reviews_analyzed > 0) {
          setReviews(data);
          setRevLoading(false);
          return;
        }

        // No cached data — force analysis
        data = await getReviewIntelligence(appId, true);
        if (!cancelled) setReviews(data);
      } catch { /* ignore */ }
      if (!cancelled) setRevLoading(false);
    }

    loadReviews();
    return () => { cancelled = true; };
  }, [app, appId]);

  // Load feature gaps
  useEffect(() => {
    if (!app) return;
    let cancelled = false;
    getFeatureGaps(appId)
      .then((data) => { if (!cancelled) setFeatureGaps(data.feature_gaps || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [app, appId]);

  // Refresh ASO after keywords load (score depends on keyword coverage)
  const refreshAso = useCallback(async () => {
    setAsoLoading(true);
    try {
      const data = await getASOScore(appId);
      setAso(data);
    } catch { /* ignore */ }
    setAsoLoading(false);
  }, [appId]);

  async function handleRemove() {
    setRemoving(true);
    try {
      await removeMyApp(appId);
      window.location.href = '/my-apps';
    } catch {
      setRemoving(false);
    }
  }

  if (loading) return <AppShell><Spinner /></AppShell>;

  if (notFound || !app) {
    return (
      <AppShell>
        <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
          <Crown className="h-10 w-10 text-gray-300 dark:text-gray-600" />
          <p className="text-lg font-semibold text-gray-900 dark:text-white">App not found in My Apps</p>
          <Link href="/my-apps" className="text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400">
            <ArrowLeft className="mr-1 inline h-4 w-4" />Back to My Apps
          </Link>
        </div>
      </AppShell>
    );
  }

  const grade = aso?.grade || app.aso_grade || 'F';
  const score = Math.round(aso?.overall_score ?? app.aso_score ?? 0);

  // Filter keywords
  const kwGaps = keywords.filter((k) => k.keyword_gap || (k.opportunity_score >= 40 && !k.app_rank));
  const kwBest = kwGaps.length > 0 ? kwGaps : keywords;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Breadcrumb + Header */}
        <div>
          <Link href="/my-apps" className="mb-3 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-indigo-600 dark:text-gray-400 dark:hover:text-indigo-400">
            <ArrowLeft className="h-3.5 w-3.5" /> My Apps
          </Link>

          <div className="flex items-start gap-4">
            {app.icon_url ? (
              <img src={app.icon_url} alt="" className="h-16 w-16 rounded-2xl object-cover shadow-sm ring-1 ring-black/5 dark:ring-white/10" />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
                <span className="text-2xl font-bold text-white">{(app.name || '?')[0]}</span>
              </div>
            )}

            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">{app.name}</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {app.developer}
                {app.primary_category && ` · ${app.primary_category}`}
              </p>
              <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-gray-400">
                {app.current_rating != null && (
                  <span className="flex items-center gap-0.5">
                    <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" /> {app.current_rating.toFixed(1)}
                  </span>
                )}
                {app.current_reviews != null && app.current_reviews > 0 && (
                  <span className="flex items-center gap-0.5">
                    <MessageSquare className="h-3 w-3" /> {app.current_reviews.toLocaleString()} reviews
                  </span>
                )}
                {app.current_rank != null && (
                  <span className="flex items-center gap-0.5">
                    <TrendingUp className="h-3 w-3" /> #{app.current_rank}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link
                href={`/apps/${app.app_id}`}
                className="rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                <ExternalLink className="mr-1 inline h-3.5 w-3.5" /> Full Page
              </Link>
              <button
                onClick={handleRemove}
                disabled={removing}
                className="rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-red-600 transition hover:bg-red-50 dark:border-gray-700 dark:text-red-400 dark:hover:bg-red-950/30"
              >
                <Trash2 className="mr-1 inline h-3.5 w-3.5" /> {removing ? 'Removing...' : 'Remove'}
              </button>
            </div>
          </div>
        </div>

        {/* ═══ ASO Health ═══ */}
        <SectionCard title="ASO Health" icon={Target} status={asoLoading ? 'loading' : 'ready'}>
          {asoLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
              <span className="ml-2 text-sm text-gray-500">Computing ASO score...</span>
            </div>
          ) : aso ? (
            <div className="space-y-4">
              <div className={cn('flex items-center gap-4 rounded-lg bg-gradient-to-r p-4 text-white', gradeColor[grade] || gradeColor.F)}>
                <ASOScoreRing score={score} size={64} />
                <div>
                  <p className="text-lg font-bold">ASO Score: {score}/100</p>
                  <p className="text-sm opacity-80">Grade {grade} — {gradeText[grade] || 'Unknown'}</p>
                </div>
                <button
                  onClick={refreshAso}
                  className="ml-auto rounded-lg bg-white/20 p-2 text-white/80 transition hover:bg-white/30 hover:text-white"
                  title="Refresh ASO score"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>

              {aso.breakdown && Object.keys(aso.breakdown).length > 0 && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(aso.breakdown).map(([key, item]) => (
                    <BreakdownBar key={key} label={item.label || key} score={Math.round(item.score)} />
                  ))}
                </div>
              )}

              {aso.tips && aso.tips.length > 0 && (
                <div>
                  <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300">
                    <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
                    Optimization Tips
                  </p>
                  <div className="space-y-1.5">
                    {aso.tips.map((tip, i) => (
                      <div key={i} className="flex items-start gap-2 rounded-lg bg-gray-50 px-4 py-2.5 text-sm dark:bg-gray-800/50">
                        <span className={cn(
                          'mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase',
                          tip.impact === 'high' ? 'bg-red-100 text-red-600 dark:bg-red-950/40 dark:text-red-400'
                            : tip.impact === 'medium' ? 'bg-amber-100 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400'
                            : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
                        )}>
                          {tip.impact}
                        </span>
                        <span className="text-gray-700 dark:text-gray-300">{tip.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">ASO data not available yet. Check back after the next analysis run.</p>
          )}
        </SectionCard>

        {/* ═══ Keyword Opportunities ═══ */}
        <SectionCard title="Keyword Opportunities" icon={Search} status={kwLoading ? 'loading' : 'ready'}>
          {kwLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
              <span className="ml-2 text-sm text-gray-500">
                {kwDiscovering ? 'Discovering keywords... this may take a minute' : 'Loading keywords...'}
              </span>
            </div>
          ) : kwBest.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-gray-800">
                    <th className="pb-2 pr-4 text-left font-semibold text-gray-500 text-xs">Keyword</th>
                    <th className="pb-2 px-2 text-right font-semibold text-gray-500 text-xs">Volume</th>
                    <th className="pb-2 px-2 text-right font-semibold text-gray-500 text-xs">Difficulty</th>
                    <th className="pb-2 px-2 text-right font-semibold text-gray-500 text-xs">Opportunity</th>
                    <th className="pb-2 px-2 text-right font-semibold text-gray-500 text-xs">Your Rank</th>
                    <th className="pb-2 pl-2 text-right font-semibold text-gray-500 text-xs">Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-gray-800/50">
                  {kwBest.slice(0, 15).map((kw) => {
                    const diff = Math.round(kw.difficulty_v2 || kw.difficulty || 0);
                    const opp = Math.round(kw.opportunity_score);
                    const diffC = diff <= 30 ? 'text-emerald-600 dark:text-emerald-400' : diff <= 60 ? 'text-amber-600 dark:text-amber-400' : 'text-red-500';
                    const oppC = opp >= 60 ? 'text-emerald-600 dark:text-emerald-400' : opp >= 40 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-500';
                    return (
                      <tr key={kw.keyword}>
                        <td className="max-w-[200px] truncate py-2.5 pr-4 font-medium text-gray-900 dark:text-white">{kw.keyword}</td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-gray-500">{Math.round(kw.volume_score || kw.search_volume || 0)}</td>
                        <td className={cn('px-2 py-2.5 text-right tabular-nums', diffC)}>{diff}</td>
                        <td className={cn('px-2 py-2.5 text-right tabular-nums font-semibold', oppC)}>{opp}</td>
                        <td className="px-2 py-2.5 text-right tabular-nums text-gray-500">{kw.app_rank ?? '—'}</td>
                        <td className="py-2.5 pl-2 text-right">
                          {kw.keyword_gap ? (
                            <span className="rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-600 dark:bg-red-950/30 dark:text-red-400">Gap</span>
                          ) : kw.app_rank ? (
                            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400">Ranked</span>
                          ) : (
                            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">New</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {keywords.length > 15 && (
                <p className="mt-3 text-xs text-gray-400">
                  Showing top 15 of {keywords.length} keywords.{' '}
                  <Link href={`/apps/${appId}`} className="text-indigo-500 hover:text-indigo-600">View all in app page</Link>
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No keywords discovered yet. Discovery will run automatically next time.</p>
          )}
        </SectionCard>

        {/* ═══ Review Insights ═══ */}
        <SectionCard title="Review Insights" icon={MessageSquare} status={revLoading ? 'loading' : 'ready'}>
          {revLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
              <span className="ml-2 text-sm text-gray-500">Analyzing reviews with AI...</span>
            </div>
          ) : reviews && reviews.reviews_analyzed > 0 ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-800/50">
                <p className="text-sm text-gray-700 dark:text-gray-300">{reviews.sentiment_summary}</p>
                <p className="mt-2 text-xs text-gray-400">{reviews.reviews_analyzed} reviews analyzed</p>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {reviews.feature_requests.length > 0 && (
                  <div>
                    <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300">
                      <ThumbsUp className="h-3.5 w-3.5 text-blue-500" />
                      Feature Requests ({reviews.feature_requests.length})
                    </p>
                    <ul className="space-y-1.5">
                      {reviews.feature_requests.slice(0, 6).map((f, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                          {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {reviews.pain_points.length > 0 && (
                  <div>
                    <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300">
                      <ThumbsDown className="h-3.5 w-3.5 text-red-500" />
                      Pain Points ({reviews.pain_points.length})
                    </p>
                    <ul className="space-y-1.5">
                      {reviews.pain_points.slice(0, 6).map((p, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
                          {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {reviews.pricing_complaints.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/40 dark:bg-amber-950/20">
                  <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="h-4 w-4" />
                    Pricing Complaints
                  </p>
                  <ul className="space-y-1">
                    {reviews.pricing_complaints.map((c, i) => (
                      <li key={i} className="text-sm text-amber-700 dark:text-amber-300">{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No review data available for this app.</p>
          )}
        </SectionCard>

        {/* ═══ Feature Gap Opportunities ═══ */}
        <SectionCard title="Feature Gap Opportunities" icon={Lightbulb}>
          {featureGaps.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {featureGaps.map((fg) => (
                <div
                  key={fg.feature}
                  className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800"
                >
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{fg.feature}</span>
                  <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-bold text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400">
                    {fg.mentions}x mentioned
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No feature gaps detected. More review data is needed for analysis.</p>
          )}
        </SectionCard>
      </div>
    </AppShell>
  );
}
