# Changelog

## [0.1.1](https://github.com/anothersunset/Graphrag-copilot/compare/graphrag-api-v0.1.0...graphrag-api-v0.1.1) (2026-10-18)


### Features

* **api:** SQLite run-store backend (backlog P3) ([1b18276](https://github.com/anothersunset/Graphrag-copilot/commit/1b182760226cdcc2425fab46a5d7a74e675d8b13))
* **api:** true token streaming over SSE (backlog P2-8) ([46066e4](https://github.com/anothersunset/Graphrag-copilot/commit/46066e415c4daba50c96914144960a44bf41dab6))
* **api:** wire optional real retrieval stack behind env flags ([36511a8](https://github.com/anothersunset/Graphrag-copilot/commit/36511a81c6f8e0b6391a59aed2268d254387b084))
* **deploy:** Docker deployment for the v3 api+web stack ([07f660b](https://github.com/anothersunset/Graphrag-copilot/commit/07f660b3ce38b8efeb9a20e11a629e5cb72c2c95))
* **eval:** end-to-end Provenance Bench (zh+en gold + adversarial) ([#6](https://github.com/anothersunset/Graphrag-copilot/issues/6)) ([97afdde](https://github.com/anothersunset/Graphrag-copilot/commit/97afdded46ea25dc14cda28d5a09eec17e38389a))
* **ingest:** LLM gleaning extraction in the ingest CLI ([a7dd878](https://github.com/anothersunset/Graphrag-copilot/commit/a7dd878f9a66fee31af3aac02a6c61efed7261b2))
* **kg:** add GraphRAG index layer (gleaning extraction, resolution, Louvain communities, HippoRAG PPR) + wire into orchestrator ([b819268](https://github.com/anothersunset/Graphrag-copilot/commit/b81926810a50b196d9fe1c291d6fa8a7f80726ea))
* **kg:** persist the built index; API boots from artifact (backlog P1-4) ([ac051fe](https://github.com/anothersunset/Graphrag-copilot/commit/ac051fed0349a2f4e438c0533f043329bf00677f))
* v3.1 full — LangGraph 7-node Agentic RAG + four-route retrieval + CRAG + Langfuse + MCP + React Flow ([#4](https://github.com/anothersunset/Graphrag-copilot/issues/4)) ([6a1aad6](https://github.com/anothersunset/Graphrag-copilot/commit/6a1aad69253eea2c13744aa37990ce6eecb0a4d7))
* v3.2 — provenance layer (EvidencePack + sentence-level claims + Provenance Sufficiency + adversarial harness) ([#5](https://github.com/anothersunset/Graphrag-copilot/issues/5)) ([3c84c02](https://github.com/anothersunset/Graphrag-copilot/commit/3c84c0299fd7a2897c0f84cb3272348d41ca1153))
* **web:** port the legacy knowledge-graph UI onto the v3 stack ([b1a1c30](https://github.com/anothersunset/Graphrag-copilot/commit/b1a1c3085399a0c2fd0707a897c15453e5ca057b))


### Bug Fixes

* **graph:** capability-aware planner pruning; verified end-to-end with real LLM ([bcf2dba](https://github.com/anothersunset/Graphrag-copilot/commit/bcf2dbab8b22140d20afd76313500c463a8410c6))
* make Python 3.12 quality gates reproducible ([fc13ac8](https://github.com/anothersunset/Graphrag-copilot/commit/fc13ac8c7037665a9fd0faf3df5bc072570f66f4))
* restore canonical GraphRAG API and evidence contracts ([be7eccf](https://github.com/anothersunset/Graphrag-copilot/commit/be7eccf980f2fc05aeecb62e06e2908fd930049f))
* unblock root Python quality gates ([e48aa02](https://github.com/anothersunset/Graphrag-copilot/commit/e48aa0233c9386e26de661f125313b81aa67e027))
