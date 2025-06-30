import pytest
from fastapi import HTTPException
from openbb_ai.models import LlmClientMessage

from allocator_bot.utils import (
    generate_id,
    is_last_message,
    sanitize_message,
    validate_api_key,
)


class TestValidateApiKey:
    """Test API key validation."""

    def test_validate_api_key_success(self):
        """Test successful API key validation."""
        api_key = "test-key"
        token = "Bearer test-key"
        assert validate_api_key(token, api_key) is True

    def test_validate_api_key_success_no_bearer(self):
        """Test successful API key validation without Bearer prefix."""
        api_key = "test-key"
        token = "test-key"
        assert validate_api_key(token, api_key) is True

    def test_validate_api_key_failure(self):
        """Test failed API key validation."""
        api_key = "test-key"
        token = "Bearer wrong-key"
        assert validate_api_key(token, api_key) is False

    def test_validate_api_key_empty_header(self):
        """Test API key validation with empty header."""
        api_key = "test-key"
        token = ""
        assert validate_api_key(token, api_key) is False





class TestSanitizeMessage:
    """Test message sanitization."""

    async def test_sanitize_message_single_braces(self):
        """Test sanitizing single braces."""
        message = "This has {single} braces"
        expected = "This has {{single}} braces"
        assert await sanitize_message(message) == expected

    async def test_sanitize_message_mixed_braces(self):
        """Test sanitizing mixed single and double braces."""
        message = "This has {single} and {{double}} braces"
        expected = "This has {{single}} and {{double}} braces"
        assert await sanitize_message(message) == expected

    async def test_sanitize_message_no_braces(self):
        """Test sanitizing message with no braces."""
        message = "This has no braces"
        expected = "This has no braces"
        assert await sanitize_message(message) == expected

    async def test_sanitize_message_only_double_braces(self):
        """Test sanitizing message with only double braces."""
        message = "This has {{only}} double braces"
        expected = "This has {{only}} double braces"
        assert await sanitize_message(message) == expected


class TestIsLastMessage:
    """Test is_last_message function."""

    async def test_is_last_message_true(self):
        """Test when message is the last human message."""
        messages = [
            LlmClientMessage(role="human", content="First message"),
            LlmClientMessage(role="ai", content="Response"),
            LlmClientMessage(role="human", content="Last message"),
        ]
        target_message = messages[2]  # Last human message
        assert await is_last_message(target_message, messages) is True

    async def test_is_last_message_false(self):
        """Test when message is not the last human message."""
        messages = [
            LlmClientMessage(role="human", content="First message"),
            LlmClientMessage(role="ai", content="Response"),
            LlmClientMessage(role="human", content="Last message"),
        ]
        target_message = messages[0]  # First human message
        assert await is_last_message(target_message, messages) is False

    async def test_is_last_message_no_human_messages(self):
        """Test when there are no human messages."""
        messages = [
            LlmClientMessage(role="ai", content="Response 1"),
            LlmClientMessage(role="ai", content="Response 2"),
        ]
        target_message = LlmClientMessage(role="human", content="Test message")
        assert await is_last_message(target_message, messages) is False

    async def test_is_last_message_only_human_messages(self):
        """Test when all messages are human messages."""
        messages = [
            LlmClientMessage(role="human", content="First message"),
            LlmClientMessage(role="human", content="Second message"),
            LlmClientMessage(role="human", content="Last message"),
        ]
        target_message = messages[2]  # Last message
        assert await is_last_message(target_message, messages) is True

    async def test_is_last_message_single_human_message(self):
        """Test with single human message."""
        messages = [
            LlmClientMessage(role="human", content="Only message"),
        ]
        target_message = messages[0]
        assert await is_last_message(target_message, messages) is True


class TestGenerateId:
    """Test ID generation."""

    async def test_generate_id_default_length(self):
        """Test generating ID with default length."""
        id_str = await generate_id()
        assert len(id_str) == 4  # 2 from timestamp + 2 default
        assert id_str.isalnum()

    async def test_generate_id_custom_length(self):
        """Test generating ID with custom length."""
        id_str = await generate_id(length=3)
        assert len(id_str) == 5  # 2 from timestamp + 3 custom
        assert id_str.isalnum()

    async def test_generate_id_zero_length(self):
        """Test generating ID with zero length suffix."""
        id_str = await generate_id(length=0)
        assert len(id_str) == 2  # Only timestamp part
        assert id_str.isalnum()

    async def test_generate_id_uniqueness(self):
        """Test that generated IDs are reasonably unique."""
        ids = [await generate_id() for _ in range(10)]
        # Should be unique (though theoretically possible to have duplicates)
        assert len(set(ids)) == len(ids)

    async def test_generate_id_character_set(self):
        """Test that generated IDs only contain valid base36 characters."""
        id_str = await generate_id(length=5)
        valid_chars = set("0123456789abcdefghijklmnopqrstuvwxyz")
        assert all(c in valid_chars for c in id_str)
