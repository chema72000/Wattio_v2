"""Tests for the agent loop with a mock LLM."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from wattio.agent import Agent
from wattio.models import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    WattioConfig,
)


def _make_text_response(text: str) -> LLMResponse:
    return LLMResponse(content=text, tool_calls=[], usage=TokenUsage())


def _make_tool_call_response(tool_name: str, args: dict) -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(id="call_1", name=tool_name, arguments=args)],
        usage=TokenUsage(),
    )


@pytest.fixture
def config() -> WattioConfig:
    return WattioConfig()


class TestAgent:
    @pytest.mark.asyncio
    async def test_simple_conversation(self, tmp_project: Path, config: WattioConfig) -> None:
        """Agent returns LLM text response to user."""
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.chat.return_value = _make_text_response("Hello engineer!")
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Hi")

            mock_router.chat.assert_called_once()
            assert len(agent._history) == 2  # user + assistant
            assert agent._history[1].content == "Hello engineer!"

            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_tool_call_flow(self, tmp_project: Path, config: WattioConfig) -> None:
        """Agent calls a tool and then returns final response."""
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            # First call: LLM requests file_reader tool
            # Second call: LLM gives final response
            mock_router.chat.side_effect = [
                _make_tool_call_response(
                    "file_reader",
                    {"file_path": "01 - LTspice/flyback/test.asc"},
                ),
                _make_text_response("I read the schematic, it contains an inductor."),
            ]
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Read my schematic")

            assert mock_router.chat.call_count == 2
            # History: user, assistant(tool_call), tool_result, assistant(text)
            assert len(agent._history) == 4

            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_clear_history(self, tmp_project: Path, config: WattioConfig) -> None:
        """Clearing history resets conversation."""
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.chat.return_value = _make_text_response("Hi")
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Hello")
            assert len(agent._history) == 2

            agent.clear_history()
            assert len(agent._history) == 0

            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_unknown_tool(self, tmp_project: Path, config: WattioConfig) -> None:
        """Agent handles unknown tool call gracefully."""
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.chat.side_effect = [
                _make_tool_call_response("nonexistent_tool", {}),
                _make_text_response("Sorry, that tool is not available."),
            ]
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Do something")

            # Should have error result in history
            tool_msg = agent._history[2]  # user, assistant(tool_call), tool_result
            assert tool_msg.tool_result.is_error
            assert "Unknown tool" in tool_msg.tool_result.content

            await agent.shutdown()
