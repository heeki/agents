"""OAuth2 JWT authentication for the orchestrator agent.

Validates Cognito access tokens and checks for required scopes.
"""

import os

import jwt
from jwt import PyJWKClient
from fastapi import Request
from fastapi.responses import JSONResponse


# Configuration from environment
COGNITO_REGION = os.environ.get("AWS_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
REQUIRED_SCOPE = "a2a-fitness-api/invoke"

# Paths that skip authentication
PUBLIC_PATHS = {"/health", "/ping", "/.well-known/agent.json"}

_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def validate_token(token: str) -> dict:
    """Validate a Cognito access token and return the payload."""
    client = get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer,
        options={"verify_aud": False},
    )
    if payload.get("token_use") != "access":
        raise ValueError("Token is not an access token")
    return payload


def check_scope(payload: dict, required_scope: str) -> bool:
    """Check if the token payload contains the required scope."""
    scopes = payload.get("scope", "").split()
    return required_scope in scopes


async def oauth2_middleware(request: Request, call_next):
    """FastAPI middleware that enforces OAuth2 on protected endpoints."""
    # Skip auth for public paths and GET requests
    if request.url.path in PUBLIC_PATHS or request.method == "GET":
        return await call_next(request)

    # Skip auth if no user pool configured (local dev without Cognito)
    if not COGNITO_USER_POOL_ID:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "Missing or invalid Authorization header"},
        )

    token = auth_header.removeprefix("Bearer ")

    try:
        payload = validate_token(token)
    except Exception as e:
        return JSONResponse(
            status_code=401,
            content={"error": f"Invalid token: {e}"},
        )

    if not check_scope(payload, REQUIRED_SCOPE):
        return JSONResponse(
            status_code=403,
            content={"error": f"Missing required scope: {REQUIRED_SCOPE}"},
        )

    return await call_next(request)
