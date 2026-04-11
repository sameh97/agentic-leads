/** @type {import('next').NextConfig} */
const path = require('path')

const nextConfig = {
  // Required for the Docker multi-stage build
  output: 'standalone',

  // Tell Next.js where src lives — fixes @/ alias in Docker builds
  webpack(config) {
    config.resolve.alias['@'] = path.resolve(__dirname, 'src')
    return config
  },

  // Proxy /api/* → backend container (server-side only)
  async rewrites() {
    return [
      {
        source:      '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://backend:8000'}/api/:path*`,
      },
    ]
  },

  // Disable buffering for SSE endpoints
  async headers() {
    return [
      {
        source: '/api/leads/stream/:jobId',
        headers: [
          { key: 'X-Accel-Buffering', value: 'no' },
          { key: 'Cache-Control',      value: 'no-cache' },
        ],
      },
    ]
  },
}

module.exports = nextConfig