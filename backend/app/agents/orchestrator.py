from typing import List, Dict, Any, Generator
from dataclasses import dataclass
from enum import Enum

from app.services.llm_service import llm_service
from app.services.vector_store import vector_store, embedding_service
from app.services.bm25_store import bm25_store
from app.services.kg_service import kg_service
from app.services.evidence_fusion import evidence_fusion_service

class AgentType(Enum):
    QUERY_UNDERSTANDING = "query_understanding"
    RETRIEVAL = "retrieval"
    REASONING = "reasoning"
    VERIFICATION = "verification"
    GENERATION = "generation"

@dataclass
class AgentMessage:
    agent_type: AgentType
    content: Any
    metadata: Dict[str, Any] | None = None

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

        result = llm_service.chat_json(messages)
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
            query_embedding = embedding_service.embed_query(query)
            results["vector_results"] = vector_store.search(query_embedding, top_k=top_k)
        except Exception as e:
            results["warnings"].append("vector_search_failed: " + str(e))

        try:
            results["bm25_results"] = bm25_store.search(query, top_k=top_k)
        except Exception as e:
            results["warnings"].append("bm25_search_failed: " + str(e))

        if entities:
            try:
                results["graph_results"] = kg_service.graph_rag_search(entities, query, depth=2)
            except Exception as e:
                results["warnings"].append("graph_search_failed: " + str(e))

        fused = evidence_fusion_service.fuse(
            vector_results=results["vector_results"],
            bm25_results=results["bm25_results"],
            graph_results=results["graph_results"],
            top_k=top_k,
        )
        results["combined_context"] = evidence_fusion_service.compress_context(fused)
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

        result = llm_service.chat_json(messages)
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
        return llm_service.verify_answer(query, answer, source_texts)

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

class MultiAgentOrchestrator:
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

class StreamingReasoningAgent:
    """流式推理 Agent - 逐 token 输出答案"""

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

        yield from llm_service.chat_stream(messages)


class StreamingOrchestrator:
    """流式编排器 - 前置步骤同步，LLM 生成流式输出"""

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


orchestrator = MultiAgentOrchestrator()
stream_orchestrator = StreamingOrchestrator()
