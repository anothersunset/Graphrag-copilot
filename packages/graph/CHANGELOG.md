# Changelog

## [0.1.1](https://github.com/anothersunset/Graphrag-copilot/compare/graphrag-graph-v0.1.0...graphrag-graph-v0.1.1) (2026-07-08)


### Features

* **eval:** end-to-end Provenance Bench (zh+en gold + adversarial) ([#6](https://github.com/anothersunset/Graphrag-copilot/issues/6)) ([97afdde](https://github.com/anothersunset/Graphrag-copilot/commit/97afdded46ea25dc14cda28d5a09eec17e38389a))
* **kg:** add GraphRAG index layer (gleaning extraction, resolution, Louvain communities, HippoRAG PPR) + wire into orchestrator ([b819268](https://github.com/anothersunset/Graphrag-copilot/commit/b81926810a50b196d9fe1c291d6fa8a7f80726ea))
* v3.1 full — LangGraph 7-node Agentic RAG + four-route retrieval + CRAG + Langfuse + MCP + React Flow ([#4](https://github.com/anothersunset/Graphrag-copilot/issues/4)) ([6a1aad6](https://github.com/anothersunset/Graphrag-copilot/commit/6a1aad69253eea2c13744aa37990ce6eecb0a4d7))
* v3.2 — provenance layer (EvidencePack + sentence-level claims + Provenance Sufficiency + adversarial harness) ([#5](https://github.com/anothersunset/Graphrag-copilot/issues/5)) ([3c84c02](https://github.com/anothersunset/Graphrag-copilot/commit/3c84c0299fd7a2897c0f84cb3272348d41ca1153))


### Bug Fixes

* crossdoc accuracy +16.5pp, DeepSeek LLM migration ([23efe95](https://github.com/anothersunset/Graphrag-copilot/commit/23efe958f20ca2384cebea8cee9999b60d6285e7))
* **graph:** repair pytest + harden CI gate ([#21](https://github.com/anothersunset/Graphrag-copilot/issues/21)) ([36878dd](https://github.com/anothersunset/Graphrag-copilot/commit/36878dd67589f180fdb6ce04c65b6ff2a7dd9c5e))
* P0 — strengthen Generator prompt + tune CRAG thresholds ([702a084](https://github.com/anothersunset/Graphrag-copilot/commit/702a084e7f011c6d6a5fd6db3b92815ed314881a))
* resolve JSON parsing, compatibility, and LangGraph integration issues ([f99c004](https://github.com/anothersunset/Graphrag-copilot/commit/f99c00432241ef3cf85c055f02d6e678010ea5bc))


### Performance Improvements

* optimize multihop faithfulness + BM25 noise reduction ([0c4ed20](https://github.com/anothersunset/Graphrag-copilot/commit/0c4ed207f8cca8623ce178559ad9ca122546d3ea))
