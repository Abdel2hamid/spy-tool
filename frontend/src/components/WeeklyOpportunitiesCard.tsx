'use client';

import Link from 'next/link';
import { Trophy, TrendingUp, Star, Users, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { WeeklyOpportunityItem, RelatedApp } from '@/lib/api';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RelatedAppRow({ app }: { app: RelatedApp }) {
  return (
    <Link
      href={`/apps/${app.id}`}
      className="flex items-center gap-2 rounded-md bg-white/10 hover:bg-white/20 px-2 py-1.5 transition-colors"
    >
      {app.icon_url ? (
        <img src={app.icon_url} alt={app.name} className="h-6 w-6 rounded flex-shrink-0 object-cover" />
      ) : (
        <div className="h-6 w-6 rounded bg-white/20 flex-shrink-0" />
      )}
      <span className="text-xs text-white/90 truncate flex-1 min-w-0">{app.name}</span>
      <div className="flex items-center gap-2 flex-shrink-0 text-xs text-white/60">
        {app.rating != null && (
          <span className="flex items-center gap-0.5">
            <Star className="h-2.5 w-2.5" />
            {app.rating.toFixed(1)}
          </span>
        )}
        {app.rank != null && <span>#{app.rank}</span>}
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Rank badge with medal colours
// ---------------------------------------------------------------------------

const RANK_COLORS: Record<number, string> = {
  1: 'bg-yellow-400 text-yellow-900',
  2: 'bg-gray-300 text-gray-700',
  3: 'bg-amber-600 text-amber-100',
};

function RankBadge({ rank }: { rank: number }) {
  const cls = RANK_COLORS[rank] ?? 'bg-indigo-500 text-white';
  return (
    <div className={cn('flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold flex-shrink-0', cls)}>
      {rank}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score bar (inline horizontal)
// ---------------------------------------------------------------------------

function ScoreBar({ label, value, max = 100, colorClass = 'bg-white/60' }: {
  label: string; value: number; max?: number; colorClass?: string;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 text-xs text-white/60 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-white/20">
        <div className={cn('h-1.5 rounded-full', colorClass)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-xs font-semibold text-white">{Math.round(value)}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual opportunity card (collapsible)
// ---------------------------------------------------------------------------

function OpportunityRow({ item }: { item: WeeklyOpportunityItem }) {
  const [expanded, setExpanded] = useState(item.rank === 1);
  const hasRelated = item.related_apps && item.related_apps.length > 0;

  const scoreColor =
    item.opportunity_score >= 65 ? 'text-emerald-300' :
    item.opportunity_score >= 45 ? 'text-amber-300' :
    'text-red-300';

  return (
    <div className="rounded-xl bg-white/10 backdrop-blur-sm overflow-hidden">
      {/* Header row — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/5 transition-colors"
      >
        <RankBadge rank={item.rank} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-white truncate">{item.app_name}</span>
            <span className="inline-flex items-center rounded-md bg-white/10 px-1.5 py-0.5 text-xs text-white/80">
              {item.category}
            </span>
          </div>
          <div className="text-xs text-indigo-200 mt-0.5 truncate">
            {item.primary_keyword}
          </div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="text-right">
            <div className={cn('text-lg font-bold', scoreColor)}>
              {item.opportunity_score.toFixed(0)}
            </div>
            <div className="text-xs text-indigo-300">score</div>
          </div>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-white/40" />
          ) : (
            <ChevronDown className="h-4 w-4 text-white/40" />
          )}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-white/10 pt-3">
          {/* Score bars */}
          <div className="space-y-1.5">
            <ScoreBar label="Trend" value={item.trend_score} colorClass="bg-indigo-400" />
            <ScoreBar
              label="Low comp."
              value={100 - item.competition_score}
              colorClass="bg-emerald-400"
            />
            <ScoreBar label="Success" value={item.success_probability} colorClass="bg-amber-400" />
            {item.ai_integration_potential != null && (
              <ScoreBar label="AI potential" value={item.ai_integration_potential} colorClass="bg-purple-400" />
            )}
          </div>

          {/* AI summary */}
          {item.ai_summary && (
            <div className="rounded-lg bg-white/10 p-3">
              <p className="text-xs font-semibold text-indigo-200 uppercase tracking-wide mb-1">Analysis</p>
              <p className="text-xs text-white/85 leading-relaxed">{item.ai_summary}</p>
            </div>
          )}

          {/* Related apps */}
          {hasRelated && (
            <div>
              <p className="text-xs font-semibold text-indigo-200 uppercase tracking-wide mb-2">
                Competitors in this niche
              </p>
              <div className="space-y-1">
                {item.related_apps!.slice(0, 5).map((app) => (
                  <RelatedAppRow key={app.id} app={app} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface WeeklyOpportunitiesCardProps {
  items: WeeklyOpportunityItem[];
  weekStartDate?: string | null;
}

export function WeeklyOpportunitiesCard({ items, weekStartDate }: WeeklyOpportunitiesCardProps) {
  const formattedWeek = weekStartDate
    ? `Week of ${new Date(weekStartDate + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
    : 'This Week';

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-violet-700 via-indigo-700 to-blue-800 p-6 text-white shadow-lg">
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-40" />

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/20 backdrop-blur-sm">
              <Trophy className="h-4 w-4 text-yellow-300" />
            </div>
            <div>
              <span className="text-sm font-semibold text-white">Top 5 Opportunities</span>
              <span className="ml-2 text-xs text-indigo-200">{formattedWeek}</span>
            </div>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-medium text-white">
            <TrendingUp className="h-3 w-3" />
            Weekly Picks
          </span>
        </div>

        {/* Opportunity list */}
        <div className="space-y-2">
          {items.map((item) => (
            <OpportunityRow key={item.rank} item={item} />
          ))}
        </div>

        {/* Footer */}
        <p className="mt-4 text-xs text-indigo-300 text-center">
          Ranked by: trend × 0.5 + low competition × 0.3 + success probability × 0.2
        </p>
      </div>
    </div>
  );
}
