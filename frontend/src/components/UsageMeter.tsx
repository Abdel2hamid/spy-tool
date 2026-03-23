'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { getUsageSummary, UsageSummary } from '@/lib/api';

interface MeterBarProps {
  label: string;
  used: number;
  limit: number | null;
}

function MeterBar({ label, used, limit }: MeterBarProps) {
  if (limit === null) {
    return (
      <div className="flex items-center justify-between text-[10px] text-gray-500 dark:text-gray-400">
        <span>{label}</span>
        <span className="text-emerald-600 dark:text-emerald-400">Unlimited</span>
      </div>
    );
  }

  const pct = Math.min(100, limit > 0 ? (used / limit) * 100 : 100);
  const isNearLimit = pct >= 80;
  const isAtLimit = used >= limit;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-gray-500 dark:text-gray-400">{label}</span>
        <span
          className={
            isAtLimit
              ? 'text-red-600 dark:text-red-400 font-medium'
              : isNearLimit
              ? 'text-amber-600 dark:text-amber-400 font-medium'
              : 'text-gray-500 dark:text-gray-400'
          }
        >
          {used}/{limit}
        </span>
      </div>
      <div className="h-1 w-full bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            isAtLimit
              ? 'bg-red-500'
              : isNearLimit
              ? 'bg-amber-400'
              : 'bg-indigo-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface UsageMeterProps {
  /** If provided, uses this instead of fetching */
  summary?: UsageSummary;
}

export function UsageMeter({ summary: propSummary }: UsageMeterProps) {
  const { token } = useAuth();
  const [summary, setSummary] = useState<UsageSummary | null>(propSummary ?? null);

  useEffect(() => {
    if (propSummary) {
      setSummary(propSummary);
      return;
    }
    if (!token) return;
    getUsageSummary(token)
      .then(setSummary)
      .catch(() => {});
  }, [token, propSummary]);

  if (!summary || summary.plan === 'unknown') return null;

  const { usage, limits, plan } = summary;
  const isPro = limits.app_imports === null;

  return (
    <div className="px-3 py-2 border-b border-gray-100 dark:border-gray-800">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide">
          Monthly usage
        </span>
        {!isPro && (
          <span className="text-[9px] bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded-full font-medium capitalize">
            {plan}
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        <MeterBar label="App imports" used={usage.app_imports} limit={limits.app_imports} />
        <MeterBar label="Keyword scans" used={usage.keyword_refreshes} limit={limits.keyword_refreshes} />
        <MeterBar label="AI requests" used={usage.ai_requests} limit={limits.ai_requests} />
      </div>
    </div>
  );
}
