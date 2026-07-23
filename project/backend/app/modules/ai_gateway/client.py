from collections.abc import AsyncIterator
from typing import Any

import httpx


def extract_content(data: dict[str, Any]) -> str:
    """Extract standard or reasoning content from an OpenAI-compatible response."""
    message = data.get("choices", [{}])[0].get("message", {})
    return message.get("content") or message.get("reasoning_content") or ""


def complete(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float | httpx.Timeout,
) -> str:
    response = httpx.post(
        _completion_url(api_url),
        headers=_headers(api_key),
        json=_payload(model, messages, temperature, max_tokens, stream_response=False),
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_content(response.json())


async def complete_async(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float | httpx.Timeout,
) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            _completion_url(api_url),
            headers=_headers(api_key),
            json=_payload(model, messages, temperature, max_tokens, stream_response=False),
        )
    response.raise_for_status()
    return extract_content(response.json())


async def stream(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float | httpx.Timeout,
) -> AsyncIterator[str]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            _completion_url(api_url),
            headers=_headers(api_key),
            json=_payload(model, messages, temperature, max_tokens, stream_response=True),
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_text():
                yield chunk


def _completion_url(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/chat/completions"


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _payload(
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    *,
    stream_response: bool,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream_response,
    }
