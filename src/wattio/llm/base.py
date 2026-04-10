"""Abstract base class for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable

from wattio.models import LLMResponse, Message


class LLMClient(ABC):
    """Base class for all LLM provider clients."""

    provider_name: str

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Send messages to the LLM and get a response."""

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
        on_text: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Stream a response, calling on_text for each text chunk.

        Default implementation falls back to non-streaming chat.
        """
        return await self.chat(messages, tools, temperature)

    async def close(self) -> None:
        """Clean up resources."""
