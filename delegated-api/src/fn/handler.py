import json
import logging
import os
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID", "")
ENTRA_CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID", "")
ENTRA_ISSUER = os.environ.get("ENTRA_ISSUER", "")
REQUIRED_SCOPE = os.environ.get("REQUIRED_SCOPE", "")
JWKS_URI = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/discovery/v2.0/keys"

VALID_ISSUERS = [
    f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0",
    f"https://sts.windows.net/{ENTRA_TENANT_ID}/",
]
VALID_AUDIENCES = [
    ENTRA_CLIENT_ID,
    f"api://{ENTRA_CLIENT_ID}",
]

_jwks_client = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(JWKS_URI)
    return _jwks_client


def validate_token(token: str) -> dict:
    client = get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=VALID_AUDIENCES,
        issuer=VALID_ISSUERS,
        options={"verify_exp": True},
    )
    scope_name = REQUIRED_SCOPE.split("/")[-1] if "/" in REQUIRED_SCOPE else REQUIRED_SCOPE
    scp = claims.get("scp", "")
    roles = claims.get("roles", [])
    if scope_name in scp.split(" "):
        return claims
    if scope_name in roles:
        return claims
    # client_credentials tokens use 'roles' claim; OBO tokens use 'scp' claim
    raise PermissionError(
        f"Token missing required scope '{scope_name}'. scp='{scp}', roles={roles}"
    )


def get_time_response(tz_name: str) -> dict:
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return {"error": f"Unknown timezone: {tz_name}. Use IANA names like 'America/New_York'."}
    now = datetime.now(tz)
    return {
        "timezone": tz_name,
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "utc_offset": now.strftime("%z"),
    }


def handler(event, context):
    logger.info(json.dumps(event))
    tz_name = event.get("queryStringParameters", {}).get("tz", "UTC") if event.get("queryStringParameters") else "UTC"
    auth_header = event.get("headers", {}).get("authorization", "") or event.get("headers", {}).get("Authorization", "")

    if not auth_header:
        time_result = get_time_response(tz_name)
        body = {
            "authenticated": False,
            "claims": None,
            **time_result,
        }
        status = 200 if "error" not in time_result else 400
        return {"statusCode": status, "body": json.dumps(body), "headers": {"Content-Type": "application/json"}}

    token = auth_header.replace("Bearer ", "").strip()
    try:
        claims = validate_token(token)
    except PermissionError as e:
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "forbidden", "detail": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "unauthorized", "detail": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }

    time_result = get_time_response(tz_name)
    safe_claims = {k: v for k, v in claims.items() if k not in ("aio", "rh")}
    body = {
        "authenticated": True,
        "claims": safe_claims,
        **time_result,
    }
    status = 200 if "error" not in time_result else 400
    return {"statusCode": status, "body": json.dumps(body), "headers": {"Content-Type": "application/json"}}
