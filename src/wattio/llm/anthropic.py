"""Anthropic LLM client via raw httpx calls."""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import httpx

from typing import Callable

from wattio.llm.base import LLMClient
from wattio.models import LLMResponse, Message, Role, TokenUsage, ToolCall

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0  # seconds


class AnthropicClient(LLMClient):
    provider_name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-5-20250929") -> None:
        self.model = model
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def _format_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        """Convert internal messages to Anthropic API format.

        Returns (system_prompt, messages).
        """
        system_prompt = None
        formatted = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_prompt = msg.content
            elif msg.role == Role.USER:
                formatted.append({"role": "user", "content": msg.content or ""})
            elif msg.role == Role.ASSISTANT:
                content_blocks: list[dict] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                formatted.append({"role": "assistant", "content": content_blocks})
            elif msg.role == Role.TOOL and msg.tool_result:
                # Build tool_result content — may include image
                tr = msg.tool_result
                if tr.image_base64 and tr.image_media_type:
                    tool_content = [
                        {"type": "text", "text": tr.content},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": tr.image_media_type,
                                "data": tr.image_base64,
                            },
                        },
                    ]
                else:
                    tool_content = tr.content
                tool_block = {
                    "type": "tool_result",
                    "tool_use_id": tr.tool_call_id,
                    "content": tool_content,
                    "is_error": tr.is_error,
                }
                # Merge consecutive tool_result blocks into one user message
                # (Anthropic requires alternating user/assistant roles)
                if formatted and formatted[-1]["role"] == "user" and isinstance(formatted[-1]["content"], list):
                    last_content = formatted[-1]["content"]
                    if last_content and last_content[0].get("type") == "tool_result":
                        formatted[-1]["content"].append(tool_block)
                        continue
                formatted.append({
                    "role": "user",
                    "content": [tool_block],
                })

        return system_prompt, formatted

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI-style tool definitions to Anthropic format."""
        anthropic_tools = []
        for tool in tools:
            func = tool["function"]
            anthropic_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools

    async def _post_with_retry(self, payload: dict) -> dict:
        """POST to Anthropic API with exponential backoff on 429 rate limits."""
        backoff = INITIAL_BACKOFF
        for attempt in range(MAX_RETRIES):
            resp = await self._client.post(ANTHROPIC_API_URL, json=payload)
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                wait = float(retry_after) if retry_after else backoff
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                    backoff *= 2
                    continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()  # Will raise the 429 error on final attempt
        return {}  # unreachable

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload = self._build_payload(messages, tools, temperature)
        data = await self._post_with_retry(payload)

        content_text = None
        tool_calls = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content_text = block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block.get("input", {}),
                ))

        usage_data = data.get("usage", {})
        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            ),
        )

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[dict] | None,
        temperature: float,
    ) -> dict:
        """Build the API request payload."""
        system_prompt, formatted_msgs = self._format_messages(messages)
        payload: dict = {
            "model": self.model,
            "messages": formatted_msgs,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = self._convert_tools(tools)
        return payload

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
        on_text: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Stream a response, calling on_text for each text chunk."""
        payload = self._build_payload(messages, tools, temperature)
        payload["stream"] = True

        backoff = INITIAL_BACKOFF
        resp = None
        for attempt in range(MAX_RETRIES):
            resp = await self._client.send(
                self._client.build_request("POST", ANTHROPIC_API_URL, json=payload),
                stream=True,
            )
            if resp.status_code == 429:
                await resp.aclose()
                retry_after = resp.headers.get("retry-after")
                wait = float(retry_after) if retry_after else backoff
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                    backoff *= 2
                    continue
            break

        assert resp is not None
        if resp.status_code >= 400:
            body = await resp.aread()
            await resp.aclose()
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )

        content_text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        current_tool_id = ""
        current_tool_name = ""
        current_tool_json = ""
        usage = TokenUsage()

        try:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break

                event = json.loads(data_str)
                event_type = event.get("type", "")

                if event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        current_tool_id = block.get("id", "")
                        current_tool_name = block.get("name", "")
                        current_tool_json = ""

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        chunk = delta.get("text", "")
                        content_text_parts.append(chunk)
                        if on_text and chunk:
                            on_text(chunk)
                    elif delta.get("type") == "input_json_delta":
                        current_tool_json += delta.get("partial_json", "")

                elif event_type == "content_block_stop":
                    if current_tool_name:
                        try:
                            args = json.loads(current_tool_json) if current_tool_json else {}
                        except json.JSONDecodeError:
                            args = {}
                        tool_calls.append(ToolCall(
                            id=current_tool_id,
                            name=current_tool_name,
                            arguments=args,
                        ))
                        current_tool_id = ""
                        current_tool_name = ""
                        current_tool_json = ""

                elif event_type == "message_delta":
                    u = event.get("usage", {})
                    usage.completion_tokens = u.get("output_tokens", usage.completion_tokens)

                elif event_type == "message_start":
                    u = event.get("message", {}).get("usage", {})
                    usage.prompt_tokens = u.get("input_tokens", 0)
        finally:
            await resp.aclose()

        usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        content_text = "".join(content_text_parts) or None

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            usage=usage,
        )

    async def close(self) -> None:
        await self._client.aclose()
