"""Tests for LLM router with fallback logic — all mock-based."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wattio.models import LLMConfig, LLMResponse, Message, TokenUsage, WattioConfig


def _make_response(text: str) -> LLMResponse:
    return LLMResponse(content=text, tool_calls=[], usage=TokenUsage())


class TestLLMRouter:
    def _make_router(self, *, fallback: bool = False):
        """Create a router with mocked clients."""
        from wattio.llm.router import LLMRouter

        llm_config = LLMConfig(
            provider="openai", model="gpt-4o",
            fallback_provider="anthropic" if fallback else None,
            fallback_model="claude-sonnet-4-5-20250929" if fallback else None,
        )
        config = WattioConfig(llm=llm_config)

        with patch("wattio.llm.router._create_client") as mock_create:
            primary = AsyncMock()
            fb = AsyncMock() if fallback else None
            mock_create.side_effect = [primary] + ([fb] if fallback else [])
            router = LLMRouter(config)
            router._primary = primary
            if fallback:
                router._fallback = fb
        return router

    @pytest.mark.asyncio
    async def test_primary_success(self) -> None:
        router = self._make_router()
        router._primary.chat.return_value = _make_response("Hello")

        resp = await router.chat([Message.user("Hi")])
        assert resp.content == "Hello"
        router._primary.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_primary_fail_fallback_success(self) -> None:
        router = self._make_router(fallback=True)
        router._primary.chat.side_effect = RuntimeError("Primary down")
        router._fallback.chat.return_value = _make_response("Fallback here")

        resp = await router.chat([Message.user("Hi")])
        assert resp.content == "Fallback here"
        router._primary.chat.assert_called_once()
        router._fallback.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_primary_fail_no_fallback_raises(self) -> None:
        router = self._make_router(fallback=False)
        router._primary.chat.side_effect = RuntimeError("Primary down")

        with pytest.raises(RuntimeError, match="Primary down"):
            await router.chat([Message.user("Hi")])

    @pytest.mark.asyncio
    async def test_primary_fail_fallback_also_fails(self) -> None:
        router = self._make_router(fallback=True)
        router._primary.chat.side_effect = RuntimeError("Primary down")
        router._fallback.chat.side_effect = RuntimeError("Fallback also down")

        with pytest.raises(RuntimeError, match="Fallback also down"):
            await router.chat([Message.user("Hi")])

    @pytest.mark.asyncio
    async def test_temperature_override(self) -> None:
        router = self._make_router()
        router._primary.chat.return_value = _make_response("ok")

        await router.chat([Message.user("Hi")], temperature=0.9)
        call_args = router._primary.chat.call_args
        assert call_args[0][2] == 0.9  # third positional arg = temperature

    @pytest.mark.asyncio
    async def test_temperature_default_from_config(self) -> None:
        router = self._make_router()
        router._primary.chat.return_value = _make_response("ok")

        await router.chat([Message.user("Hi")])
        call_args = router._primary.chat.call_args
        assert call_args[0][2] == 0.2  # default from LLMConfig

    @pytest.mark.asyncio
    async def test_close_calls_both(self) -> None:
        router = self._make_router(fallback=True)
        await router.close()
        router._primary.close.assert_called_once()
        router._fallback.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_fallback(self) -> None:
        router = self._make_router(fallback=False)
        await router.close()
        router._primary.close.assert_called_once()


class TestUnknownProvider:
    def test_unknown_provider_raises(self) -> None:
        from wattio.llm.router import _create_client
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            _create_client("nonexistent", "model")
