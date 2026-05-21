# infra/docker

Local development infrastructure for GraphRAG Copilot v3.1.

## Bring up

```bash
cp infra/docker/.env.example infra/docker/.env
docker compose -f infra/docker/docker-compose.dev.yml \
  --env-file infra/docker/.env up -d
```

## Services

| service     | host port     | purpose                            | landed in |
| ----------- | ------------- | ---------------------------------- | --------- |
| qdrant      | 6333 / 6334   | vector DB                          | W3        |
| neo4j       | 7474 / 7687   | knowledge graph (APOC enabled)     | W3        |
| langfuse-db | (internal)    | postgres for langfuse              | W5        |
| langfuse    | 3010          | trace + eval UI                    | W5        |

## Health checks

- Qdrant: `curl -fsS http://localhost:6333/healthz`
- Neo4j: open <http://localhost:7474> (login: `neo4j` / password from `NEO4J_AUTH`)
- Langfuse: open <http://localhost:3010>

## Tear down

```bash
docker compose -f infra/docker/docker-compose.dev.yml down          # keep volumes
docker compose -f infra/docker/docker-compose.dev.yml down -v       # nuke data
```

## Production note

This compose file is intentionally **dev-only**:

- Default credentials are placeholders.
- No TLS, no reverse proxy, no resource limits.
- Volumes are local Docker volumes, not durable storage.

Production manifests (kubernetes + sealed-secrets) land in W8 release notes.
