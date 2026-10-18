"""Neutral external provider seam, shared by real requests and mocked evaluations."""

from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import Field

from careflow.chat_contracts import (
    Contract,
    Limits,
    ToolCall,
    ToolDefinition,
    ToolResult,
)


class ProviderError(Exception):
    """Safe marker: never carry transport bodies, configuration or credentials."""


class ProviderReply(Contract):
    stop: Literal["end", "tool", "refused"]
    calls: list[ToolCall] = Field(default_factory=list)
    text: str = ""
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    resolved_model: str | None = None
    sdk_version: str | None = None


class Provider(Protocol):
    async def complete(
        self,
        message: str,
        tools: Sequence[ToolDefinition],
        result: ToolResult | None,
        limits: Limits,
    ) -> ProviderReply: ...


class ScriptedProvider:
    """Only scripts the external boundary; never simulates domain services."""

    def __init__(self, replies: Sequence[ProviderReply | Exception]) -> None:
        self.replies = iter(replies)
        self.results: list[ToolResult] = []

    async def complete(
        self,
        message: str,
        tools: Sequence[ToolDefinition],
        result: ToolResult | None,
        limits: Limits,
    ) -> ProviderReply:
        if result is not None:
            self.results.append(result)
        reply = next(self.replies, ProviderError())
        if isinstance(reply, Exception):
            raise reply
        return reply
