# @graphrag/web — Next.js 15 frontend image.
#
# Build with pnpm from the repository root workspace (the lockfile pins
# every version), then ship the `output: "standalone"` server bundle:
# .next/standalone already contains the pruned node_modules tree, so the
# runtime image is just the server + static assets.

# syntax=docker/dockerfile:1
FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/
RUN pnpm install --frozen-lockfile
COPY apps/web ./apps/web
RUN pnpm --filter @graphrag/web build

FROM node:22-alpine AS runner
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup --system nodejs && adduser --system nextjs --ingroup nodejs
WORKDIR /app
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
