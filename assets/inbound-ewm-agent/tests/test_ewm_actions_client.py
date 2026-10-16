"""Unit tests for EwmActionsClient using env-var mode (no Destination service)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _set_env(monkeypatch, add_agent_to_path):
    """Point client at a fake base URL and token via env vars."""
    monkeypatch.setenv("EWM_ACTIONS_URL", "https://fake-ewm.example.com/api/v1")
    monkeypatch.setenv("EWM_ACTIONS_TOKEN", "test-bearer-token")


def _mock_response(data: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_get_sends_correct_headers():
    from ewm_actions_client import EwmActionsClient

    client = EwmActionsClient()
    expected = {"tuNumber": "TU001", "dockDoor": "D01"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=_mock_response(expected))

        result = await client.get("/transport-units/TU001", params={"warehouseNumber": "WH01"})

    assert result == expected
    call_kwargs = mock_http.get.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer test-bearer-token"
    assert call_kwargs[1]["headers"]["Accept"] == "application/json"
    assert call_kwargs[1]["params"] == {"warehouseNumber": "WH01"}


@pytest.mark.asyncio
async def test_get_includes_user_identity_header():
    from ewm_actions_client import EwmActionsClient

    client = EwmActionsClient()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=_mock_response({}))

        await client.get("/deliveries/DEL001", params={}, user_identity="JDOE")

    headers = mock_http.get.call_args[1]["headers"]
    assert headers["X-User-Identity"] == "JDOE"


@pytest.mark.asyncio
async def test_get_omits_user_identity_when_none():
    from ewm_actions_client import EwmActionsClient

    client = EwmActionsClient()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=_mock_response({}))

        await client.get("/deliveries/DEL001")

    headers = mock_http.get.call_args[1]["headers"]
    assert "X-User-Identity" not in headers


@pytest.mark.asyncio
async def test_post_sends_json_body():
    from ewm_actions_client import EwmActionsClient

    client = EwmActionsClient()
    body = {"warehouseNumber": "WH01", "postingDate": "2026-10-15", "operatorId": "JDOE"}
    expected = {"grDocumentNumber": "GR001", "status": "POSTED"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=_mock_response(expected))

        result = await client.post("/deliveries/DEL001/goods-receipt", body=body)

    assert result == expected
    call_kwargs = mock_http.post.call_args
    assert call_kwargs[1]["json"] == body
    assert call_kwargs[1]["headers"]["Content-Type"] == "application/json"
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer test-bearer-token"


@pytest.mark.asyncio
async def test_post_uses_correct_url():
    from ewm_actions_client import EwmActionsClient

    client = EwmActionsClient()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=_mock_response({}))

        await client.post("/exceptions/analyse", body={})

    url = mock_http.post.call_args[0][0]
    assert url == "https://fake-ewm.example.com/api/v1/exceptions/analyse"


@pytest.mark.asyncio
async def test_get_raises_on_http_error():
    import httpx
    from ewm_actions_client import EwmActionsClient

    client = EwmActionsClient()

    error_resp = MagicMock()
    error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=MagicMock()
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=error_resp)

        with pytest.raises(httpx.HTTPStatusError):
            await client.get("/transport-units/MISSING")
