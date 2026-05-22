# Release process — release-please + Conventional Commits

GraphRAG Copilot v3.1 ships with [release-please](https://github.com/googleapis/release-please-action)
running in `linked-versions` mode so every package and app moves in lockstep.

## How commits drive versions

We use [Conventional Commits](https://www.conventionalcommits.org/). The
prefix of the commit subject controls the next version bump:

| prefix                | bump on pre-1.0   | bump on ≥1.0  | example                                       |
| --------------------- | ----------------- | ------------- | --------------------------------------------- |
| `feat:`               | minor (0.x → 0.y) | minor         | `feat(graph): add CRAG scorer thresholds`     |
| `fix:`                | patch             | patch         | `fix(retrieval): jieba persistence roundtrip` |
| `feat!:` / `BREAKING` | major (after 1.0) | major         | `feat(api)!: rename /ask to /v1/ask`          |
| `chore: / docs: / refactor:` | none      | none          | hygiene only                                  |

Pre-1.0 we set `bump-minor-pre-major: true` so `feat:` lands as a minor
bump rather than a major one — standard library convention.

## Flow

1. PRs merge into `main` with Conventional Commit subjects.
2. `release-please.yml` runs on push to `main`.
3. It opens (or updates) a single rolling release PR titled
   `chore(main): release X.Y.Z` containing version bumps + CHANGELOG
   regeneration for every component.
4. Merging that PR triggers release-please to:
   - tag each component (e.g. `graphrag-graph-v0.2.0`)
   - create a GitHub Release per component
   - update `.release-please-manifest.json`

## Cutting v0.1.0

The initial manifest is pinned at `0.1.0` for every package. The first
release-please run on `main` opens the v0.1.0 release PR; merging it
creates the tags and Releases.

## Notes

- `apps/web` uses `release-type: node` because it has a `package.json`;
  every other component uses `python`.
- We deliberately use `separate-pull-requests: false` to keep a single,
  reviewable release PR per cycle.
