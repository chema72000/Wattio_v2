"""OpenAI LLM client via raw httpx calls."""

from __future__ import annotations

import json
import os

import httpx

from wattio.llm.base import LLMClient
from wattio.models import LLMResponse, Message, Role, TokenUsage, ToolCall

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIClient(LLMClient):
    provider_name = "openai"

    def __init__(self, model: str = "gpt-4o") -> None:
        self.model = model
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Convert internal messages to OpenAI API format."""
        formatted = []
        for msg in messages:
            if msg.role == Role.TOOL and msg.tool_result:
                formatted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result.tool_call_id,
                    "content": msg.tool_result.content,
                })
            elif msg.role == Role.ASSISTANT and msg.tool_calls:
                entry: dict = {"role": "assistant"}
                if msg.content:
                    entry["content"] = msg.content
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
                formatted.append(entry)
            else:
                formatted.append({
                    "role": msg.role.value,
                    "content": msg.content or "",
                })
        return formatted

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        resp = await self._client.post(OPENAI_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        usage_data = data.get("usage", {})

        tool_calls = []
        if choice.get("tool_calls"):
            for tc in choice["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                ))

        return LLMResponse(
            content=choice.get("content"),
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()
