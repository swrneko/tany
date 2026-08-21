import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
