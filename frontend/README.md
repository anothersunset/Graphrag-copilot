# Legacy frontend (v1)

This Next.js application is retained only for the legacy `backend/` and root
`docker-compose.yml` demonstration stack. It is not the supported GraphRAG
Copilot product entrypoint.

- Supported web application: `apps/web`
- Supported API: `apps/api`
- Root `pnpm lint`, `pnpm typecheck`, and `pnpm build` intentionally target
  `@graphrag/web` only.
- Run legacy checks explicitly from this directory with `pnpm lint` and
  `pnpm build` when maintaining the v1 demonstration.

Do not add new product features here. Port required compatibility behavior to
`apps/web` and keep this application isolated from canonical CI and docs.
