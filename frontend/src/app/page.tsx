'use client';

export const dynamic = 'force-dynamic';

import { useAuth } from '@/lib/auth';
import DashboardPage from './DashboardClient';
import LandingPage from './landing/page';

export default function Page() {
  const { isAuthenticated, isLoading } = useAuth();

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

  return <DashboardPage />;
}
