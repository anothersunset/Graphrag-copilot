from typing import List, Dict, Any, Generator
import time
from openai import OpenAI, RateLimitError, APIConnectionError
from config.settings import settings
from app.utils.json_utils import extract_json_object
from app.core.logger import logger


class LLMService:
    def __init__(self):
        api_key = settings.LLM_API_KEY
        if not api_key:
            logger.warning("LLM_API_KEY 未配置，LLM 调用将不可用；请在 .env 中设置 DeepSeek API Key")
            api_key = "not-configured"

        self.client = OpenAI(
            api_key=api_key,
            base_url=settings.LLM_BASE_URL,
            timeout=60.0,
            max_retries=3,
        )
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=kwargs.get("model", self.model),
                    messages=messages,
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    logger.warning("LLM 返回空内容，重试 ({}/{})", attempt+1, max_retries)
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt * 3)
                        continue
                return content
            except (RateLimitError, APIConnectionError, ConnectionError, ConnectionResetError) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt * 5  # 5s, 10s, 20s
                    logger.warning("LLM 限流/连接错误，{}s 后重试 ({}/{}): {}", wait, attempt+1, max_retries, e)
                    time.sleep(wait)
                else:
                    logger.exception("LLM 调用失败（重试耗尽）")
                    raise
            except Exception:
                logger.exception("LLM 调用失败")
                raise

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """流式调用 LLM，逐 token yield"""
        try:
            response = self.client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stream=True,
            )
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.exception("LLM 流式调用失败: {}", type(e).__name__)
            yield "\n\n[生成中断，请稍后重试]"

    def chat_json(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        response = self.chat(messages, **kwargs)
        return extract_json_object(response)

    def extract_entities(self, text: str) -> Dict[str, Any]:
        system_prompt = (
            "你是一个知识图谱抽取专家。请从文本中抽取实体和关系，只输出 JSON。\n\n"
            "输出格式:\n"
            '{"entities": [{"name": "实体名", "type": "Person|Organization|Product|Technology|Concept|Document|Event|Location|Entity", "confidence": 0.0, "properties": {}}], '
            '"relations": [{"source": "源实体", "target": "目标实体", "type": "USES|BELONGS_TO|DEPENDS_ON|RELATED_TO|CAUSES|PART_OF|COMPARES_WITH|CONTAINS|CREATED|WORKS_FOR", "confidence": 0.0, "properties": {}}]}'
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请抽取以下文本中的实体和关系:\n\n" + text[:3000]},
        ]

        result = self.chat_json(messages)
        return {
            "entities": result.get("entities", []) if isinstance(result, dict) else [],
            "relations": result.get("relations", []) if isinstance(result, dict) else [],
        }

    def verify_answer(self, question: str, answer: str, sources: List[str]) -> Dict[str, Any]:
        sources_text = "\n".join(["[" + str(i + 1) + "] " + s for i, s in enumerate(sources)])
        system_prompt = (
            "你是答案验证专家。检查答案是否被来源支持，只输出 JSON:\n"
            '{"is_supported": true, "hallucination_detected": false, "confidence": 0.0, "issues": [], "source_mapping": {}}'
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "问题: " + question + "\n\n答案: " + answer + "\n\n来源:\n" + sources_text},
        ]

        result = self.chat_json(messages)
        return {
            "is_supported": bool(result.get("is_supported", False)),
            "hallucination_detected": bool(result.get("hallucination_detected", False)),
            "confidence": float(result.get("confidence", 0.0) or 0.0),
            "issues": result.get("issues", []),
            "source_mapping": result.get("source_mapping", {}),
        }

llm_service = LLMService()
