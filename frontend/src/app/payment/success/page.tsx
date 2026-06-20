'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { CheckCircle, Zap, Settings, Calendar, Shield } from 'lucide-react';
import Link from 'next/link';

export default function PaymentSuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <PaymentSuccessContent />
    </Suspense>
  );
}

function PaymentSuccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading, workspace } = useAuth();
  const [countdown, setCountdown] = useState(8);

  const sessionId = searchParams.get('session_id');
  const planCode = workspace?.subscription?.plan_code || 'starter';
  const planPrices: Record<string, string> = { starter: '$19.99', pro: '$49.99' };
  const planPrice = planPrices[planCode] || '';
  const trialEndDate = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  });

  // Auto-redirect to dashboard after countdown
  useEffect(() => {
    if (countdown <= 0) {
      router.replace('/');
      return;
    }
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown, router]);

  // If not authenticated, redirect to login
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-6 inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-950">
          <CheckCircle className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
        </div>

        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Payment Method Saved!
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mb-8">
          Your account is now active. Welcome to RankSpy!
        </p>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 mb-8 text-left">
          {/* Plan summary */}
          <div className="flex items-center gap-3 mb-4 pb-4 border-b border-gray-100 dark:border-gray-800">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="font-semibold text-gray-900 dark:text-white capitalize">{planCode} Plan</p>
              {planPrice && (
                <p className="text-sm text-gray-500">{planPrice}/month after trial</p>
              )}
            </div>
          </div>

          {/* Key details */}
          <div className="space-y-3">
            <div className="flex items-start gap-2.5">
              <Calendar className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">7-day free trial active</p>
                <p className="text-xs text-gray-500">Your first charge of {planPrice || 'your plan price'} will be on {trialEndDate}, unless you cancel before then.</p>
              </div>
            </div>
            <div className="flex items-start gap-2.5">
              <Settings className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">Manage your subscription</p>
                <p className="text-xs text-gray-500">You can cancel, upgrade, or change your plan anytime from <Link href="/settings" className="text-indigo-600 hover:underline">Settings &rarr; Billing</Link>.</p>
              </div>
            </div>
            <div className="flex items-start gap-2.5">
              <Shield className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">Secure payment via Stripe</p>
                <p className="text-xs text-gray-500">Your payment details are securely stored by Stripe. We never see your card number.</p>
              </div>
            </div>
          </div>
        </div>

        <Link
          href="/"
          className="inline-flex items-center gap-2 bg-indigo-600 text-white font-semibold px-6 py-3 rounded-lg hover:bg-indigo-700 transition"
        >
          Go to Dashboard
        </Link>

        <p className="mt-4 text-sm text-gray-400">
          Redirecting in {countdown} seconds…
        </p>
      </div>
    </div>
  );
}
