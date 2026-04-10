"""OAuth2 client with OIDC well-known discovery for token acquisition."""

import base64
import json
import time
import urllib.parse
import urllib.request
from typing import Optional


class OAuth2Client:
    """Client-credentials OAuth2 client that auto-discovers the token endpoint.

    Reads the OIDC well-known configuration to find the token endpoint, then
    performs the client_credentials grant using HTTP Basic auth.

    Args:
        well_known_url: OIDC discovery document URL, e.g.
            https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration
        client_id: OAuth2 client ID.
        client_secret: OAuth2 client secret.
    """

    def __init__(self, well_known_url: str, client_id: str, client_secret: str) -> None:
        self.well_known_url = well_known_url
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._token_endpoint: Optional[str] = None

    def discover(self) -> dict:
        """Fetch and return the OIDC discovery document."""
        with urllib.request.urlopen(self.well_known_url) as resp:
            return json.loads(resp.read())

    def _token_endpoint_url(self) -> str:
        if not self._token_endpoint:
            self._token_endpoint = self.discover()["token_endpoint"]
        return self._token_endpoint

    def _basic_auth_header(self) -> str:
        return "Basic " + base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

    def get_token(self, scope: str = "", force_refresh: bool = False) -> str:
        """Return a valid access token, refreshing if necessary."""
        if not force_refresh and self._token and time.time() < self._token_expiry - 60:
            return self._token

        payload = self.token_payload(scope=scope)
        self._token = payload["access_token"]
        self._token_expiry = time.time() + payload.get("expires_in", 3600)
        return self._token

    def token_payload(self, scope: str = "") -> dict:
        """Perform the client_credentials grant and return the full token response."""
        params: dict = {"grant_type": "client_credentials"}
        if scope:
            params["scope"] = scope

        req = urllib.request.Request(
            self._token_endpoint_url(),
            data=urllib.parse.urlencode(params).encode(),
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
