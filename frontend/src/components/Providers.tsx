'use client';

import { ThemeProvider } from 'next-themes';
import { AuthProvider } from '@/lib/auth';
import { UpgradeModalProvider } from '@/components/UpgradeModal';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <AuthProvider>
        <UpgradeModalProvider>
          {children}
        </UpgradeModalProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
