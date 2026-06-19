'use client';

export const dynamic = 'force-dynamic';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import DashboardPage from './DashboardClient';
import LandingPage from './landing/page';

export default function Page() {
  const { isAuthenticated, isLoading, isPendingPayment, isTrialExpired } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated && isPendingPayment) {
      router.replace('/payment');
    }
  }, [isLoading, isAuthenticated, isPendingPayment, router]);

  // Trial expired users get the subscribe wall via AuthGuard in DashboardPage
  // No special handling needed here — DashboardPage uses AppShell which includes AuthGuard

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LandingPage />;
  }

  if (isPendingPayment) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return <DashboardPage />;
}
