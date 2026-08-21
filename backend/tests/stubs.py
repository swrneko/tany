import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

WHISPER_VERBOSE_JSON: dict[str, Any] = {
    "task": "transcribe",
    "language": "en",
    "duration": 3.0,
    "text": "Hello there. General Kenobi.",
    "segments": [
        {"id": 0, "start": 0.0, "end": 1.4, "text": " Hello there."},
        {"id": 1, "start": 1.4, "end": 3.0, "text": " General Kenobi."},
    ],
}


@dataclass
class RecordedRequest:
    fields: dict[str, str] = field(default_factory=dict)
    filename: str | None = None
    file_size: int = 0
    authorization: str | None = None


class SttStub:
    """A stand-in for an OpenAI-compatible transcription endpoint.

    A stub rather than a patch, so the multipart body is really encoded by httpx
    and really parsed on the far side. A patch would only prove that we called
    our own function.
    """

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        status: int = 200,
        payload_for: Callable[[int], dict[str, Any]] | None = None,
        status_for: Callable[[int], int] | None = None,
        hold: asyncio.Event | None = None,
    ) -> None:
        fixed = WHISPER_VERBOSE_JSON if payload is None else payload
        self._payload_for = payload_for or (lambda _index: fixed)
        self._status_for = status_for or (lambda _index: status)
        # When set, the handler blocks until released -- lets a test act while a
        # request is genuinely in flight.
        self._hold = hold
        self.received = asyncio.Event()
        self.calls: list[RecordedRequest] = []
        self.app = FastAPI()

        @self.app.post("/v1/audio/transcriptions")
        async def transcriptions(request: Request) -> JSONResponse:
            index = len(self.calls)
            async with request.form() as form:
                upload = form.get("file")
                recorded = RecordedRequest(
                    fields={k: v for k, v in form.items() if isinstance(v, str)},
                    authorization=request.headers.get("Authorization"),
                )
                if upload is not None and not isinstance(upload, str):
                    recorded.filename = upload.filename
                    recorded.file_size = len(await upload.read())
            self.calls.append(recorded)
            self.received.set()
            if self._hold is not None:
                await self._hold.wait()
            return JSONResponse(self._payload_for(index), status_code=self._status_for(index))

    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://stt.test/v1",
            headers={"Authorization": "Bearer sk-test"},
        )


@dataclass
class RecordedCompletion:
    model: str
    system: str
    user: str
    temperature: float | None
    stream: bool


class LlmStub:
    """A stand-in for an OpenAI-compatible chat endpoint.

    Answers both the plain and the streaming shape, because the worker uses the
    stream and any regression in the SSE framing is invisible otherwise.
    """

    def __init__(
        self,
        reply_for: Callable[[int], str] | None = None,
        status: int = 200,
        models: list[str] | None = None,
    ) -> None:
        self._reply_for = reply_for or (lambda index: f"summary {index}")
        self.status = status
        self.calls: list[RecordedCompletion] = []
        self.app = FastAPI()

        @self.app.get("/v1/models")
        async def list_models() -> dict[str, Any]:
            return {"data": [{"id": name, "object": "model"} for name in (models or ["stub-llm"])]}

        @self.app.post("/v1/chat/completions")
        async def completions(request: Request) -> Response:
            body = await request.json()
            index = len(self.calls)
            messages = {message["role"]: message["content"] for message in body["messages"]}
            self.calls.append(
                RecordedCompletion(
                    model=body["model"],
                    system=messages.get("system", ""),
                    user=messages.get("user", ""),
                    temperature=body.get("temperature"),
                    stream=bool(body.get("stream")),
                )
            )

            if self.status >= 400:
                return JSONResponse({"error": "nope"}, status_code=self.status)

            reply = self._reply_for(index)
            if not body.get("stream"):
                return JSONResponse(
                    {"choices": [{"message": {"role": "assistant", "content": reply}}]}
                )

            async def sse() -> AsyncIterator[str]:
                for word in reply.split(" "):
                    piece = json.dumps({"choices": [{"delta": {"content": word + " "}}]})
                    yield f"data: {piece}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(sse(), media_type="text/event-stream")

    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://llm.test/v1",
            headers={"Authorization": "Bearer sk-test"},
        )
