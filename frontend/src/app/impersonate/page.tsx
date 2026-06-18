'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Impersonate page — opened in a new tab by the admin console.
 * Reads the impersonate token from sessionStorage, sets it as the
 * auth_token in localStorage, and redirects to the dashboard.
 */
export default function ImpersonatePage() {
  const router = useRouter();

  useEffect(() => {
    const token = sessionStorage.getItem('impersonate_token');
    if (token) {
      sessionStorage.removeItem('impersonate_token');
      localStorage.setItem('auth_token', token);
      window.location.href = '/';
    } else {
      router.replace('/login');
    }
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-gray-500">Logging in as user...</p>
      </div>
    </div>
  );
}
