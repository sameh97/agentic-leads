/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for the Docker multi-stage build (copies only what's needed)
  output: 'standalone',

  // Proxy API requests to backend so frontend never exposes the backend URL
  async rewrites() {
    return [
      {
        source:      '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://backend:8000'}/api/:path*`,
      },
    ];
  },

  // Required for SSE (Server-Sent Events) — disable response buffering
  async headers() {
    return [
      {
        source: '/api/leads/stream/:jobId',
        headers: [
          { key: 'X-Accel-Buffering', value: 'no' },
          { key: 'Cache-Control',      value: 'no-cache' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;