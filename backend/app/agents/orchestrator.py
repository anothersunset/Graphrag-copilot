"""GraphRAG Copilot — 多智能体编排器.

v3.2: 接入 packages/graph 的 LangGraph 7 节点流水线:
  planner → retriever → evaluator(CRAG) → [rewriter → retriever] → generator → auditor

保留旧版 MultiAgentOrchestrator 作为 LegacyOrchestrator 备选。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List

logger = logging.getLogger(__name__)


def _get_llm_service():
    from app.services.llm_service import llm_service
    return llm_service


def _get_vector_store():
    from app.services.vector_store import vector_store, embedding_service
    return vector_store, embedding_service


def _get_bm25_store():
    from app.services.bm25_store import bm25_store
    return bm25_store


def _get_kg_service():
    from app.services.kg_service import kg_service
    return kg_service


def _get_evidence_fusion():
    from app.services.evidence_fusion import evidence_fusion_service
    return evidence_fusion_service


# ─────────────────── LLM 适配器 ───────────────────


class LLMAdapter:
    """将 backend 的 LLMService 适配为 packages/graph 期望的 llm_client 接口.

    packages/graph 的 generator_node 调用:
        llm.complete(model=..., system=..., user=..., timeout_s=...)
    """

    def complete(self, *, model: str = "", system: str = "", user: str = "", timeout_s: float = 20.0) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if user:
            messages.append({"role": "user", "content": user})
        # planner 短 prompt 用更少 max_tokens
        max_tokens = 300 if len(user) < 200 else None
        kwargs = {}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return _get_llm_service().chat(messages, **kwargs)


# ─────────────────── LangGraph 编排器 ───────────────────


class LangGraphOrchestrator:
    """基于 packages/graph 的 7 节点 Agentic RAG 编排器.

    流程: planner → retriever → evaluator(CRAG) → [rewriter → retriever] → generator → auditor
    """

    def __init__(self):
        from graphrag_graph.graph import build_graph
        from graphrag_graph.config import GraphConfig
        from app.agents.retriever_adapters import build_retrievers

        self._graph = build_graph(
            config=GraphConfig(
                enable_kg=True,
                max_rewrites=1,
                max_hits=20,
                top_k_after_rerank=5,
                llm_timeout_s=20.0,
            ),
            retrievers=build_retrievers(),
            llm_client=LLMAdapter(),
        )

    def process_query(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        from graphrag_graph.state import initial_state

        state = initial_state(query)
        try:
            result = self._graph.invoke(state)
        except Exception as e:
            logger.exception("LangGraph pipeline failed")
            # 返回拒答而非崩溃
            return {
                "query": query,
                "answer": "根据现有信息无法回答这个问题。",
                "sources": [],
                "citations": [],
                "confidence": 0.0,
                "crag_decision": "fallback",
                "auditor_verdict": "fail",
                "trace": {"nodes": ["planner", "retriever", "evaluator"], "audit": [], "tool_calls": [], "rewrite_iteration": 0},
            }
        return self._format_response(query, result)

    def _format_response(self, query: str, state: dict) -> Dict[str, Any]:
        """将 LangGraph state 转换为 API 响应格式."""
        answer = state.get("answer", "当前信息不足，无法回答。")
        fused_hits = state.get("fused_hits", [])
        citations = state.get("citations", [])
        audit_entries = state.get("audit", [])

        # 构造 sources 列表
        sources = []
        for hit in fused_hits[:5]:
            sources.append({
                "content": hit.get("content", "")[:300],
                "source": hit.get("source", ""),
                "score": hit.get("rerank_score") or hit.get("score", 0.0),
                "chunk_id": hit.get("chunk_id", ""),
            })

        # 构造 trace（7 节点执行记录）
        trace_nodes = []
        for entry in audit_entries:
            node_name = entry.get("node", "")
            if node_name and node_name not in trace_nodes:
                trace_nodes.append(node_name)

        return {
            "query": query,
            "answer": answer,
            "sources": sources,
            "citations": [
                {"chunk_id": c.get("chunk_id", ""), "span": c.get("span", ""), "confidence": c.get("confidence", 0.0)}
                for c in citations
            ],
            "confidence": state.get("crag_score", 0.0),
            "crag_decision": state.get("crag_decision", "unknown"),
            "auditor_verdict": state.get("auditor_verdict", "unknown"),
            "trace": {
                "nodes": trace_nodes,
                "audit": audit_entries,
                "tool_calls": state.get("tool_calls", []),
                "rewrite_iteration": state.get("rewrite_iteration", 0),
            },
        }


# ─────────────────── 旧版编排器（保留备选） ───────────────────


class QueryUnderstandingAgent:
    def analyze(self, query: str) -> Dict[str, Any]:
        system_prompt = (
            "分析用户问题，只输出 JSON:\n"
            '{"intent": "query|compare|summarize|analyze|recommend", "entities": [], "keywords": [], "complexity": "simple|medium|complex", "requires_multi_hop": false, "query_rewrite": ""}'
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        result = _get_llm_service().chat_json(messages)
        return {
            "intent": result.get("intent", "query"),
            "entities": result.get("entities", []),
            "keywords": result.get("keywords", []),
            "complexity": result.get("complexity", "medium"),
            "requires_multi_hop": result.get("requires_multi_hop", False),
            "query_rewrite": result.get("query_rewrite", query) or query,
            "original_query": query,
        }


class RetrievalAgent:
    def hybrid_search(self, query: str, entities: List[str], top_k: int = 10) -> Dict[str, Any]:
        results = {
            "vector_results": [],
            "bm25_results": [],
            "graph_results": {},
            "combined_context": [],
            "warnings": [],
        }

        try:
            vs, es = _get_vector_store()
            query_embedding = es.embed_query(query)
            results["vector_results"] = vs.search(query_embedding, top_k=top_k)
        except Exception as e:
            results["warnings"].append("vector_search_failed: " + str(e))

        try:
            results["bm25_results"] = _get_bm25_store().search(query, top_k=top_k)
        except Exception as e:
            results["warnings"].append("bm25_search_failed: " + str(e))

        if entities:
            try:
                results["graph_results"] = _get_kg_service().graph_rag_search(entities, query, depth=2)
            except Exception as e:
                results["warnings"].append("graph_search_failed: " + str(e))

        ef = _get_evidence_fusion()
        fused = ef.fuse(
            vector_results=results["vector_results"],
            bm25_results=results["bm25_results"],
            graph_results=results["graph_results"],
            top_k=top_k,
        )
        results["combined_context"] = ef.compress_context(fused)
        return results


class ReasoningAgent:
    def reason(self, query: str, context: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
        context_text = "\n\n".join([
            "[" + str(i + 1) + "] 类型: " + str(c.get("type")) + "; 来源: " + str(c.get("source")) + "; 分数: " + str(c.get("fusion_score", c.get("score", 0))) + "\n" + str(c.get("content", ""))
            for i, c in enumerate(context[:10])
        ])

        if not context_text.strip():
            return {
                "answer": "当前知识库中没有找到足够信息回答这个问题。",
                "reasoning_path": ["没有召回到有效证据"],
                "sources_used": [],
                "confidence": 0.0,
                "limitations": "retrieval_empty",
            }

        system_prompt = (
            "你是严谨的企业知识问答助手。必须基于给定上下文回答。\n"
            "要求:\n"
            "1. 只基于上下文回答，不允许编造。\n"
            "2. 每个关键结论尽量标注来源编号。\n"
            "3. 如果证据不足，明确说明不足。\n"
            "4. 输出 reasoning_path，说明从哪些证据推到结论。\n\n"
            "只输出 JSON:\n"
            '{"answer": "回答", "reasoning_path": [], "sources_used": [], "confidence": 0.0, "limitations": ""}'
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "问题: " + query + "\n\n问题分析: " + str(analysis) + "\n\n上下文:\n" + context_text},
        ]

        result = _get_llm_service().chat_json(messages)
        # 如果 JSON 解析失败（推理模型可能返回非 JSON 文本），从原始文本提取答案
        if "answer" not in result:
            raw = result.get("raw_response", "")
            logger.warning("ReasoningAgent: JSON 解析失败, raw=%s", str(raw)[:300])
            # 尝试从原始响应中提取答案（跳过推理部分，取最后一个段落）
            if raw:
                # 去掉可能的推理文本，尝试找 JSON
                import re
                json_match = re.search(r'"answer"\s*:\s*"([^"]*)"', raw)
                if json_match:
                    result["answer"] = json_match.group(1)
                else:
                    # 取最后一个非空段落作为答案
                    paragraphs = [p.strip() for p in raw.split("\n") if p.strip() and not p.strip().startswith("{")]
                    if paragraphs:
                        result["answer"] = paragraphs[-1][:2000]
        return {
            "answer": result.get("answer", "当前信息不足，无法回答。"),
            "reasoning_path": result.get("reasoning_path", []),
            "sources_used": result.get("sources_used", []),
            "confidence": float(result.get("confidence", 0.0) or 0.0),
            "limitations": result.get("limitations", ""),
        }


class VerificationAgent:
    def verify(self, query: str, answer: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        source_texts = [s.get("content", "") for s in sources[:5]]
        return _get_llm_service().verify_answer(query, answer, source_texts)


class GenerationAgent:
    def generate(self, reasoning_result: Dict[str, Any], verification_result: Dict[str, Any]) -> str:
        answer = reasoning_result.get("answer", "当前信息不足，无法回答。")
        confidence = verification_result.get("confidence", reasoning_result.get("confidence", 0.0))

        final_answer = answer

        sources = reasoning_result.get("sources_used", [])
        if sources:
            final_answer += "\n\n参考来源:\n"
            for i, source in enumerate(sources, 1):
                final_answer += str(i) + ". " + str(source) + "\n"

        if confidence < 0.6:
            final_answer += "\n\n注意: 当前答案置信度较低，建议结合原文进一步核实。"

        issues = verification_result.get("issues", [])
        if issues:
            final_answer += "\n\n验证提示:\n"
            for issue in issues:
                final_answer += "- " + str(issue) + "\n"

        return final_answer


class LegacyOrchestrator:
    """旧版 5 节点手动编排（保留作为 fallback）."""

    def __init__(self):
        self.query_agent = QueryUnderstandingAgent()
        self.retrieval_agent = RetrievalAgent()
        self.reasoning_agent = ReasoningAgent()
        self.verification_agent = VerificationAgent()
        self.generation_agent = GenerationAgent()

    def process_query(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        analysis = self.query_agent.analyze(query)

        retrieval_results = self.retrieval_agent.hybrid_search(
            query=analysis.get("query_rewrite", query),
            entities=analysis.get("entities", []),
            top_k=top_k,
        )

        reasoning_result = self.reasoning_agent.reason(
            query=query,
            context=retrieval_results.get("combined_context", []),
            analysis=analysis,
        )

        verification_result = self.verification_agent.verify(
            query=query,
            answer=reasoning_result.get("answer", ""),
            sources=retrieval_results.get("combined_context", []),
        )

        final_answer = self.generation_agent.generate(reasoning_result, verification_result)

        confidence = float(
            verification_result.get("confidence", reasoning_result.get("confidence", 0.0)) or 0.0
        )

        return {
            "query": query,
            "analysis": analysis,
            "answer": final_answer,
            "reasoning": reasoning_result,
            "verification": verification_result,
            "sources": retrieval_results.get("combined_context", [])[:5],
            "graph_context": retrieval_results.get("graph_results", {}),
            "confidence": confidence,
            "trace": {
                "analysis": analysis,
                "retrieval": retrieval_results,
                "reasoning": reasoning_result,
                "verification": verification_result,
            },
        }


# ─────────────────── 流式编排器 ───────────────────


class StreamingReasoningAgent:
    """流式推理 Agent - 逐 token 输出答案."""

    def reason_stream(self, query: str, context: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Generator[str, None, None]:
        context_text = "\n\n".join([
            "[" + str(i + 1) + "] 类型: " + str(c.get("type")) + "; 来源: " + str(c.get("source")) + "; 分数: " + str(c.get("fusion_score", c.get("score", 0))) + "\n" + str(c.get("content", ""))
            for i, c in enumerate(context[:10])
        ])

        if not context_text.strip():
            yield "当前知识库中没有找到足够信息来回答这个问题。"
            return

        system_prompt = (
            "你是一个严谨的企业知识问答助手。必须基于给定上下文回答问题。\n"
            "要求:\n"
            "1. 只基于上下文回答，不允许编造。\n"
            "2. 每个关键结论尽量标注来源编号（如[1]）。\n"
            "3. 如果证据不足，明确说明不足。\n"
            "4. 用简洁清晰的中文回答。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "问题: " + query + "\n\n问题分析: " + str(analysis) + "\n\n上下文:\n" + context_text},
        ]

        yield from _get_llm_service().chat_stream(messages)


class StreamingOrchestrator:
    """流式编排器 - 前置步骤同步，LLM 生成流式输出."""

    def __init__(self):
        self.query_agent = QueryUnderstandingAgent()
        self.retrieval_agent = RetrievalAgent()
        self.streaming_reasoner = StreamingReasoningAgent()
        self.verification_agent = VerificationAgent()

    def process_query_stream(self, query: str, top_k: int = 10) -> Generator[Dict[str, Any], None, None]:
        # Phase 1: 问题理解
        analysis = self.query_agent.analyze(query)
        yield {"type": "phase", "phase": "analysis", "data": analysis}

        # Phase 2: 混合检索
        retrieval_results = self.retrieval_agent.hybrid_search(
            query=analysis.get("query_rewrite", query),
            entities=analysis.get("entities", []),
            top_k=top_k,
        )
        yield {
            "type": "phase",
            "phase": "retrieval",
            "data": {
                "vector_count": len(retrieval_results.get("vector_results", [])),
                "bm25_count": len(retrieval_results.get("bm25_results", [])),
                "graph_count": len(retrieval_results.get("graph_results", {}).get("entities", []) if isinstance(retrieval_results.get("graph_results"), dict) else 0),
                "warnings": retrieval_results.get("warnings", []),
            },
        }

        context = retrieval_results.get("combined_context", [])

        # Phase 3: 流式推理（token by token）
        yield {"type": "answer_start"}
        answer_buffer = []
        for token in self.streaming_reasoner.reason_stream(
            query=query,
            context=context,
            analysis=analysis,
        ):
            answer_buffer.append(token)
            yield {"type": "token", "text": token}
        yield {"type": "answer_end"}

        full_answer = "".join(answer_buffer)

        # Phase 4: 校验
        verification_result = self.verification_agent.verify(
            query=query,
            answer=full_answer,
            sources=context,
        )

        sources = [{"content": c.get("content", "")[:200], "source": c.get("source", ""), "type": c.get("type", "")} for c in context[:5]]
        confidence = float(verification_result.get("confidence", 0.0) or 0.0)

        yield {
            "type": "done",
            "data": {
                "sources": sources,
                "confidence": confidence,
                "verification": verification_result,
                "analysis": analysis,
            },
        }


# ─────────────────── 实例化 ───────────────────

def _create_orchestrator():
    """尝试创建 LangGraph 编排器，失败则回退到旧版."""
    try:
        orch = LangGraphOrchestrator()
        logger.info("使用 LangGraph 7 节点编排器")
        return orch
    except Exception:
        logger.exception("LangGraph 编排器初始化失败，回退到 LegacyOrchestrator")
        return LegacyOrchestrator()


orchestrator = _create_orchestrator()
stream_orchestrator = StreamingOrchestrator()
