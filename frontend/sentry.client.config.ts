import * as Sentry from '@sentry/nextjs';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

Sentry.init({
  dsn: dsn || undefined,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV || 'development',
  tracesSampleRate: parseFloat(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || '0.0'),
  // Replay is optional; enable only if needed.
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,
  // Suppress Sentry if DSN is not configured (local dev).
  beforeSend(event) {
    if (!dsn) return null;
    return event;
  },
});
