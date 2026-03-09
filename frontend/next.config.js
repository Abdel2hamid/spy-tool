/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
};

module.exports = nextConfig;
