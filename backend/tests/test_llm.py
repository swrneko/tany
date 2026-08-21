import pytest

from app.errors import ApiError
from app.llm import LlmClient
from tests.stubs import LlmStub


async def test_a_completion_comes_back_as_text() -> None:
    stub = LlmStub(reply_for=lambda _index: "Three people argued about a database.")

    async with stub.http_client() as http:
        reply = await LlmClient(http).complete(
            model="stub-llm", system="Be brief.", user="Summarise this.", temperature=0.3
        )

    assert reply == "Three people argued about a database."

    call = stub.calls[0]
    assert call.model == "stub-llm"
    assert call.system == "Be brief."
    assert call.user == "Summarise this."
    assert call.temperature == 0.3
    assert call.stream is False


async def test_a_streamed_completion_arrives_in_pieces() -> None:
    stub = LlmStub(reply_for=lambda _index: "one two three")

    pieces: list[str] = []
    async with stub.http_client() as http:
        async for piece in LlmClient(http).stream(
            model="stub-llm", system="s", user="u", temperature=0.0
        ):
            pieces.append(piece)

    assert len(pieces) > 1, "a stream that arrives all at once is not a stream"
    assert "".join(pieces).strip() == "one two three"
    assert stub.calls[0].stream is True


async def test_a_refused_request_is_reported_with_a_code() -> None:
    stub = LlmStub(status=400)

    async with stub.http_client() as http:
        with pytest.raises(ApiError) as caught:
            await LlmClient(http).complete(model="stub-llm", system="s", user="u")

    assert caught.value.code == "llm_rejected_request"


async def test_a_server_error_is_marked_retryable() -> None:
    """Same split as the STT client: transport trouble is worth repeating, a
    malformed request never is."""
    stub = LlmStub(status=503)

    async with stub.http_client() as http:
        with pytest.raises(ApiError) as caught:
            await LlmClient(http).complete(model="stub-llm", system="s", user="u")

    assert caught.value.code == "llm_server_error"


async def test_the_model_list_is_readable() -> None:
    stub = LlmStub(models=["small", "large"])

    async with stub.http_client() as http:
        assert await LlmClient(http).models() == ["small", "large"]
