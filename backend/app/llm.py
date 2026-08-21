import json
from collections.abc import AsyncIterator

import httpx

from app.errors import ApiError

DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0)

# Failures worth repeating: the connection, not the request.
RETRYABLE_CODES = frozenset({"llm_unreachable", "llm_server_error"})


def llm_http_client(base_url: str, api_key: str | None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )


class LlmClient:
    """Chat completions over the OpenAI protocol.

    Shares no abstraction with the speech-to-text client on purpose: different
    endpoint, different payload, different failure modes. One "AI provider"
    interface covering both would be a generalisation that fits neither.
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def models(self) -> list[str]:
        response = await self._request("GET", "/models")
        return [entry["id"] for entry in response.json().get("data", [])]

    async def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float | None = None,
    ) -> str:
        response = await self._request(
            "POST", "/chat/completions", json=self._body(model, system, user, temperature)
        )
        choices = response.json().get("choices") or []
        if not choices:
            raise ApiError(502, "llm_empty_reply", "The model returned nothing.")
        return (choices[0].get("message", {}).get("content") or "").strip()

    async def stream(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        body = self._body(model, system, user, temperature) | {"stream": True}

        try:
            async with self._http.stream("POST", "/chat/completions", json=body) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise self._failure(response.status_code, response.text)

                async for line in response.aiter_lines():
                    piece = _delta(line)
                    if piece:
                        yield piece
        except httpx.RequestError as cause:
            raise self._unreachable() from cause

    def _body(
        self, model: str, system: str, user: str, temperature: float | None
    ) -> dict[str, object]:
        body: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if temperature is not None:
            body["temperature"] = temperature
        return body

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)  # type: ignore[arg-type]
        except httpx.RequestError as cause:
            raise self._unreachable() from cause

        if response.status_code >= 400:
            raise self._failure(response.status_code, response.text)
        return response

    def _unreachable(self) -> ApiError:
        return ApiError(
            502,
            "llm_unreachable",
            f"Cannot reach the language model server at {self._http.base_url}.",
            base_url=str(self._http.base_url),
        )

    def _failure(self, status: int, detail: str) -> ApiError:
        code = "llm_server_error" if status >= 500 else "llm_rejected_request"
        return ApiError(
            502,
            code,
            f"The language model server answered {status}.",
            status=status,
            detail=detail[:500],
        )


def _delta(line: str) -> str:
    """Pull the text out of one server-sent chunk, ignoring the framing."""
    if not line.startswith("data: "):
        return ""

    payload = line.removeprefix("data: ").strip()
    if not payload or payload == "[DONE]":
        return ""

    try:
        choices = json.loads(payload).get("choices") or []
    except json.JSONDecodeError:
        return ""

    return str(choices[0].get("delta", {}).get("content") or "") if choices else ""
