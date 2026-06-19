'use client';

import { Suspense, useState, useEffect, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Eye, EyeOff, Zap, Check, ArrowLeft, ArrowRight, Crown } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function SignupPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <SignupContent />
    </Suspense>
  );
}

// ---------------------------------------------------------------------------
// Plan data
// ---------------------------------------------------------------------------

const PLANS = [
  {
    code: 'starter',
    name: 'Starter',
    price: '$29',
    period: '/month',
    description: 'For indie developers getting started',
    features: [
      '100 app imports / month',
      '200 keyword refreshes / month',
      '100 AI requests / month',
      '50 exports / month',
      'All premium features',
    ],
    excluded: [],
    cta: 'Start 7-Day Free Trial',
    popular: false,
  },
  {
    code: 'pro',
    name: 'Pro',
    price: '$79',
    period: '/month',
    description: 'For serious ASO professionals',
    features: [
      'Unlimited app imports',
      'Unlimited keyword refreshes',
      'Unlimited AI requests',
      'Unlimited exports',
      'All premium features',
    ],
    excluded: [],
    cta: 'Start 7-Day Free Trial',
    popular: true,
  },
  {
    code: 'enterprise',
    name: 'Enterprise',
    price: '$199',
    period: '/month',
    description: 'For teams and agencies',
    features: [
      'Everything in Pro',
      'Priority support',
      'Custom integrations',
      'Dedicated account manager',
      'SLA guarantee',
    ],
    excluded: [],
    cta: 'Start 7-Day Free Trial',
    popular: false,
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function SignupContent() {
  const { register, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Steps: 1 = plan selection, 2 = account details
  const [step, setStep] = useState(1);
  const [selectedPlan, setSelectedPlan] = useState(searchParams.get('plan') || '');

  // Account form
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // If plan was passed in URL, jump to step 2
  useEffect(() => {
    const planParam = searchParams.get('plan');
    if (planParam && PLANS.some((p) => p.code === planParam)) {
      setSelectedPlan(planParam);
      setStep(2);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace('/');
    }
  }, [isAuthenticated, isLoading, router]);

  function handleSelectPlan(code: string) {
    setSelectedPlan(code);
    setStep(2);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password.length > 72) {
      setError('Password must be at most 72 characters.');
      return;
    }
    if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/\d/.test(password)) {
      setError('Password must contain uppercase, lowercase, and a digit.');
      return;
    }

    setSubmitting(true);
    try {
      const checkoutUrl = await register(email, password, fullName || undefined, selectedPlan || 'starter');

      if (checkoutUrl && checkoutUrl.startsWith('https://checkout.stripe.com/')) {
        // Redirect to Stripe Checkout for card collection
        window.location.href = checkoutUrl;
      } else if (!checkoutUrl) {
        // No Stripe configured — go to dashboard
        router.replace('/');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
      setSubmitting(false);
    }
  }

  if (isLoading || isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const planInfo = PLANS.find((p) => p.code === selectedPlan);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <Link href="/landing" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
          </Link>
          <p className="text-sm text-gray-500">
            Already have an account?{' '}
            <Link href="/login" className="text-indigo-600 hover:text-indigo-700 font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </header>

      {/* Step indicator */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        <div className="flex items-center justify-center gap-3 text-sm">
          <span className={cn('flex items-center gap-1.5 font-medium', step === 1 ? 'text-indigo-600' : 'text-gray-400')}>
            <span className={cn('w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold', step === 1 ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-700')}>1</span>
            Choose Plan
          </span>
          <div className="w-12 h-px bg-gray-300 dark:bg-gray-700" />
          <span className={cn('flex items-center gap-1.5 font-medium', step === 2 ? 'text-indigo-600' : 'text-gray-400')}>
            <span className={cn('w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold', step === 2 ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-700')}>2</span>
            Create Account
          </span>
          <div className="w-12 h-px bg-gray-300 dark:bg-gray-700" />
          <span className="flex items-center gap-1.5 font-medium text-gray-400">
            <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-gray-200 text-gray-500 dark:bg-gray-700">3</span>
            Payment
          </span>
        </div>
      </div>

      {/* Step 1: Plan Selection */}
      {step === 1 && (
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="text-center mb-10">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Choose your plan</h1>
            <p className="text-gray-500 dark:text-gray-400">All plans include a 7-day free trial. No charge until the trial ends.</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
            {PLANS.map((plan) => (
              <div
                key={plan.code}
                className={cn(
                  'relative rounded-xl border-2 bg-white dark:bg-gray-900 p-6 transition-all cursor-pointer hover:shadow-lg',
                  plan.popular
                    ? 'border-indigo-500 shadow-md ring-1 ring-indigo-500/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-700',
                )}
                onClick={() => handleSelectPlan(plan.code)}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-indigo-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                    <Crown className="w-3 h-3" /> Most Popular
                  </div>
                )}

                <h3 className="text-lg font-bold text-gray-900 dark:text-white">{plan.name}</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 mb-4">{plan.description}</p>

                <div className="mb-5">
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
                  {plan.excluded.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <span className="w-4 h-4 flex items-center justify-center text-gray-300 mt-0.5 flex-shrink-0">✕</span>
                      <span className="text-gray-400">{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  className={cn(
                    'w-full py-2.5 rounded-lg font-semibold text-sm transition',
                    plan.popular
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-700',
                  )}
                >
                  {plan.cta} <ArrowRight className="w-4 h-4 inline ml-1" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step 2: Account Details */}
      {step === 2 && (
        <div className="max-w-md mx-auto px-4 sm:px-6 lg:px-8 py-10">
          {/* Selected plan summary */}
          {planInfo && (
            <div className="mb-6 p-4 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/30">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-indigo-900 dark:text-indigo-200">
                    {planInfo.name} Plan — {planInfo.price}{planInfo.period}
                  </p>
                  {planInfo.code !== 'free' && (
                    <p className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">
                      Includes 7-day free trial
                    </p>
                  )}
                </div>
                <button
                  onClick={() => setStep(1)}
                  className="text-xs text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
                >
                  <ArrowLeft className="w-3 h-3" /> Change
                </button>
              </div>
            </div>
          )}

          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-1">Create your account</h2>
          <p className="text-gray-500 dark:text-gray-400 mb-6 text-sm">
            Next, you&apos;ll add your payment method to activate your plan.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                Full name <span className="text-gray-400">(optional)</span>
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Jane Smith"
                className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3.5 py-2.5 pr-10 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {password.length > 0 && password.length < 8 && (
                <p className="mt-1 text-xs text-amber-600">{8 - password.length} more characters needed</p>
              )}
            </div>

            {error && (
              <div className="px-3.5 py-2.5 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition flex items-center justify-center gap-2 mt-2"
            >
              {submitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Creating account…
                </>
              ) : (
                <>
                  Continue to Payment <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
            Already have an account?{' '}
            <Link href="/login" className="text-indigo-600 hover:text-indigo-700 font-medium">
              Sign in
            </Link>
          </p>

          <p className="mt-4 text-center text-xs text-gray-400">
            By signing up, you agree to our{' '}
            <Link href="/terms" className="underline hover:text-gray-600">Terms of Service</Link>{' '}
            and{' '}
            <Link href="/privacy" className="underline hover:text-gray-600">Privacy Policy</Link>.
          </p>
        </div>
      )}
    </div>
  );
}
