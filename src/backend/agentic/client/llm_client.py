import asyncio
import os
from typing import Any, AsyncGenerator
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from backend.agentic.client.response import (
    StreamEventType,
    StreamEvent,
    TextDelta,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
    parse_tool_call_arguments,
)
from backend.agentic.config.config import Config


def _completion_max_tokens() -> int | None:
    """Plafond de sortie du modèle (réponses + arguments d’outils volumineux). 0 / vide = laisser le défaut API."""
    raw = (os.environ.get("AGENTIC_MAX_COMPLETION_TOKENS") or "").strip()
    if not raw:
        return 16_384
    try:
        n = int(raw, 10)
    except ValueError:
        return 16_384
    return None if n <= 0 else min(n, 128_000)


def _stream_idle_timeout_sec() -> float | None:
    """Si > 0 : abandon du flux si aucun chunk reçu pendant N secondes (débloque un SSE bloqué)."""
    raw = (os.environ.get("AGENTIC_STREAM_IDLE_SEC") or "").strip()
    if not raw:
        return None
    try:
        sec = float(raw)
    except ValueError:
        return None
    return sec if sec > 0 else None


def _openrouter_reasoning_extra_body(config: Config) -> dict[str, Any] | None:
    """Contrôle OpenRouter ``reasoning`` (thinking / chaîne de pensée streamée).

    - Par défaut : ``effort=low`` uniquement si ``base_url`` pointe vers OpenRouter ; sinon désactivé
      (évite d’envoyer ``extra_body`` à d’autres backends). Forcer avec ``AGENTIC_REASONING_FORCE=1``.
    - ``AGENTIC_REASONING_EFFORT`` : ``off`` pour désactiver ; ``low``, ``medium``, ``high``, …
    - Ou un entier positif : ``max_tokens`` de réflexion.

    Voir https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
    """
    raw = (os.environ.get("AGENTIC_REASONING_EFFORT") or "").strip().lower()
    base = (config.base_url or "").lower()
    is_openrouter = "openrouter.ai" in base
    forced = os.environ.get("AGENTIC_REASONING_FORCE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not raw:
        raw = "low" if (is_openrouter or forced) else "off"
    if raw in ("off", "false", "0", "disable", "no", ""):
        return None
    if not is_openrouter and not forced:
        return None
    if raw in ("default", "enabled", "on", "true", "1"):
        return {"reasoning": {"enabled": True}}
    if raw in ("xhigh", "high", "medium", "low", "minimal", "none"):
        return {"reasoning": {"effort": raw}}
    try:
        max_tok = int(raw, 10)
        if max_tok > 0:
            return {"reasoning": {"max_tokens": max_tok}}
    except ValueError:
        pass
    return {"reasoning": {"effort": "medium"}}


def _typed_reasoning_chunks_from_delta(delta: Any) -> list[tuple[str, str]]:
    """Extrait (canal, texte) : canal ``planning`` (résumé / plan) ou ``reasoning`` (détail).

    OpenRouter ``reasoning_details`` : ``reasoning.summary`` → planning, ``reasoning.text`` → reasoning.
    Sans détails structurés, ``delta.reasoning`` alimente uniquement ``reasoning``.
    """
    chunks: list[tuple[str, str]] = []
    if delta is None:
        return chunks

    details = getattr(delta, "reasoning_details", None)
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("type") or "").lower()
            text: str | None = None
            channel = "reasoning"
            if typ == "reasoning.summary":
                channel = "planning"
                t = item.get("summary")
                text = t if isinstance(t, str) else None
                if not text:
                    t2 = item.get("text")
                    text = t2 if isinstance(t2, str) else None
            elif typ == "reasoning.text":
                channel = "reasoning"
                t = item.get("text")
                text = t if isinstance(t, str) else None
            else:
                t = item.get("text") or item.get("summary")
                text = t if isinstance(t, str) else None
                if "summary" in typ or "plan" in typ:
                    channel = "planning"
            if text:
                chunks.append((channel, text))
        if chunks:
            return chunks

    for attr in ("reasoning", "reasoning_content"):
        val = getattr(delta, attr, None)
        if isinstance(val, str) and val:
            chunks.append(("reasoning", val))
    return chunks


class LLMClient:
    def __init__(self, config: Config) -> None:
        self._client: AsyncOpenAI | None = None
        self._max_retries: int = 3
        self.config = config

    def get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.config.api_key, 
                base_url=self.config.base_url,  # "https://openrouter.ai/api/v1"
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    def _build_tools(self, tools: list[dict[str, Any]]):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "parameters",
                        {
                            "type": "object",
                            "properties": {},
                        },
                    ),
                },
            }
            for tool in tools
        ]

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> AsyncGenerator[StreamEvent, None]:
        client = self.get_client()

        kwargs: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": stream,
        }
        mt = _completion_max_tokens()
        if mt is not None:
            kwargs["max_tokens"] = mt

        reasoning_body = _openrouter_reasoning_extra_body(self.config)
        if reasoning_body:
            kwargs["extra_body"] = reasoning_body

        if tools:
            kwargs["tools"] = self._build_tools(tools)
            kwargs["tool_choice"] = "auto"

        for attempt in range(self._max_retries + 1):
            try:
                if stream:
                    async for event in self._stream_response(client, kwargs):
                        yield event
                else:
                    event = await self._non_stream_response(client, kwargs)
                    yield event
                return
            except RateLimitError as e:
                if attempt < self._max_retries:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Rate limit exceeded: {e}",
                    )
                    return
            except APIConnectionError as e:
                if attempt < self._max_retries:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Connection error: {e}",
                    )
                    return
            except APIError as e:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    error=f"API error: {e}",
                )
                return

    async def _stream_response(
        self,
        client: AsyncOpenAI,
        kwargs: dict[str, Any],
    ) -> AsyncGenerator[StreamEvent, None]:
        response = await client.chat.completions.create(**kwargs)

        finish_reason: str | None = None
        usage: TokenUsage | None = None
        tool_calls: dict[int, dict[str, Any]] = {}

        idle_sec = _stream_idle_timeout_sec()
        aiter = response.__aiter__()

        async def _next_chunk():
            return await aiter.__anext__()

        while True:
            try:
                if idle_sec is not None:
                    chunk = await asyncio.wait_for(_next_chunk(), timeout=idle_sec)
                else:
                    chunk = await _next_chunk()
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    error=(
                        f"Flux LLM interrompu : aucun chunk reçu pendant {idle_sec:.0f}s "
                        "(AGENTIC_STREAM_IDLE_SEC). Réessayez ou augmentez la valeur."
                    ),
                )
                return

            if hasattr(chunk, "usage") and chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=chunk.usage.prompt_tokens_details.cached_tokens,
                )

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            for channel, fragment in _typed_reasoning_chunks_from_delta(delta):
                if channel == "planning":
                    yield StreamEvent(
                        type=StreamEventType.PLANNING_DELTA,
                        planning_delta=fragment,
                    )
                else:
                    yield StreamEvent(
                        type=StreamEventType.REASONING_DELTA,
                        reasoning_delta=fragment,
                    )

            if delta.content:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=TextDelta(delta.content),
                )

            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    idx = tool_call_delta.index

                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tool_call_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }

                    if tool_call_delta.function:
                        # The model may stream tool call name and arguments across
                        # multiple chunks. We must accumulate arguments for every
                        # delta, not just the first one.
                        if tool_call_delta.function.name:
                            # Only emit TOOL_CALL_START the first time we learn the name.
                            if not tool_calls[idx]["name"]:
                                tool_calls[idx]["name"] = tool_call_delta.function.name
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_CALL_START,
                                    tool_call_delta=ToolCallDelta(
                                        call_id=tool_calls[idx]["id"],
                                        name=tool_call_delta.function.name,
                                    ),
                                )
                            else:
                                tool_calls[idx]["name"] = tool_call_delta.function.name

                        if tool_call_delta.function.arguments:
                            tool_calls[idx]["arguments"] += tool_call_delta.function.arguments

                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_DELTA,
                                tool_call_delta=ToolCallDelta(
                                    call_id=tool_calls[idx]["id"],
                                    name=tool_call_delta.function.name,
                                    arguments_delta=tool_call_delta.function.arguments,
                                ),
                            )

        for idx, tc in tool_calls.items():
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    call_id=tc["id"],
                    name=tc["name"],
                    arguments=parse_tool_call_arguments(tc["arguments"]),
                ),
            )

        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def _non_stream_response(
        self,
        client: AsyncOpenAI,
        kwargs: dict[str, Any],
    ) -> StreamEvent:
        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        text_delta = None
        if message.content:
            text_delta = TextDelta(content=message.content)

        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        call_id=tc.id,
                        name=tc.function.name,
                        arguments=parse_tool_call_arguments(tc.function.arguments),
                    )
                )

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.usage.prompt_tokens_details.cached_tokens,
            )

        return StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            finish_reason=choice.finish_reason,
            usage=usage,
        )
