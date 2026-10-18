"""Tests for app.services.llm_service.LLMService"""

import pytest
from unittest.mock import MagicMock, patch
import json


class TestLLMService:
    """Test suite for LLMService operations."""

    def _create_service(self):
        """Create LLMService with mocked OpenAI client."""
        with patch("app.services.llm_service.OpenAI") as MockOpenAI, \
             patch("app.services.llm_service.settings") as mock_settings, \
             patch("app.services.llm_service.os.getenv", return_value="test-key"):
            mock_settings.ZHIPU_API_KEY = "test-key"
            mock_settings.ZHIPU_BASE_URL = "https://api.zhipu.ai/v1"
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_BASE_URL = "https://api.openai.com/v1"
            mock_settings.LLM_MODEL = "gpt-4"
            mock_settings.LLM_TEMPERATURE = 0.7
            mock_settings.LLM_MAX_TOKENS = 1024

            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client

            from app.services.llm_service import LLMService
            service = LLMService()
            return service, mock_client

    def test_chat返回正确文本(self):
        """chat 应返回 LLM 的文本响应。"""
        service, mock_client = self._create_service()
        expected = "Hello, I am a helpful assistant."
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=expected))]
        )

        result = service.chat([{"role": "user", "content": "Hi"}])
        assert result == expected

    def test_chat_json返回解析后的dict(self):
        """chat_json 应返回解析后的字典。"""
        service, mock_client = self._create_service()
        expected = {"key": "value", "number": 42}
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(expected)))]
        )

        result = service.chat_json([{"role": "user", "content": "Give me JSON"}])
        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_extract_entities返回entities和relations(self):
        """extract_entities 应返回实体和关系列表。"""
        service, mock_client = self._create_service()
        response = json.dumps({
            "entities": [
                {"name": "Python", "type": "Technology"},
                {"name": "FastAPI", "type": "Framework"},
            ],
            "relations": [
                {"source": "FastAPI", "target": "Python", "type": "USES"},
            ],
        })
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response))]
        )

        result = service.extract_entities("Python is a language. FastAPI uses Python.")
        assert "entities" in result
        assert "relations" in result
        assert len(result["entities"]) == 2
        assert len(result["relations"]) == 1

    def test_verify_answer返回验证结果(self):
        """verify_answer 应返回验证结果。"""
        service, mock_client = self._create_service()
        response = json.dumps({
            "is_supported": True,
            "hallucination_detected": False,
            "confidence": 0.9,
            "issues": [],
            "source_mapping": {},
        })
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response))]
        )

        result = service.verify_answer(
            question="What is Python?",
            answer="Python is a programming language.",
            sources=["Python is a high-level programming language."],
        )
        assert isinstance(result, dict)
        assert result["is_supported"] is True
        assert result["confidence"] == 0.9

    def test_chat失败时抛异常(self):
        """chat 在 API 调用失败时应抛出异常。"""
        service, mock_client = self._create_service()
        mock_client.chat.completions.create.side_effect = RuntimeError("API Error")

        with pytest.raises(RuntimeError, match="API Error"):
            service.chat([{"role": "user", "content": "Hi"}])
