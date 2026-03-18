'use client';

import Link from 'next/link';
import { Zap, Star, Users } from 'lucide-react';
import { OpportunityOfDay, RelatedApp } from '@/lib/api';
import { cn } from '@/lib/utils';

interface OpportunityOfDayCardProps {
  opportunity: OpportunityOfDay;
}

function RelatedAppRow({ app }: { app: RelatedApp }) {
  return (
    <Link
      href={`/apps/${app.id}`}
      className="flex items-center gap-3 rounded-lg bg-white/10 hover:bg-white/20 px-3 py-2 transition-colors group/row"
    >
      {app.icon_url ? (
        <img
          src={app.icon_url}
          alt={app.name}
          className="h-8 w-8 rounded-lg object-cover flex-shrink-0"
        />
      ) : (
        <div className="h-8 w-8 rounded-lg bg-white/20 flex-shrink-0" />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-white truncate group-hover/row:text-indigo-100">
          {app.name}
        </p>
        <div className="flex items-center gap-3 text-xs text-indigo-300">
          {app.rating != null && (
            <span className="flex items-center gap-0.5">
              <Star className="h-3 w-3" />
              {app.rating.toFixed(1)}
            </span>
          )}
          {app.reviews != null && (
            <span className="flex items-center gap-0.5">
              <Users className="h-3 w-3" />
              {app.reviews.toLocaleString()}
            </span>
          )}
          {app.rank != null && (
            <span className="text-indigo-200">#{app.rank}</span>
          )}
        </div>
      </div>
    </Link>
  );
}

export function OpportunityOfDayCard({ opportunity }: OpportunityOfDayCardProps) {
  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-emerald-400';
    if (score >= 50) return 'text-amber-400';
    return 'text-red-400';
  };

  const hasRelatedApps = opportunity?.related_apps && opportunity.related_apps.length > 0;

  return (
    <div className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-purple-600 to-indigo-800 p-6 text-white shadow-lg transition-all duration-300 hover:shadow-xl">
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/20 backdrop-blur-sm">
              <Zap className="h-4 w-4 text-yellow-300" />
            </div>
            <span className="text-sm font-medium text-indigo-100">Opportunity of the Day</span>
          </div>
          <span className="inline-flex items-center rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-medium text-white">
            AI Powered
          </span>
        </div>

        {/* Title */}
        <h2 className="text-2xl font-bold mb-1">{opportunity?.app_name || 'N/A'}</h2>
        <p className="text-indigo-200 mb-6">
          Primary keyword:{' '}
          <span className="font-semibold text-white">{opportunity?.primary_keyword || 'N/A'}</span>
          <span className="ml-2 inline-flex items-center rounded-md bg-white/10 px-2 py-0.5 text-xs">
            {opportunity?.category || 'general'}
          </span>
        </p>

        {/* Score grid */}
        <div className="grid grid-cols-2 gap-3 mb-6 sm:grid-cols-4">
          <div className="rounded-xl bg-white/10 backdrop-blur-sm p-3">
            <p className="text-xs text-indigo-200 mb-1">Competition</p>
            <p className={cn('text-xl font-bold', getScoreColor(100 - (opportunity?.competition_score || 0)))}>
              {(opportunity?.competition_score || 0).toFixed(0)}%
            </p>
          </div>
          <div className="rounded-xl bg-white/10 backdrop-blur-sm p-3">
            <p className="text-xs text-indigo-200 mb-1">Trend Score</p>
            <p className={cn('text-xl font-bold', getScoreColor(opportunity?.trend_score || 0))}>
              {(opportunity?.trend_score || 0).toFixed(0)}%
            </p>
          </div>
          <div className="rounded-xl bg-white/10 backdrop-blur-sm p-3">
            <p className="text-xs text-indigo-200 mb-1">Success Prob.</p>
            <p className={cn('text-xl font-bold', getScoreColor(opportunity?.success_probability || 0))}>
              {(opportunity?.success_probability || 0).toFixed(0)}%
            </p>
          </div>
          <div className="rounded-xl bg-white/10 backdrop-blur-sm p-3">
            <p className="text-xs text-indigo-200 mb-1">AI Potential</p>
            <p className={cn('text-xl font-bold', getScoreColor(opportunity?.ai_integration_potential || 0))}>
              {(opportunity?.ai_integration_potential || 0).toFixed(0)}%
            </p>
          </div>
        </div>

        {/* AI Summary */}
        {opportunity?.ai_summary && (
          <div className="rounded-xl bg-white/10 backdrop-blur-sm p-4 mb-4">
            <p className="text-xs font-semibold text-indigo-200 uppercase tracking-wide mb-1">Analysis</p>
            <p className="text-sm text-white/90 leading-relaxed">{opportunity.ai_summary}</p>
          </div>
        )}

        {/* Recommendation (shown only if no ai_summary) */}
        {!opportunity?.ai_summary && (
          <div className="rounded-xl bg-white/10 backdrop-blur-sm p-4 mb-4">
            <p className="text-sm text-indigo-100">
              {opportunity?.recommendation || 'No recommendation available'}
            </p>
          </div>
        )}

        {/* Related Apps */}
        {hasRelatedApps && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-indigo-200 uppercase tracking-wide mb-2">
              Competing Apps in this Niche
            </p>
            <div className="space-y-1.5">
              {opportunity.related_apps!.slice(0, 6).map((app) => (
                <RelatedAppRow key={app.id} app={app} />
              ))}
            </div>
          </div>
        )}

        {/* Footer stats */}
        <div className="mt-4 flex items-center justify-between text-xs text-indigo-300">
          <span>Rank velocity: {(opportunity?.rank_velocity || 0).toFixed(2)}</span>
          <span>Review growth: {(opportunity?.review_growth || 0).toFixed(2)}%</span>
          <span>Rating velocity: {(opportunity?.rating_velocity || 0).toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}
