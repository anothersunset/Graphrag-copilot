## What

<!-- One-line summary of the change. -->

## Why

<!-- Link issues, ADRs, or roadmap section. -->

Closes #

## How

<!-- Brief implementation notes; reviewer-friendly. -->

## Verification

- [ ] `make lint typecheck test` passes locally
- [ ] New tests added (diff coverage ≥ 70% from W5)
- [ ] ADR added if introducing new tech or architecture change
- [ ] CHANGELOG `[Unreleased]` updated
- [ ] Screenshots / trace IDs attached if user-visible

## Architecture invariants checklist

- [ ] Every retrieval emits a `RetrievalTrace`
- [ ] Every tool call goes through `ToolSpec` registry
- [ ] Every CRAG decision is logged
