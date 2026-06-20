import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/Providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: {
    default: 'RankSpy — AI-Powered App Store Intelligence',
    template: '%s | RankSpy',
  },
  description: 'AI-powered App Store intelligence — discover opportunities, track rankings, and spy on competitors.',
  metadataBase: new URL('https://rankspy.app'),
  openGraph: {
    type: 'website',
    siteName: 'RankSpy',
    title: 'RankSpy — AI-Powered App Store Intelligence',
    description: 'Discover App Store opportunities, track keyword rankings, monitor competitors, and get AI-generated insights.',
    url: 'https://rankspy.app',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'RankSpy — AI-Powered App Store Intelligence',
    description: 'Discover App Store opportunities, track keyword rankings, monitor competitors, and get AI-generated insights.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className}`}>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
