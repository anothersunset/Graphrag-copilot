FROM node:22-alpine
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY legacy/frontend/package.json legacy/frontend/package.json
RUN pnpm install --frozen-lockfile --filter frontend...

COPY legacy/frontend legacy/frontend
WORKDIR /app/legacy/frontend
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
