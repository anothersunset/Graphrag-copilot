"""Tests for app.services.llm_service.LLMService"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json


class TestLLMService:
    """Test suite for LLMService operations."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        with patch("app.services.llm_service.OpenAI") as MockOpenAI:
            self.mock_client = MagicMock()
            MockOpenAI.return_value = self.mock_client
            
            from app.services.llm_service import LLMService
            self.service = LLMService()

    def test_chat返回正确文本(self):
        """Test that chat returns the expected text response."""
        # Arrange
        expected_text = "Hello, I am a helpful assistant."
        self.mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=expected_text))]
        )

        # Act
        result = self.service.chat([{"role": "user", "content": "Hi"}])

        # Assert
        assert result == expected_text
        self.mock_client.chat.completions.create.assert_called_once()

    def test_chat_json返回解析后的dict(self):
        """Test that chat_json returns a parsed dictionary."""
        # Arrange
        expected_dict = {"key": "value", "number": 42}
        json_str = json.dumps(expected_dict)
        self.mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json_str))]
        )

        # Act
        result = self.service.chat_json([{"role": "user", "content": "Give me JSON"}])

        # Assert
        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_extract_entities返回entities和relations(self):
        """Test that extract_entities returns entities and relations."""
        # Arrange
        entities_response = json.dumps({
            "entities": [
                {"name": "Python", "type": "Technology"},
                {"name": "FastAPI", "type": "Framework"},
            ],
            "relations": [
                {"source": "FastAPI", "target": "Python", "relation": "built_with"},
            ],
        })
        self.mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=entities_response))]
        )

        # Act
        result = self.service.extract_entities("Python is a language. FastAPI is built with Python.")

        # Assert
        assert isinstance(result, dict)
        assert "entities" in result
        assert "relations" in result
        assert len(result["entities"]) == 2
        assert len(result["relations"]) == 1

    def test_verify_answer返回验证结果(self):
        """Test that verify_answer returns a verification result."""
        # Arrange
        verification_response = json.dumps({
            "is_consistent": True,
            "confidence": 0.9,
            "issues": [],
            "explanation": "The answer is well-supported by sources.",
        })
        self.mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=verification_response))]
        )

        # Act
        result = self.service.verify_answer(
            question="What is Python?",
            answer="Python is a programming language.",
            sources=["Python is a high-level programming language."],
        )

        # Assert
        assert isinstance(result, dict)
        assert "is_consistent" in result
        assert "confidence" in result
        assert result["is_consistent"] is True
        assert result["confidence"] == 0.9

    def test_chat失败时抛异常(self):
        """Test that chat raises an exception when the API call fails."""
        # Arrange
        self.mock_client.chat.completions.create.side_effect = RuntimeError("API Error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="API Error"):
            self.service.chat([{"role": "user", "content": "Hi"}])
