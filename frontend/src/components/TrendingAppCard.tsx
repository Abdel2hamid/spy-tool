'use client';

import Link from 'next/link';
import { TrendingUp as TrendUpIcon, Star, TrendingDown, ShieldCheck } from 'lucide-react';
import { TrendingApp } from '@/lib/api';
import { cn } from '@/lib/utils';

interface TrendingAppCardProps {
  app: TrendingApp;
}

export function TrendingAppCard({ app }: TrendingAppCardProps) {
  const isTrendingUp = (app?.momentum_7d || 0) > 0;
  const currentRank = app?.current_rank ?? '-';
  const momentum7d = app?.momentum_7d ?? 0;
  const consistencyScore = app?.consistency_score ?? 0;
  const confidenceFactor = app?.confidence_factor ?? 0;
  const reviewMomentum = app?.review_momentum ?? 0;
  const trendScore = app?.trend_score ?? 0;

  return (
    <Link href={`/apps/${app.id}`}>
      <div className="group rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition-all duration-200 hover:border-indigo-200 hover:shadow-md dark:border-gray-800 dark:bg-gray-900 cursor-pointer">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-gray-100 overflow-hidden dark:bg-gray-800">
            {app?.icon_url ? (
              <img
                src={app.icon_url}
                alt={app.name || 'App'}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="text-xl font-bold text-gray-400">
                {(app?.name || '?')[0]}
              </span>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold text-gray-900 dark:text-white">
              {app?.name || 'Unknown App'}
            </h3>
            <p className="truncate text-xs text-gray-500 dark:text-gray-400">
              {app?.developer || 'Unknown Developer'}
            </p>

            <div className="mt-2 flex items-center gap-3">
              <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-600 dark:text-gray-300">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-gray-100 text-xs font-bold dark:bg-gray-800">
                  #{currentRank}
                </span>
              </span>

              <span
                className={cn(
                  'inline-flex items-center gap-1 text-xs font-medium',
                  isTrendingUp
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-red-600 dark:text-red-400'
                )}
              >
                {isTrendingUp ? (
                  <TrendUpIcon className="h-3 w-3" />
                ) : (
                  <TrendingDown className="h-3 w-3" />
                )}
                {Math.abs(momentum7d).toFixed(1)}
              </span>

              <span className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                <Star className="h-3 w-3 text-yellow-500" />
                {reviewMomentum.toFixed(1)}
              </span>

              {confidenceFactor >= 0.7 && (
                <span className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400" title="High confidence">
                  <ShieldCheck className="h-3 w-3" />
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end">
            <div
              className={cn(
                'text-lg font-bold',
                trendScore > 70
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : trendScore > 40
                  ? 'text-amber-600 dark:text-amber-400'
                  : 'text-gray-400 dark:text-gray-500'
              )}
            >
              {trendScore.toFixed(0)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">score</div>
          </div>
        </div>

        {(app.estimated_installs_min != null || app.estimated_revenue_monthly_min != null) && (
          <div className="mt-3 flex items-center gap-4 border-t border-gray-100 pt-3 dark:border-gray-800">
            {app.estimated_installs_min != null && (
              <div>
                <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                  {app.estimated_installs_min >= 1_000_000
                    ? `${(app.estimated_installs_min / 1_000_000).toFixed(1)}M`
                    : app.estimated_installs_min >= 1_000
                    ? `${(app.estimated_installs_min / 1_000).toFixed(1)}K`
                    : String(app.estimated_installs_min)}
                </span>
                <span className="ml-0.5 text-[10px] text-gray-400"> DL/mo</span>
              </div>
            )}
            {app.estimated_revenue_monthly_min != null && (
              <div>
                <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                  ${app.estimated_revenue_monthly_min >= 1_000_000
                    ? `${(app.estimated_revenue_monthly_min / 1_000_000).toFixed(1)}M`
                    : app.estimated_revenue_monthly_min >= 1_000
                    ? `${(app.estimated_revenue_monthly_min / 1_000).toFixed(1)}K`
                    : String(Math.round(app.estimated_revenue_monthly_min))}
                </span>
                <span className="ml-0.5 text-[10px] text-gray-400"> Rev/mo</span>
              </div>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}
