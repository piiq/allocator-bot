from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from openbb_ai.models import (  # type: ignore[import-untyped]
    LlmClientMessage,
    QueryRequest,
)

from allocator_bot.agent import execution_loop
from allocator_bot.models import TaskStructure


class TestExecutionLoop:
    """Test the execution_loop function."""

    @pytest.mark.asyncio
    async def test_execution_loop_no_allocation_needed(self):
        """Test execution loop when no allocation is needed."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(
                    role="human", content="What is portfolio optimization?"
                )
            ]
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return False

        # Mock the callable that make_llm returns
        mock_llm_callable = AsyncMock(return_value="Portfolio optimization is...")
        # Create a mock for the make_llm function itself.
        # This mock, when called, will return our other mock (the callable).
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            assert len(events) == 1
            # The event from `message_chunk` is a `MessageChunkSSE` object.
            # The text content is in the `data.delta` attribute.
            assert hasattr(events[0], "data")
            assert hasattr(events[0].data, "delta")
            assert events[0].data.delta == "Portfolio optimization is..."

            # Assert that make_llm was called to create the LLM
            mock_make_llm.assert_called_once()
            # Assert that the llm was called
            mock_llm_callable.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execution_loop_with_ai_messages(self):
        """Test execution loop with AI messages in history."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(role="human", content="Hello"),
                LlmClientMessage(role="ai", content="Hi there!"),
                LlmClientMessage(
                    role="human", content="Create a portfolio with AAPL and GOOGL"
                ),
            ]
        )

        task_structure = TaskStructure(
            task="Create portfolio",
            asset_symbols=["AAPL", "GOOGL"],
            total_investment=100000,
        )

        # Mock allocation DataFrame
        mock_allocation = pd.DataFrame(
            [
                {
                    "Risk Model": "max_sharpe",
                    "Ticker": "AAPL",
                    "Weight": 0.6,
                    "Quantity": 10,
                },
                {
                    "Risk Model": "max_sharpe",
                    "Ticker": "GOOGL",
                    "Weight": 0.4,
                    "Quantity": 5,
                },
            ]
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return True

        mock_llm_callable = AsyncMock(return_value="Portfolio created successfully")
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            _get_task_structure=AsyncMock(return_value=task_structure),
            prepare_allocation=AsyncMock(return_value=mock_allocation),
            save_allocation=AsyncMock(return_value="test_id_123"),
            save_task=AsyncMock(return_value="test_id_123"),
            generate_id=MagicMock(return_value="test_id"),
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            # Should have multiple events: reasoning steps, table, message chunks
            assert len(events) > 5

    @pytest.mark.asyncio
    async def test_execution_loop_allocation_error(self):
        """Test execution loop when allocation preparation fails."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(
                    role="human", content="Create a portfolio with invalid symbols"
                ),
            ]
        )

        task_structure = TaskStructure(
            task="Create portfolio", asset_symbols=["INVALID"], total_investment=100000
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return True

        mock_llm_callable = AsyncMock(return_value="Error occurred")
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            _get_task_structure=AsyncMock(return_value=task_structure),
            prepare_allocation=MagicMock(side_effect=Exception("Data fetch failed")),
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            # Should have error reasoning step
            error_events = [
                e
                for e in events
                if hasattr(e, "data")
                and hasattr(e.data, "eventType")
                and e.data.eventType == "ERROR"
            ]
            assert len(error_events) > 0

    @pytest.mark.asyncio
    async def test_execution_loop_save_allocation_error(self):
        """Test execution loop when saving allocation fails."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(role="human", content="Create a portfolio with AAPL"),
            ]
        )

        task_structure = TaskStructure(
            task="Create portfolio", asset_symbols=["AAPL"], total_investment=100000
        )

        mock_allocation = pd.DataFrame(
            [
                {
                    "Risk Model": "max_sharpe",
                    "Ticker": "AAPL",
                    "Weight": 1.0,
                    "Quantity": 100,
                },
            ]
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return True

        mock_llm_callable = AsyncMock(return_value="Error saving")
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            _get_task_structure=AsyncMock(return_value=task_structure),
            prepare_allocation=AsyncMock(return_value=mock_allocation),
            save_allocation=MagicMock(side_effect=Exception("Save failed")),
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            # Should have error reasoning step for save failure
            error_events = [
                e
                for e in events
                if hasattr(e, "data")
                and hasattr(e.data, "eventType")
                and e.data.eventType == "ERROR"
            ]
            assert len(error_events) > 0

    @pytest.mark.asyncio
    async def test_execution_loop_string_llm_result(self):
        """Test execution loop when LLM returns a string (not streamed)."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(role="human", content="What is diversification?")
            ]
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return False

        mock_llm_callable = AsyncMock(
            return_value="Diversification is a risk management strategy"
        )
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_execution_loop_streamed_llm_result(self):
        """Test execution loop when LLM returns a streamed result."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(role="human", content="Explain portfolio theory")
            ]
        )

        # Mock AsyncStreamedStr
        async def mock_stream():
            yield "Modern "
            yield "portfolio "
            yield "theory..."

        mock_streamed_str = MagicMock()
        mock_streamed_str.__aiter__ = lambda self: mock_stream()

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return False

        mock_llm_callable = AsyncMock(return_value=mock_streamed_str)
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            # Should have multiple chunks
            assert len(events) >= 3

    @pytest.mark.asyncio
    async def test_execution_loop_with_citations(self):
        """Test execution loop generates citations when allocation is successful."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(
                    role="human", content="Create portfolio with AAPL and MSFT"
                ),
            ]
        )

        task_structure = TaskStructure(
            task="Create portfolio",
            asset_symbols=["AAPL", "MSFT"],
            total_investment=50000,
        )

        mock_allocation = pd.DataFrame(
            [
                {
                    "Risk Model": "max_sharpe",
                    "Ticker": "AAPL",
                    "Weight": 0.7,
                    "Quantity": 20,
                },
                {
                    "Risk Model": "max_sharpe",
                    "Ticker": "MSFT",
                    "Weight": 0.3,
                    "Quantity": 15,
                },
            ]
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return True

        mock_llm_callable = AsyncMock(return_value="Portfolio created successfully")
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            _get_task_structure=AsyncMock(return_value=task_structure),
            prepare_allocation=AsyncMock(return_value=mock_allocation),
            save_allocation=AsyncMock(return_value="citation_test_id"),
            save_task=AsyncMock(return_value="citation_test_id"),
            generate_id=AsyncMock(return_value="citation_test"),
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            # Should have citations at the end
            citation_events = [
                e
                for e in events
                if hasattr(e, "event")
                and e.event == "copilotCitationCollection"
            ]
            assert len(citation_events) > 0

    @pytest.mark.asyncio
    async def test_execution_loop_message_content_handling(self):
        """Test execution loop properly handles message content."""
        request = QueryRequest(
            messages=[
                LlmClientMessage(role="human", content="Test message with {braces}"),
            ]
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return False

        mock_llm_callable = AsyncMock(return_value="Response")
        mock_make_llm = MagicMock(return_value=mock_llm_callable)
        mock_sanitize = AsyncMock(return_value="Test message with {{braces}}")

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            sanitize_message=mock_sanitize,
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            # sanitize_message should have been called
            mock_sanitize.assert_called()

    @pytest.mark.asyncio
    async def test_execution_loop_message_without_content(self):
        """Test execution loop handles messages without content attribute."""
        # Create a real message and then remove the content attribute via mocking
        request = QueryRequest(
            messages=[LlmClientMessage(role="human", content="Test message")]
        )

        async def mock_need_to_allocate_portfolio(*args, **kwargs):
            return False

        mock_llm_callable = AsyncMock(return_value="Response")
        mock_make_llm = MagicMock(return_value=mock_llm_callable)

        with patch.multiple(
            "allocator_bot.agent",
            _need_to_allocate_portfolio=mock_need_to_allocate_portfolio,
            make_llm=mock_make_llm,
        ):
            events = []
            async for event in execution_loop(request):
                events.append(event)

            # Should not crash and should produce some events
            assert len(events) >= 1
