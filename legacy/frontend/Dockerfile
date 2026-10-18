# Legacy v1 frontend (Next.js) — built from the pnpm workspace so the
# root lockfile pins every version.
FROM node:22-alpine
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

# NEXT_PUBLIC_* is baked into the bundle at build time.
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY legacy/frontend/package.json legacy/frontend/package.json
RUN pnpm install --frozen-lockfile --filter frontend...

COPY legacy/frontend legacy/frontend
WORKDIR /app/legacy/frontend
RUN pnpm build

USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:3000/ >/dev/null 2>&1 || exit 1
CMD ["pnpm", "start"]
