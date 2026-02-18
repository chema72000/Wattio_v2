"""Provider selection and fallback logic."""

from __future__ import annotations

from rich.console import Console

from wattio.llm.base import LLMClient
from wattio.models import LLMResponse, Message, WattioConfig

console = Console()

_PROVIDERS = {
    "openai": ("wattio.llm.openai", "OpenAIClient"),
    "anthropic": ("wattio.llm.anthropic", "AnthropicClient"),
}


def _create_client(provider: str, model: str) -> LLMClient:
    """Instantiate an LLM client by provider name."""
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(_PROVIDERS)}")
    module_path, class_name = _PROVIDERS[provider]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(model=model)


class LLMRouter:
    """Routes LLM calls to the configured provider with optional fallback."""

    def __init__(self, config: WattioConfig) -> None:
        self.config = config
        self._primary = _create_client(config.llm.provider, config.llm.model)
        self._fallback: LLMClient | None = None
        if config.llm.fallback_provider and config.llm.fallback_model:
            try:
                self._fallback = _create_client(
                    config.llm.fallback_provider, config.llm.fallback_model
                )
            except ValueError:
                pass  # Fallback not available — that's OK

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        temp = temperature if temperature is not None else self.config.llm.temperature
        try:
            return await self._primary.chat(messages, tools, temp)
        except Exception as e:
            if self._fallback:
                console.print(f"  [yellow]Primary LLM failed ({e}), trying fallback...[/]")
                return await self._fallback.chat(messages, tools, temp)
            raise

    async def close(self) -> None:
        await self._primary.close()
        if self._fallback:
            await self._fallback.close()
