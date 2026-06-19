'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  X,
  Zap,
  TrendingUp,
  Search,
  BarChart2,
  Download,
  Crown,
} from 'lucide-react';
import type { UpgradeEventDetail } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type UpgradeReason = UpgradeEventDetail;

interface UpgradeModalContextValue {
  showUpgrade: (reason: UpgradeReason) => void;
}

const UpgradeModalContext = createContext<UpgradeModalContextValue | null>(null);

export function useUpgradeModal(): UpgradeModalContextValue {
  const ctx = useContext(UpgradeModalContext);
  if (!ctx) throw new Error('useUpgradeModal must be used within <UpgradeModalProvider>');
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider + Modal
// ---------------------------------------------------------------------------

const PRO_FEATURES = [
  { icon: TrendingUp, text: 'Unlimited app tracking & imports' },
  { icon: Search, text: 'Unlimited keyword refreshes' },
  { icon: BarChart2, text: 'Full AI-powered analytics' },
  { icon: Download, text: 'CSV & JSON data exports' },
];

const ACTION_LABELS: Record<string, string> = {
  app_imports: 'App Imports',
  keyword_refreshes: 'Keyword Refreshes',
  ai_requests: 'AI Requests',
  exports: 'Data Exports',
};

export function UpgradeModalProvider({ children }: { children: React.ReactNode }) {
  const [reason, setReason] = useState<UpgradeReason | null>(null);
  const router = useRouter();

  const showUpgrade = useCallback((r: UpgradeReason) => {
    setReason(r);
  }, []);

  // Listen for global upgrade events emitted by the API layer
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<UpgradeReason>).detail;
      if (detail) setReason(detail);
    };
    window.addEventListener('rankspy:upgrade', handler);
    return () => window.removeEventListener('rankspy:upgrade', handler);
  }, []);

  const close = useCallback(() => setReason(null), []);

  const handleUpgrade = useCallback(() => {
    close();
    router.push('/signup?plan=pro');
  }, [close, router]);

  return (
    <UpgradeModalContext.Provider value={{ showUpgrade }}>
      {children}

      {/* Modal overlay */}
      {reason && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div
            className="relative w-full max-w-md mx-4 overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-gray-900"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Gradient header */}
            <div className="relative bg-gradient-to-br from-indigo-600 via-violet-600 to-purple-700 px-6 pt-6 pb-8 text-center">
              <button
                onClick={close}
                className="absolute top-3 right-3 rounded-full p-1 text-white/70 hover:bg-white/10 hover:text-white transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
              <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 backdrop-blur-sm">
                <Crown className="h-7 w-7 text-white" />
              </div>
              <h2 className="text-xl font-bold text-white">
                {reason.kind === 'premium_required' ? 'Upgrade to Pro' : 'Usage Limit Reached'}
              </h2>
              <p className="mt-1.5 text-sm text-white/80">
                {reason.message}
              </p>
            </div>

            {/* Body */}
            <div className="px-6 py-5">
              {/* Usage bar for limit_exceeded */}
              {reason.kind === 'limit_exceeded' && (
                <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-amber-800 dark:text-amber-300">
                      {ACTION_LABELS[reason.action] ?? reason.action}
                    </span>
                    <span className="text-xs font-semibold text-amber-700 dark:text-amber-400">
                      {reason.currentUsage} / {reason.limit}
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-amber-200 dark:bg-amber-900">
                    <div
                      className="h-full rounded-full bg-amber-500 transition-all"
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              )}

              {/* Features list */}
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">
                Unlock with Pro
              </p>
              <ul className="space-y-2.5">
                {PRO_FEATURES.map(({ icon: Icon, text }) => (
                  <li key={text} className="flex items-center gap-2.5">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/50">
                      <Icon className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <span className="text-sm text-gray-700 dark:text-gray-300">{text}</span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <button
                onClick={handleUpgrade}
                className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-xl hover:shadow-indigo-500/30 hover:brightness-110"
              >
                <Zap className="h-4 w-4" />
                Upgrade to Pro
              </button>

              <button
                onClick={close}
                className="mt-2 flex w-full items-center justify-center py-2 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
              >
                Maybe later
              </button>
            </div>
          </div>
        </div>
      )}
    </UpgradeModalContext.Provider>
  );
}
