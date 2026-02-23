"""Tests for Pydantic models: messages, tool calls, config."""

from __future__ import annotations

from wattio.models import (
    DiaryConfig,
    LLMConfig,
    LLMResponse,
    Message,
    Role,
    TokenUsage,
    ToolCall,
    ToolResult,
    WattioConfig,
)


class TestMessageFactory:
    def test_user_message(self) -> None:
        msg = Message.user("hello")
        assert msg.role == Role.USER
        assert msg.content == "hello"
        assert msg.tool_calls is None
        assert msg.tool_result is None

    def test_assistant_message(self) -> None:
        msg = Message.assistant("world")
        assert msg.role == Role.ASSISTANT
        assert msg.content == "world"
        assert msg.tool_calls is None

    def test_system_message(self) -> None:
        msg = Message.system("you are helpful")
        assert msg.role == Role.SYSTEM
        assert msg.content == "you are helpful"

    def test_tool_message(self) -> None:
        result = ToolResult(tool_call_id="tc_1", content="done")
        msg = Message.tool(result)
        assert msg.role == Role.TOOL
        assert msg.content == "done"
        assert msg.tool_result is result

    def test_assistant_with_tool_calls(self) -> None:
        tc = ToolCall(id="tc_1", name="file_reader", arguments={"file_path": "a.txt"})
        msg = Message.assistant("thinking...", tool_calls=[tc])
        assert msg.role == Role.ASSISTANT
        assert msg.content == "thinking..."
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "file_reader"


class TestToolCall:
    def test_default_arguments(self) -> None:
        tc = ToolCall(id="tc_1", name="test_tool")
        assert tc.arguments == {}

    def test_explicit_arguments(self) -> None:
        tc = ToolCall(id="tc_1", name="test_tool", arguments={"key": "val"})
        assert tc.arguments == {"key": "val"}


class TestToolResult:
    def test_default_is_error(self) -> None:
        tr = ToolResult(tool_call_id="tc_1", content="ok")
        assert tr.is_error is False

    def test_explicit_error(self) -> None:
        tr = ToolResult(tool_call_id="tc_1", content="fail", is_error=True)
        assert tr.is_error is True


class TestLLMResponse:
    def test_defaults(self) -> None:
        resp = LLMResponse()
        assert resp.content is None
        assert resp.tool_calls == []
        assert resp.usage.prompt_tokens == 0
        assert resp.usage.completion_tokens == 0
        assert resp.usage.total_tokens == 0

    def test_with_content(self) -> None:
        resp = LLMResponse(content="hello")
        assert resp.content == "hello"
        assert resp.tool_calls == []


class TestTokenUsage:
    def test_defaults(self) -> None:
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_explicit(self) -> None:
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30


class TestWattioConfig:
    def test_defaults(self) -> None:
        config = WattioConfig()
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.llm.temperature == 0.2
        assert config.diary.enabled is True
        assert config.diary.auto_export_docx is False

    def test_llm_fallback_nullable(self) -> None:
        config = LLMConfig()
        assert config.fallback_provider is None
        assert config.fallback_model is None

    def test_llm_fallback_set(self) -> None:
        config = LLMConfig(fallback_provider="anthropic", fallback_model="claude-sonnet-4-5-20250929")
        assert config.fallback_provider == "anthropic"
        assert config.fallback_model == "claude-sonnet-4-5-20250929"

    def test_diary_config_defaults(self) -> None:
        dc = DiaryConfig()
        assert dc.enabled is True
        assert dc.auto_export_docx is False
