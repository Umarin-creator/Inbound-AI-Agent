"""BTP Destination-backed REST client for the EWM Inbound Actions API.

Resolves the named BTP Destination at call time (no credential caching) so
tokens are always fresh.  In local/test mode, set:
  EWM_ACTIONS_URL        — base URL of the EWM Inbound Actions API
  EWM_ACTIONS_TOKEN      — bearer token to use directly
  EWM_ACTIONS_SAP_CLIENT — SAP client number (e.g. "400"); sent as sap-client query param
to bypass the Destination service entirely.
"""
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ENV_PREFIX = "EWM_ACTIONS"
_DEFAULT_DESTINATION_NAME = os.environ.get("EWM_ACTIONS_DESTINATION_NAME", "EWM_ACTIONS")


def _vcap_services() -> dict:
    raw = os.environ.get("VCAP_SERVICES", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse VCAP_SERVICES — treating as empty")
        return {}


def _find_destination_credentials() -> dict:
    for bindings in _vcap_services().values():
        for binding in bindings:
            tags = binding.get("tags", [])
            if binding.get("label") == "destination" or "destination" in tags:
                return binding["credentials"]
    raise RuntimeError(
        "No BTP Destination service binding found in VCAP_SERVICES. "
        "Bind the 'destination' service instance to this application."
    )


async def _fetch_oauth_token(token_url: str, client_id: str, client_secret: str) -> str:
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            token_url,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _resolve_destination(destination_name: str) -> tuple[str, str, str | None]:
    """Return (base_url, bearer_token, sap_client) for the named BTP Destination.

    Calls the Destination service API to get both the endpoint URL and a
    pre-fetched auth token in a single round trip.
    """
    creds = _find_destination_credentials()

    token_url: str = creds.get("url") or creds.get("tokenurl", "")
    if not token_url.endswith("/oauth/token"):
        token_url = token_url.rstrip("/") + "/oauth/token"

    ds_token = await _fetch_oauth_token(
        token_url, creds["clientid"], creds["clientsecret"]
    )

    ds_uri = creds["uri"].rstrip("/")
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"{ds_uri}/destination-configuration/v1/destinations/{destination_name}",
            headers={"Authorization": f"Bearer {ds_token}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

    dest_config: dict = data.get("destinationConfiguration", {})
    base_url: str = dest_config.get("URL", "").rstrip("/")
    sap_client: str | None = dest_config.get("sap-client") or None

    auth_tokens: list = data.get("authTokens", [])
    if not auth_tokens:
        raise RuntimeError(
            f"Destination '{destination_name}' returned no auth tokens. "
            "Verify the destination authentication type yields tokens "
            "(e.g. OAuth2ClientCredentials)."
        )

    token_entry = auth_tokens[0]
    if token_entry.get("error"):
        raise RuntimeError(
            f"Destination '{destination_name}' auth token fetch failed: "
            f"{token_entry['error']}"
        )

    return base_url, token_entry["value"], sap_client


class EwmActionsClient:
    """REST client for the EWM Inbound Actions API backed by a BTP Destination.

    Resolution strategy (checked in order):
      1. EWM_ACTIONS_URL + EWM_ACTIONS_TOKEN env vars (local/test)
      2. BTP Destination service via VCAP_SERVICES (CF production)

    SAP client number is read from EWM_ACTIONS_SAP_CLIENT env var (local) or
    the destination's sap-client additional property (CF), and sent as
    the sap-client query parameter on every request.
    """

    def __init__(self, destination_name: str = _DEFAULT_DESTINATION_NAME) -> None:
        self._destination_name = destination_name

    async def _base_url_and_token(self) -> tuple[str, str, str | None]:
        """Return (base_url, bearer_token, sap_client)."""
        env_url = os.environ.get(f"{_ENV_PREFIX}_URL")
        env_token = os.environ.get(f"{_ENV_PREFIX}_TOKEN")
        if env_url and env_token:
            sap_client = os.environ.get(f"{_ENV_PREFIX}_SAP_CLIENT") or None
            return env_url.rstrip("/"), env_token, sap_client
        return await _resolve_destination(self._destination_name)

    def _inject_sap_client(
        self, params: dict[str, Any] | None, sap_client: str | None
    ) -> dict[str, Any] | None:
        if not sap_client:
            return params
        result = dict(params) if params else {}
        result.setdefault("sap-client", sap_client)
        return result

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        user_identity: str | None = None,
    ) -> dict[str, Any]:
        base_url, token, sap_client = await self._base_url_and_token()
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if user_identity:
            headers["X-User-Identity"] = user_identity
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{base_url}{path}",
                params=self._inject_sap_client(params, sap_client),
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        user_identity: str | None = None,
    ) -> dict[str, Any]:
        base_url, token, sap_client = await self._base_url_and_token()
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if user_identity:
            headers["X-User-Identity"] = user_identity
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{base_url}{path}",
                params=self._inject_sap_client(None, sap_client),
                json=body,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
