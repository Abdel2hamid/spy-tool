'use client';

/**
 * AuthGuard — wraps any page/layout that requires authentication.
 *
 * While loading: shows a centered spinner.
 * If unauthenticated: redirects to /login.
 * If superadmin on a regular page: redirects to /admin.
 * If authenticated: renders children.
 */

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth();
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
          <p className="text-sm text-gray-500">Loading…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;
  // Block regular pages for superadmins (they'll be redirected)
  if (user?.is_superadmin && !pathname.startsWith('/admin')) return null;

  return <>{children}</>;
}
