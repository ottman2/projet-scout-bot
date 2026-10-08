import asyncio
from unittest.mock import AsyncMock

import aiohttp
import pytest

from src.services.faceit_client import (
    FaceitAPIError,
    FaceitAuthenticationError,
    FaceitForbiddenError,
    FaceitInvalidResponseError,
    FaceitNotFoundError,
    FaceitRateLimitError,
    FaceitNetworkError,
    FaceitServerError,
    FaceitClient,
)


class FakeResponse:
    def __init__(self, status, payload=None, headers=None, json_error=None):
        self.status = status
        self.payload = payload
        self.headers = headers or {}
        self.json_error = json_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


@pytest.mark.asyncio
async def test_200_uses_bearer_auth_and_explicit_timeout():
    session = FakeSession([FakeResponse(200, {"items": []})])
    payload = await FaceitClient(session, "secret").get("/players", params={"nickname": "x"})
    assert payload == {"items": []}
    _, kwargs = session.calls[0]
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert isinstance(kwargs["timeout"], aiohttp.ClientTimeout)


@pytest.mark.parametrize("status,error_type", [
    (400, FaceitAPIError),
    (401, FaceitAuthenticationError),
    (403, FaceitForbiddenError),
    (404, FaceitNotFoundError),
    (500, FaceitServerError),
])
@pytest.mark.asyncio
async def test_http_errors_are_classified(status, error_type):
    client = FaceitClient(FakeSession([FakeResponse(status)]), "secret")
    with pytest.raises(error_type):
        await client.get("/teams/x")


@pytest.mark.asyncio
async def test_404_can_be_optional_for_legacy_optional_data():
    result = await FaceitClient(FakeSession([FakeResponse(404)]), "secret").get(
        "/players/x/teams", allow_not_found=True
    )
    assert result == {}


@pytest.mark.asyncio
async def test_rate_limit_retries_and_respects_retry_after(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("src.services.faceit_client.asyncio.sleep", sleep)
    session = FakeSession([
        FakeResponse(429, headers={"Retry-After": "0.25"}),
        FakeResponse(200, {"ok": True}),
    ])
    result = await FaceitClient(session, "secret").get("/teams/x")
    assert result == {"ok": True}
    sleep.assert_awaited_once_with(0.25)


@pytest.mark.asyncio
async def test_rate_limit_has_bounded_retries(monkeypatch):
    monkeypatch.setattr("src.services.faceit_client.asyncio.sleep", AsyncMock())
    session = FakeSession([FakeResponse(429) for _ in range(3)])
    with pytest.raises(FaceitRateLimitError):
        await FaceitClient(session, "secret", max_rate_limit_retries=2).get("/teams/x")
    assert len(session.calls) == 3


@pytest.mark.parametrize("error", [ValueError("bad json"), aiohttp.ContentTypeError(None, ())])
@pytest.mark.asyncio
async def test_invalid_json_is_reported(error):
    client = FaceitClient(FakeSession([FakeResponse(200, json_error=error)]), "secret")
    with pytest.raises(FaceitInvalidResponseError):
        await client.get("/players")


@pytest.mark.asyncio
async def test_timeout_is_reported_as_network_error():
    client = FaceitClient(FakeSession([asyncio.TimeoutError()]), "secret")
    with pytest.raises(FaceitNetworkError):
        await client.get("/players")
