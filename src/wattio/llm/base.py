"""Abstract base class for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod

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

    async def close(self) -> None:
        """Clean up resources."""
