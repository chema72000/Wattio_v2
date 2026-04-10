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
            mock_router.chat_stream.return_value = _make_text_response("Hello engineer!")
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Hi")

            mock_router.chat_stream.assert_called_once()
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
            mock_router.chat_stream.side_effect = [
                _make_tool_call_response(
                    "file_reader",
                    {"file_path": "01 - LTspice/flyback/test.asc"},
                ),
                _make_text_response("I read the schematic, it contains an inductor."),
            ]
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Read my schematic")

            assert mock_router.chat_stream.call_count == 2
            # History: user, assistant(tool_call), tool_result, assistant(text)
            assert len(agent._history) == 4

            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_clear_history(self, tmp_project: Path, config: WattioConfig) -> None:
        """Clearing history resets conversation."""
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.chat_stream.return_value = _make_text_response("Hi")
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
            mock_router.chat_stream.side_effect = [
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

    @pytest.mark.asyncio
    async def test_max_tool_rounds(self, tmp_project: Path, config: WattioConfig) -> None:
        """Agent stops after MAX_TOOL_ROUNDS consecutive tool calls."""
        from wattio.agent import MAX_TOOL_ROUNDS

        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            # Always return a tool call — never give a final text response
            mock_router.chat_stream.return_value = _make_tool_call_response(
                "file_reader", {"file_path": "01 - LTspice/flyback/test.asc"}
            )
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Loop forever")

            assert mock_router.chat_stream.call_count == MAX_TOOL_ROUNDS
            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_llm_exception_no_crash(self, tmp_project: Path, config: WattioConfig) -> None:
        """LLM error is caught and printed, no crash."""
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.chat_stream.side_effect = RuntimeError("API timeout")
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            # Should not raise
            await agent.handle_user_input("Hello")
            # History should only have the user message
            assert len(agent._history) == 1
            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, tmp_project: Path, config: WattioConfig) -> None:
        """Agent handles multiple tool calls in one response."""
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            multi_tool_response = LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="file_reader", arguments={"file_path": "01 - LTspice/flyback/test.asc"}),
                    ToolCall(id="call_2", name="list_files", arguments={"directory": "."}),
                ],
                usage=TokenUsage(),
            )
            mock_router.chat_stream.side_effect = [
                multi_tool_response,
                _make_text_response("Done reading both."),
            ]
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            await agent.handle_user_input("Read and list")

            # History: user, assistant(2 tool_calls), tool_result, tool_result, assistant(text)
            assert len(agent._history) == 5
            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_diary_disabled(self, tmp_project: Path) -> None:
        """When diary is disabled, no DiaryWriter is created."""
        from wattio.models import DiaryConfig

        config = WattioConfig(diary=DiaryConfig(enabled=False))
        with patch("wattio.agent.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.chat_stream.return_value = _make_text_response("Hi")
            MockRouter.return_value = mock_router

            agent = Agent(config=config, project_dir=tmp_project)
            assert agent._diary_writer is None
            await agent.handle_user_input("Hello")
            # No diary files should be created
            diary_files = list((tmp_project / "wattio" / "diary").glob("*.md"))
            assert len(diary_files) == 0
            await agent.shutdown()


class TestExtractSimulationInfo:
    """Test _extract_simulation_info for different LTspice tools."""

    def test_ltspice_run_param_changes(self) -> None:
        from wattio.agent import _extract_simulation_info

        info = _extract_simulation_info(
            "ltspice_run",
            {"schematic_path": "test.asc", "param_changes": {"R1": 10, "C1": "100n"}},
            "Simulation complete.\nOutput voltage: 12V",
        )
        assert info["schematic"] == "test.asc"
        assert info["params"] == {"R1": "10", "C1": "100n"}
        assert info["summary"] == "Simulation complete."

    def test_ltspice_sweep(self) -> None:
        from wattio.agent import _extract_simulation_info

        info = _extract_simulation_info(
            "ltspice_sweep",
            {"schematic_path": "test.asc", "sweep_param": "fsw", "start": 100000, "stop": 500000, "step": 100000, "measure_trace": "I(L1)"},
            "Sweep complete.",
        )
        assert info["params"] == {"fsw": "100000 → 500000 step 100000"}
        assert info["traces"] == ["I(L1)"]

    def test_ltspice_edit(self) -> None:
        from wattio.agent import _extract_simulation_info

        info = _extract_simulation_info(
            "ltspice_edit",
            {"schematic_path": "test.asc", "action": "set_value", "component": "R1", "value": "20k"},
            "Value set.",
        )
        assert info["params"] == {"component": "R1", "value": "20k"}
        assert "set_value" in info["summary"]

    def test_plot_path_extraction(self) -> None:
        from wattio.agent import _extract_simulation_info

        info = _extract_simulation_info(
            "ltspice_run",
            {"schematic_path": "test.asc"},
            "Simulation complete.\n**Plot saved:** `wattio/results/plot.png`\nDone.",
        )
        assert info["plot_path"] == "wattio/results/plot.png"

    def test_no_plot_path(self) -> None:
        from wattio.agent import _extract_simulation_info

        info = _extract_simulation_info(
            "ltspice_run",
            {"schematic_path": "test.asc"},
            "Simulation complete.",
        )
        assert info["plot_path"] is None
