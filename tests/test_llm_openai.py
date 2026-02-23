"""Tests for OpenAI LLM client — all mock-based, no real API calls."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from wattio.models import Message, Role, ToolCall, ToolResult


class TestOpenAIFormatMessages:
    """Test _format_messages conversion to OpenAI API format."""

    def _make_client(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            from wattio.llm.openai import OpenAIClient
            return OpenAIClient(model="gpt-4o")

    def test_system_message(self) -> None:
        client = self._make_client()
        msgs = [Message.system("You are helpful")]
        formatted = client._format_messages(msgs)
        assert formatted == [{"role": "system", "content": "You are helpful"}]

    def test_user_message(self) -> None:
        client = self._make_client()
        msgs = [Message.user("hello")]
        formatted = client._format_messages(msgs)
        assert formatted == [{"role": "user", "content": "hello"}]

    def test_assistant_message(self) -> None:
        client = self._make_client()
        msgs = [Message.assistant("world")]
        formatted = client._format_messages(msgs)
        assert formatted == [{"role": "assistant", "content": "world"}]

    def test_tool_result_message(self) -> None:
        client = self._make_client()
        result = ToolResult(tool_call_id="tc_1", content="file contents")
        msgs = [Message.tool(result)]
        formatted = client._format_messages(msgs)
        assert formatted == [{"role": "tool", "tool_call_id": "tc_1", "content": "file contents"}]

    def test_assistant_with_tool_calls(self) -> None:
        client = self._make_client()
        tc = ToolCall(id="tc_1", name="file_reader", arguments={"file_path": "a.txt"})
        msgs = [Message.assistant("thinking", tool_calls=[tc])]
        formatted = client._format_messages(msgs)
        assert len(formatted) == 1
        entry = formatted[0]
        assert entry["role"] == "assistant"
        assert entry["content"] == "thinking"
        assert len(entry["tool_calls"]) == 1
        assert entry["tool_calls"][0]["id"] == "tc_1"
        assert entry["tool_calls"][0]["type"] == "function"
        assert entry["tool_calls"][0]["function"]["name"] == "file_reader"
        assert json.loads(entry["tool_calls"][0]["function"]["arguments"]) == {"file_path": "a.txt"}


class TestOpenAIChat:
    """Test chat() with mocked httpx responses."""

    def _make_client(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            from wattio.llm.openai import OpenAIClient
            return OpenAIClient(model="gpt-4o")

    @pytest.mark.asyncio
    async def test_text_response(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!", "tool_calls": None}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        client._client.post = AsyncMock(return_value=mock_response)

        resp = await client.chat([Message.user("Hi")])
        assert resp.content == "Hello!"
        assert resp.tool_calls == []
        assert resp.usage.prompt_tokens == 10
        assert resp.usage.completion_tokens == 5
        assert resp.usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_tool_call_response(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "file_reader",
                            "arguments": json.dumps({"file_path": "test.asc"}),
                        },
                    }],
                },
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        client._client.post = AsyncMock(return_value=mock_response)

        resp = await client.chat([Message.user("Read file")])
        assert resp.content is None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].id == "call_abc"
        assert resp.tool_calls[0].name == "file_reader"
        assert resp.tool_calls[0].arguments == {"file_path": "test.asc"}

    @pytest.mark.asyncio
    async def test_tools_none_omits_from_payload(self) -> None:
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }
        client._client.post = AsyncMock(return_value=mock_response)

        await client.chat([Message.user("Hi")], tools=None)
        call_args = client._client.post.call_args
        payload = call_args.kwargs["json"]
        assert "tools" not in payload

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


class TestOpenAIMissingKey:
    def test_missing_api_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            # Ensure the key is not present
            import os
            os.environ.pop("OPENAI_API_KEY", None)
            from wattio.llm.openai import OpenAIClient
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIClient()
