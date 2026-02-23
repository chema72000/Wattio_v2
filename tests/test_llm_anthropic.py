"""Tests for Anthropic LLM client — all mock-based, no real API calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from wattio.models import Message, Role, ToolCall, ToolResult


class TestAnthropicFormatMessages:
    """Test _format_messages conversion to Anthropic API format."""

    def _make_client(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from wattio.llm.anthropic import AnthropicClient
            return AnthropicClient(model="claude-sonnet-4-5-20250929")

    def test_system_extracted_separately(self) -> None:
        client = self._make_client()
        msgs = [Message.system("Be helpful"), Message.user("Hi")]
        system, formatted = client._format_messages(msgs)
        assert system == "Be helpful"
        assert len(formatted) == 1
        assert formatted[0] == {"role": "user", "content": "Hi"}

    def test_user_message(self) -> None:
        client = self._make_client()
        msgs = [Message.user("hello")]
        system, formatted = client._format_messages(msgs)
        assert system is None
        assert formatted == [{"role": "user", "content": "hello"}]

    def test_assistant_text_only(self) -> None:
        client = self._make_client()
        msgs = [Message.assistant("world")]
        _, formatted = client._format_messages(msgs)
        assert len(formatted) == 1
        assert formatted[0]["role"] == "assistant"
        assert formatted[0]["content"] == [{"type": "text", "text": "world"}]

    def test_assistant_with_tool_calls(self) -> None:
        client = self._make_client()
        tc = ToolCall(id="tc_1", name="file_reader", arguments={"file_path": "a.txt"})
        msgs = [Message.assistant("thinking", tool_calls=[tc])]
        _, formatted = client._format_messages(msgs)
        content = formatted[0]["content"]
        assert len(content) == 2
        assert content[0] == {"type": "text", "text": "thinking"}
        assert content[1]["type"] == "tool_use"
        assert content[1]["id"] == "tc_1"
        assert content[1]["name"] == "file_reader"
        assert content[1]["input"] == {"file_path": "a.txt"}

    def test_tool_result_message(self) -> None:
        client = self._make_client()
        result = ToolResult(tool_call_id="tc_1", content="file contents", is_error=False)
        msgs = [Message.tool(result)]
        _, formatted = client._format_messages(msgs)
        assert formatted[0]["role"] == "user"
        block = formatted[0]["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "tc_1"
        assert block["content"] == "file contents"
        assert block["is_error"] is False

    def test_tool_result_error(self) -> None:
        client = self._make_client()
        result = ToolResult(tool_call_id="tc_1", content="bad input", is_error=True)
        msgs = [Message.tool(result)]
        _, formatted = client._format_messages(msgs)
        block = formatted[0]["content"][0]
        assert block["is_error"] is True


class TestAnthropicConvertTools:
    def _make_client(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from wattio.llm.anthropic import AnthropicClient
            return AnthropicClient()

    def test_openai_to_anthropic_format(self) -> None:
        client = self._make_client()
        openai_tools = [{
            "type": "function",
            "function": {
                "name": "file_reader",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string"}},
                    "required": ["file_path"],
                },
            },
        }]
        converted = client._convert_tools(openai_tools)
        assert len(converted) == 1
        assert converted[0]["name"] == "file_reader"
        assert converted[0]["description"] == "Read a file"
        assert converted[0]["input_schema"]["type"] == "object"


class TestAnthropicChat:
    def _make_client(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from wattio.llm.anthropic import AnthropicClient
            return AnthropicClient()

    @pytest.mark.asyncio
    async def test_text_response(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hello!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        client._client.post = AsyncMock(return_value=mock_response)

        resp = await client.chat([Message.user("Hi")])
        assert resp.content == "Hello!"
        assert resp.tool_calls == []
        assert resp.usage.prompt_tokens == 10
        assert resp.usage.completion_tokens == 5
        assert resp.usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_tool_use_response(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{
                "type": "tool_use",
                "id": "toolu_abc",
                "name": "file_reader",
                "input": {"file_path": "test.asc"},
            }],
            "usage": {"input_tokens": 20, "output_tokens": 10},
        }
        client._client.post = AsyncMock(return_value=mock_response)

        resp = await client.chat([Message.user("Read file")])
        assert resp.content is None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].id == "toolu_abc"
        assert resp.tool_calls[0].name == "file_reader"
        assert resp.tool_calls[0].arguments == {"file_path": "test.asc"}

    @pytest.mark.asyncio
    async def test_mixed_content(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "Let me read that."},
                {
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "file_reader",
                    "input": {"file_path": "test.asc"},
                },
            ],
            "usage": {"input_tokens": 15, "output_tokens": 8},
        }
        client._client.post = AsyncMock(return_value=mock_response)

        resp = await client.chat([Message.user("Read file")])
        assert resp.content == "Let me read that."
        assert len(resp.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_system_prompt_in_payload(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {},
        }
        client._client.post = AsyncMock(return_value=mock_response)

        msgs = [Message.system("Be helpful"), Message.user("Hi")]
        await client.chat(msgs)
        call_args = client._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["system"] == "Be helpful"

    @pytest.mark.asyncio
    async def test_http_error_raises(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock()
        )
        client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await client.chat([Message.user("Hi")])

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        client = self._make_client()
        client._client.aclose = AsyncMock()
        await client.close()
        client._client.aclose.assert_called_once()


class TestAnthropicMissingKey:
    def test_missing_api_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("ANTHROPIC_API_KEY", None)
            from wattio.llm.anthropic import AnthropicClient
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                AnthropicClient()
