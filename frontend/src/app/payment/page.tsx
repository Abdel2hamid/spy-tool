'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { createStripeCheckout } from '@/lib/api';
import { CreditCard, Zap, AlertCircle } from 'lucide-react';
import Link from 'next/link';

export default function PaymentPage() {
  const { token, workspace, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const planCode = workspace?.subscription?.plan_code || 'free';

  async function handlePay() {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const { checkout_url } = await createStripeCheckout(token, planCode);
      window.location.href = checkout_url;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start checkout. Please try again.');
      setLoading(false);
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    router.replace('/login');
    return null;
  }

  // If payment is already done, go to dashboard
  if (workspace?.subscription?.status !== 'pending_payment') {
    router.replace('/');
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <Link href="/landing" className="inline-flex items-center gap-2.5 mb-6">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Complete Your Registration
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
            Add a payment method to activate your account.
          </p>
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950">
              <CreditCard className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <p className="font-semibold text-gray-900 dark:text-white">Payment Required</p>
              <p className="text-xs text-gray-500">Secure payment via Stripe</p>
            </div>
          </div>

          <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-4 mb-4">
            <p className="text-sm text-gray-700 dark:text-gray-300">
              <strong>Selected plan:</strong>{' '}
              <span className="capitalize">{planCode}</span>
              {planCode !== 'free' && (
                <span className="block text-xs text-gray-500 mt-1">
                  Includes 7-day free trial — you won&apos;t be charged today.
                </span>
              )}
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-2 mb-4 px-3 py-2.5 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
            </div>
          )}

          <button
            onClick={handlePay}
            disabled={loading}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-semibold rounded-lg transition flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Redirecting to checkout…
              </>
            ) : (
              <>
                <CreditCard className="w-4 h-4" />
                Add Payment Method
              </>
            )}
          </button>
        </div>

        <p className="text-center text-xs text-gray-400">
          <button onClick={logout} className="hover:text-gray-600 underline">
            Sign out
          </button>{' '}
          and use a different account
        </p>
      </div>
    </div>
  );
}
