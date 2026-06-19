'use client';

/**
 * AuthGuard — wraps any page/layout that requires authentication.
 *
 * While loading: shows a centered spinner.
 * If unauthenticated: redirects to /login.
 * If trial expired: shows subscribe wall.
 * If superadmin on a regular page: redirects to /admin.
 * If authenticated: renders children.
 */

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Crown, Zap, Check, ArrowRight, LogOut } from 'lucide-react';
import { createStripeCheckout } from '@/lib/api';

function SubscribeWall() {
  const { workspace, token, logout } = useAuth();
  const sub = workspace?.subscription;

  async function handleSubscribe(plan: string) {
    if (!token) return;
    try {
      const data = await createStripeCheckout(token, plan);
      const url = data?.checkout_url;
      if (url?.startsWith('https://')) {
        window.location.href = url;
      }
    } catch {
      // Fallback: redirect to signup with plan preselected
      window.location.href = `/signup?plan=${plan}`;
    }
  }

  const plans = [
    {
      code: 'starter',
      name: 'Starter',
      price: '$29',
      period: '/month',
      features: ['100 app imports/mo', '200 keyword refreshes/mo', '100 AI requests/mo', '50 exports/mo', 'All premium features'],
    },
    {
      code: 'pro',
      name: 'Pro',
      price: '$79',
      period: '/month',
      popular: true,
      features: ['Unlimited app imports', 'Unlimited keyword refreshes', 'Unlimited AI requests', 'Unlimited exports', 'All premium features'],
    },
    {
      code: 'enterprise',
      name: 'Enterprise',
      price: '$199',
      period: '/month',
      features: ['Everything in Pro', 'Priority support', 'Custom integrations', 'Dedicated account manager', 'SLA guarantee'],
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="max-w-4xl w-full">
          {/* Hero */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 px-4 py-2 rounded-full text-sm font-medium mb-4">
              <Crown className="h-4 w-4" />
              Your free trial has ended
            </div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-3">
              Subscribe to continue using RankSpy
            </h1>
            <p className="text-gray-500 dark:text-gray-400 max-w-lg mx-auto">
              Your 7-day free trial has expired. Choose a plan below to unlock full access
              to all App Store intelligence tools.
            </p>
          </div>

          {/* Plan cards */}
          <div className="grid md:grid-cols-3 gap-5">
            {plans.map((plan) => (
              <div
                key={plan.code}
                className={`relative rounded-xl border-2 bg-white dark:bg-gray-900 p-6 ${
                  plan.popular
                    ? 'border-indigo-500 shadow-lg ring-1 ring-indigo-500/20'
                    : 'border-gray-200 dark:border-gray-700'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-indigo-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                    <Crown className="w-3 h-3" /> Most Popular
                  </div>
                )}

                <h3 className="text-lg font-bold text-gray-900 dark:text-white">{plan.name}</h3>
                <div className="mt-2 mb-5">
                  <span className="text-3xl font-bold text-gray-900 dark:text-white">{plan.price}</span>
                  <span className="text-sm text-gray-500">{plan.period}</span>
                </div>

                <ul className="space-y-2 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                      <span className="text-gray-700 dark:text-gray-300">{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSubscribe(plan.code)}
                  className={`w-full py-2.5 rounded-lg font-semibold text-sm transition flex items-center justify-center gap-1.5 ${
                    plan.popular
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  Subscribe Now <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          <p className="text-center mt-8 text-xs text-gray-400">
            Secure payment via Stripe. Cancel anytime.
          </p>
        </div>
      </div>
    </div>
  );
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, isLoading, isTrialExpired } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }
    // Superadmins always go to admin console
    if (user?.is_superadmin && !pathname.startsWith('/admin')) {
      router.replace('/admin');
    }
  }, [isAuthenticated, isLoading, user, router, pathname]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;
  // Block regular pages for superadmins (they'll be redirected)
  if (user?.is_superadmin && !pathname.startsWith('/admin')) return null;

  // Trial expired — show subscribe wall (superadmins bypass)
  if (isTrialExpired && !user?.is_superadmin) {
    return <SubscribeWall />;
  }

  return <>{children}</>;
}
