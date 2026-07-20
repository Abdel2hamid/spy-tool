const { withSentryConfig } = require('@sentry/nextjs');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  async rewrites() {
    // BACKEND_URL is a server-side env var set in Railway (or .env.local for dev).
    // It must NOT include a trailing slash or path — just the origin.
    // Example: https://backend-production-xxxx.railway.app
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://browser.sentry-cdn.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' https: data:",
              "font-src 'self' https: data:",
              "connect-src 'self' https://*.railway.app https://api.stripe.com https://*.stripe.com https://*.ingest.sentry.io https://sentry.io",
              "frame-src https://js.stripe.com https://hooks.stripe.com https://checkout.stripe.com",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join('; '),
          },
        ],
      },
    ];
  },
};

const sentryWebpackPluginOptions = {
  // Sentry webpack plugin options — disable source maps upload unless
  // SENTRY_AUTH_TOKEN is configured. This keeps local/staging builds fast
  // and avoids failures when Sentry org/project are not set.
  silent: true,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  sourcemaps: {
    // Only generate source maps when we can actually upload them. Prevents
    // serving source maps to users in production without Sentry auth.
    disable: !process.env.SENTRY_AUTH_TOKEN,
  },
};

module.exports = withSentryConfig(nextConfig, sentryWebpackPluginOptions);
