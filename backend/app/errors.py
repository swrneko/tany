from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Machine-readable failure.

    The UI is multilingual, so the client renders a translation of `code` and
    interpolates `params`. `message` is an English fallback for consumers that
    have no translation layer of their own (curl, webhooks, scripts).
    """

    def __init__(self, status_code: int, code: str, message: str, **params: Any) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.params = params

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "params": self.params,
                }
            },
        )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return exc.to_response()
