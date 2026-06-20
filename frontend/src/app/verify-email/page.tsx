'use client';

import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Mail, CheckCircle, AlertCircle, Zap, ArrowRight, RefreshCw } from 'lucide-react';
import { authVerifyEmail, authResendVerification, authCreateCheckoutAfterVerify } from '@/lib/api';

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [pageStatus, setPageStatus] = useState<'waiting' | 'verifying' | 'verified' | 'error'>('waiting');
  const [error, setError] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);
  const [pendingEmail, setPendingEmail] = useState('');
  const [redirectMsg, setRedirectMsg] = useState('');

  useEffect(() => {
    const stored = localStorage.getItem('pending_verification_email');
    if (stored) setPendingEmail(stored);
  }, []);

  // If token is present in URL, auto-verify
  useEffect(() => {
    if (!token) return;
    setPageStatus('verifying');

    authVerifyEmail(token)
      .then(async () => {
        setPageStatus('verified');
        localStorage.removeItem('pending_verification_email');

        // Now create Stripe checkout session
        const authToken = localStorage.getItem('auth_token');
        if (authToken) {
          try {
            setRedirectMsg('Setting up your payment...');
            const { checkout_url } = await authCreateCheckoutAfterVerify(authToken);
            if (checkout_url) {
              setRedirectMsg('Redirecting to checkout...');
              setTimeout(() => {
                window.location.href = checkout_url;
              }, 1500);
              return;
            }
          } catch {
            // Stripe not configured — go to dashboard
          }
        }
        setRedirectMsg('Redirecting to dashboard...');
        setTimeout(() => router.replace('/'), 2000);
      })
      .catch((err) => {
        setPageStatus('error');
        setError(err.message);
      });
  }, [token, router]);

  async function handleResend() {
    if (!pendingEmail || resendCooldown > 0) return;
    try {
      await authResendVerification(pendingEmail);
      setResendCooldown(60);
    } catch {
      // silent
    }
  }

  // Cooldown timer
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setTimeout(() => setResendCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [resendCooldown]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <Link href="/landing" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">RankSpy</span>
          </Link>
        </div>
      </header>

      <div className="flex items-center justify-center px-4 py-20">
        <div className="max-w-md w-full text-center">
          {/* Waiting — check your inbox */}
          {pageStatus === 'waiting' && (
            <>
              <div className="mb-6 inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-950">
                <Mail className="w-8 h-8 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Check your inbox</h1>
              <p className="text-gray-500 dark:text-gray-400 mb-2">
                We sent a verification link to
              </p>
              {pendingEmail && (
                <p className="text-sm font-semibold text-gray-900 dark:text-white mb-6">{pendingEmail}</p>
              )}
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Click the link in the email to verify your account and continue to payment setup.
              </p>
              <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-4 py-3 mb-8 text-left">
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  <strong>Next step:</strong> After verifying your email, you&apos;ll be asked to add a payment method. Your 7-day free trial starts immediately — you won&apos;t be charged until the trial ends.
                </p>
              </div>

              <button
                onClick={handleResend}
                disabled={resendCooldown > 0}
                className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-700 disabled:text-gray-400 disabled:cursor-not-allowed transition"
              >
                <RefreshCw className="w-4 h-4" />
                {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend verification email'}
              </button>

              <p className="mt-8 text-xs text-gray-400">
                Didn&apos;t receive the email? Check your spam folder or{' '}
                <button onClick={handleResend} className="text-indigo-600 hover:underline">
                  try again
                </button>
                .
              </p>
            </>
          )}

          {/* Verifying */}
          {pageStatus === 'verifying' && (
            <>
              <div className="mb-6 inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-950">
                <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Verifying your email...</h1>
              <p className="text-gray-500 dark:text-gray-400">Please wait a moment.</p>
            </>
          )}

          {/* Verified */}
          {pageStatus === 'verified' && (
            <>
              <div className="mb-6 inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-950">
                <CheckCircle className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Email verified!</h1>
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                {redirectMsg || 'Redirecting...'}
              </p>
              <div className="flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              </div>
            </>
          )}

          {/* Error */}
          {pageStatus === 'error' && (
            <>
              <div className="mb-6 inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 dark:bg-red-950">
                <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Verification failed</h1>
              <p className="text-red-600 dark:text-red-400 text-sm mb-6">{error}</p>

              {pendingEmail && (
                <button
                  onClick={handleResend}
                  disabled={resendCooldown > 0}
                  className="inline-flex items-center gap-2 bg-indigo-600 text-white font-semibold px-6 py-3 rounded-lg hover:bg-indigo-700 transition disabled:opacity-60"
                >
                  <RefreshCw className="w-4 h-4" />
                  {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Send new verification link'}
                </button>
              )}

              <p className="mt-6 text-sm text-gray-500">
                <Link href="/signup" className="text-indigo-600 hover:underline">
                  Back to sign up
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
