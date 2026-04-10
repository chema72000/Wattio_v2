"""Pydantic models for messages, tool calls, and configuration."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Messages ──────────────────────────────────────────────────────────

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_call_id: str
    content: str
    is_error: bool = False
    image_base64: str | None = None
    image_media_type: str | None = None  # e.g. "image/png", "image/jpeg"
    keep_full: bool = False  # If True, never truncate in history compression


class Message(BaseModel):
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_result: ToolResult | None = None

    @classmethod
    def user(cls, text: str) -> Message:
        return cls(role=Role.USER, content=text)

    @classmethod
    def assistant(cls, text: str, tool_calls: list[ToolCall] | None = None) -> Message:
        return cls(role=Role.ASSISTANT, content=text, tool_calls=tool_calls)

    @classmethod
    def system(cls, text: str) -> Message:
        return cls(role=Role.SYSTEM, content=text)

    @classmethod
    def tool(cls, result: ToolResult) -> Message:
        return cls(role=Role.TOOL, content=result.content, tool_result=result)


# ── LLM Response ─────────────────────────────────────────────────────

class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)


# ── Configuration ────────────────────────────────────────────────────

class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-5-20250929"
    temperature: float = 0.2
    fallback_provider: str | None = None
    fallback_model: str | None = None


class DiaryConfig(BaseModel):
    enabled: bool = True
    auto_export_docx: bool = False


class WattioConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    diary: DiaryConfig = Field(default_factory=DiaryConfig)
