# ─────────────────────────────────────────────────────────────
# Stage 1: dependency installer
# ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app

# Install dependencies only (layer cache-friendly)
COPY package.json package-lock.json* ./
RUN npm ci --frozen-lockfile


# ─────────────────────────────────────────────────────────────
# Stage 2: Next.js builder
# ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_ vars must be available at build time
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build


# ─────────────────────────────────────────────────────────────
# Stage 3: minimal runtime image
# ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS runtime

WORKDIR /app
ENV NODE_ENV=production

# Only copy what Next.js needs to run
COPY --from=builder /app/public         ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static   ./.next/static

# Non-root user
RUN addgroup -g 1001 -S nodejs \
 && adduser  -S nextjs -u 1001 -G nodejs
USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD wget -qO- http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]