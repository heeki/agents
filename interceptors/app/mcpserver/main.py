import ast
import json
import logging
import math
import operator
import os
import uvicorn
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import boto3
import httpx
import jwt as pyjwt

from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CUSTOM_HEADER = "x-amzn-bedrock-agentcore-runtime-custom-interceptor-demo"
DELEGATED_API_ENDPOINT = os.environ.get("DELEGATED_API_ENDPOINT", "")
CREDENTIAL_PROVIDER_NAME = os.environ.get("CREDENTIAL_PROVIDER_NAME", "")
OBO_SCOPE = os.environ.get("OBO_SCOPE", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

mcp = FastMCP("interceptors-demo", host="0.0.0.0", port=8000, stateless_http=False)


@mcp.tool()
def hello_world(name: str, ctx: Context) -> dict:
    """Says hello to the given name. Used to demonstrate Gateway interceptors."""
    logger.info("[hello_world] name=%s", name)
    timestamp = datetime.now(timezone.utc).isoformat()
    interceptor_header = None
    request = ctx.request_context.request
    if request is not None:
        interceptor_header = request.headers.get(CUSTOM_HEADER)
        logger.info("[hello_world] request headers: %s", dict(request.headers))
    result = {
        "greeting": f"Hello, {name}!",
        "timestamp": timestamp,
        "interceptor_header": interceptor_header,
    }
    logger.info("[hello_world] response: %s", result)
    return result


@mcp.tool()
async def fetch_webpage(url: str) -> dict:
    """Fetch the text content of a webpage or HTTP endpoint. Returns status code and body text."""
    logger.info("[fetch_webpage] url=%s", url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        response = await client.get(url, headers={"User-Agent": "mcp-tool/1.0"})
    result = {
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "body": response.text[:8000],
    }
    logger.info("[fetch_webpage] status=%d, content_type=%s", response.status_code, result["content_type"])
    return result


@mcp.tool()
async def geocode_location(address: str) -> dict:
    """Convert a street address or place name to latitude/longitude coordinates using OpenStreetMap Nominatim."""
    logger.info("[geocode_location] address=%s", address)
    params = {"q": address, "format": "json", "limit": 1}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={"User-Agent": "mcp-tool/1.0"},
        )
    results = response.json()
    if not results:
        result = {"error": f"No results found for: {address}"}
        logger.info("[geocode_location] response: %s", result)
        return result
    r = results[0]
    result = {
        "display_name": r["display_name"],
        "latitude": float(r["lat"]),
        "longitude": float(r["lon"]),
        "type": r.get("type", ""),
        "importance": r.get("importance", 0),
    }
    logger.info("[geocode_location] response: %s", result)
    return result


@mcp.tool()
async def reverse_geocode(latitude: float, longitude: float) -> dict:
    """Convert latitude/longitude coordinates to a human-readable address using OpenStreetMap Nominatim."""
    logger.info("[reverse_geocode] lat=%s, lon=%s", latitude, longitude)
    params = {"lat": latitude, "lon": longitude, "format": "json"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://nominatim.openstreetmap.org/reverse",
            params=params,
            headers={"User-Agent": "mcp-tool/1.0"},
        )
    data = response.json()
    if "error" in data:
        result = {"error": data["error"]}
        logger.info("[reverse_geocode] response: %s", result)
        return result
    result = {
        "display_name": data.get("display_name", ""),
        "address": data.get("address", {}),
        "latitude": latitude,
        "longitude": longitude,
    }
    logger.info("[reverse_geocode] response: %s", result)
    return result


@mcp.tool()
async def get_weather(city: str) -> dict:
    """Get current weather conditions for a city using Open-Meteo (no API key required).
    First geocodes the city name, then fetches weather data."""
    logger.info("[get_weather] city=%s", city)
    geo = await geocode_location(city)
    if "error" in geo:
        return geo
    lat, lon = geo["latitude"], geo["longitude"]

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
    data = response.json()
    current = data.get("current", {})

    wmo_descriptions = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 99: "Thunderstorm with hail",
    }
    code = current.get("weather_code", -1)
    result = {
        "location": geo["display_name"],
        "latitude": lat,
        "longitude": lon,
        "temperature_celsius": current.get("temperature_2m"),
        "feels_like_celsius": current.get("apparent_temperature"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "precipitation_mm": current.get("precipitation"),
        "condition": wmo_descriptions.get(code, f"Weather code {code}"),
        "time": current.get("time"),
    }
    logger.info("[get_weather] response: %s", result)
    return result


@mcp.tool()
async def get_exchange_rate(base_currency: str, target_currency: str) -> dict:
    """Get the current exchange rate between two currencies using the Frankfurter API (ECB data, no API key required).
    Example currencies: USD, EUR, GBP, JPY, CAD, AUD, CHF, CNY."""
    logger.info("[get_exchange_rate] base=%s, target=%s", base_currency, target_currency)
    base = base_currency.upper()
    target = target_currency.upper()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://api.frankfurter.app/latest",
            params={"from": base, "to": target},
        )
    if response.status_code != 200:
        result = {"error": f"Failed to fetch exchange rate: {response.text}"}
        logger.info("[get_exchange_rate] response: %s", result)
        return result
    data = response.json()
    rate = data.get("rates", {}).get(target)
    result = {
        "base": base,
        "target": target,
        "rate": rate,
        "date": data.get("date"),
        "description": f"1 {base} = {rate} {target}",
    }
    logger.info("[get_exchange_rate] response: %s", result)
    return result


@mcp.tool()
async def get_ip_info(ip_address: str) -> dict:
    """Look up geolocation and network info for an IP address using ip-api.com (free tier, no API key required)."""
    logger.info("[get_ip_info] ip_address=%s", ip_address)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"http://ip-api.com/json/{ip_address}")
    data = response.json()
    if data.get("status") == "fail":
        result = {"error": data.get("message", "Lookup failed"), "ip": ip_address}
        logger.info("[get_ip_info] response: %s", result)
        return result
    result = {
        "ip": ip_address,
        "country": data.get("country"),
        "region": data.get("regionName"),
        "city": data.get("city"),
        "zip": data.get("zip"),
        "latitude": data.get("lat"),
        "longitude": data.get("lon"),
        "timezone": data.get("timezone"),
        "isp": data.get("isp"),
        "org": data.get("org"),
    }
    logger.info("[get_ip_info] response: %s", result)
    return result


@mcp.tool()
async def web_search(query: str) -> dict:
    """Search the web using DuckDuckGo Instant Answers API. Returns an abstract summary and related topics."""
    logger.info("[web_search] query=%s", query)
    params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.duckduckgo.com/", params=params)
    data = response.json()
    related = [
        {"text": t.get("Text", ""), "url": t.get("FirstURL", "")}
        for t in data.get("RelatedTopics", [])[:5]
        if isinstance(t, dict) and t.get("Text")
    ]
    result = {
        "query": query,
        "abstract": data.get("AbstractText", ""),
        "abstract_source": data.get("AbstractSource", ""),
        "abstract_url": data.get("AbstractURL", ""),
        "answer": data.get("Answer", ""),
        "answer_type": data.get("AnswerType", ""),
        "related_topics": related,
    }
    logger.info("[web_search] response: %s", result)
    return result


def _get_obo_token(user_token: str) -> str | None:
    """Exchange the incoming user JWT for an OBO token via AgentCore Identity.
    Two-step flow:
    1. GetWorkloadAccessTokenForJWT: user JWT -> AgentCore workload identity token
    2. GetResourceOauth2Token: workload identity token -> IdP access token (with OBO)
    """
    if not CREDENTIAL_PROVIDER_NAME:
        logger.warning("CREDENTIAL_PROVIDER_NAME not configured, skipping OBO exchange")
        return None
    try:
        client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

        # Step 1: Get workload identity token
        logger.info("Step 1: GetWorkloadAccessTokenForJWT (workloadName=%s)", CREDENTIAL_PROVIDER_NAME)
        wit_response = client.get_workload_access_token_for_jwt(
            workloadName=CREDENTIAL_PROVIDER_NAME,
            userToken=user_token,
        )
        workload_token = wit_response.get("workloadAccessToken")
        logger.info("Step 1 succeeded, workload identity token length: %d", len(workload_token) if workload_token else 0)

        # Step 2: Exchange workload identity token for IdP access token via OBO
        logger.info("Step 2: GetResourceOauth2Token (provider=%s, scope=%s, flow=ON_BEHALF_OF_TOKEN_EXCHANGE)",
                    CREDENTIAL_PROVIDER_NAME, OBO_SCOPE)
        obo_response = client.get_resource_oauth2_token(
            workloadIdentityToken=workload_token,
            resourceCredentialProviderName=CREDENTIAL_PROVIDER_NAME,
            scopes=[OBO_SCOPE] if OBO_SCOPE else [],
            oauth2Flow="ON_BEHALF_OF_TOKEN_EXCHANGE",
            customParameters={"requested_token_use": "on_behalf_of"},
        )
        access_token = obo_response.get("accessToken")
        logger.info("Step 2 succeeded, access token length: %d", len(access_token) if access_token else 0)
        return access_token
    except Exception as e:
        logger.error(f"OBO token exchange failed: {e}")
        return None


def _decode_token_claims(token: str) -> dict:
    """Decode JWT claims without verification (for logging/streaming purposes)."""
    try:
        claims = pyjwt.decode(token, options={"verify_signature": False})
        return {k: v for k, v in claims.items() if k not in ("aio", "rh")}
    except Exception as e:
        logger.error(f"Failed to decode token claims: {e}")
        return {}


async def _emit_token_info(ctx: Context, claims: dict) -> None:
    """Emit token_info as a notifications/message via MCP logging."""
    token_info = {
        "token_type": "obo",
        "credential_provider": CREDENTIAL_PROVIDER_NAME,
        "flow": "ON_BEHALF_OF_TOKEN_EXCHANGE",
        "claims": claims,
    }
    await ctx.session.send_log_message(
        level="info",
        data={"token_info": token_info},
        logger="token_info",
    )


@mcp.tool()
async def get_current_time(timezone_name: str, ctx: Context) -> dict:
    """Get the current date and time in the specified timezone (e.g. 'America/New_York', 'Europe/London', 'UTC').
    Returns ISO 8601 formatted datetime. If a credential provider is configured, uses OBO token
    to call the delegated time API and includes token claims in the response."""
    logger.info("[get_current_time] timezone_name=%s, delegated_api=%s, credential_provider=%s",
                timezone_name, DELEGATED_API_ENDPOINT, CREDENTIAL_PROVIDER_NAME)
    if not DELEGATED_API_ENDPOINT or not CREDENTIAL_PROVIDER_NAME:
        try:
            tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            result = {"error": f"Unknown timezone: {timezone_name}. Use IANA names like 'America/New_York'."}
            logger.info("[get_current_time] response: %s", result)
            return result
        now = datetime.now(tz)
        result = {
            "timezone": timezone_name,
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "utc_offset": now.strftime("%z"),
        }
        logger.info("[get_current_time] response: %s", result)
        return result

    # Extract the incoming user token from the request
    user_token = None
    request = ctx.request_context.request
    if request is not None:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            user_token = auth_header[7:]
        logger.info("[get_current_time] has authorization header: %s", bool(auth_header))

    if not user_token:
        result = {"error": "No authorization token found in request. OBO exchange requires a user token."}
        logger.info("[get_current_time] response: %s", result)
        return result

    # Log incoming token claims for debugging
    incoming_claims = _decode_token_claims(user_token)
    logger.info("[get_current_time] incoming token: aud=%s, iss=%s, scp=%s, azp=%s",
                incoming_claims.get("aud"), incoming_claims.get("iss"),
                incoming_claims.get("scp"), incoming_claims.get("azp"))

    # Exchange for OBO token
    logger.info("[get_current_time] exchanging user token for OBO token via %s", CREDENTIAL_PROVIDER_NAME)
    obo_token = _get_obo_token(user_token)
    if not obo_token:
        result = {"error": "OBO token exchange failed. Check credential provider configuration."}
        logger.info("[get_current_time] response: %s", result)
        return result
    logger.info("[get_current_time] OBO token (first 50 chars): %s...", obo_token[:50])

    # Decode and emit token claims
    claims = _decode_token_claims(obo_token)
    logger.info("[get_current_time] OBO token claims: %s", claims)
    await _emit_token_info(ctx, claims)

    # Call the delegated API with the OBO token
    url = f"{DELEGATED_API_ENDPOINT}/time"
    params = {"tz": timezone_name}
    headers = {"Authorization": f"Bearer {obo_token}"}
    logger.info("[get_current_time] calling delegated API: %s?tz=%s", url, timezone_name)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params, headers=headers)

    if response.status_code != 200:
        result = {
            "error": f"Delegated API returned {response.status_code}",
            "detail": response.text,
        }
        logger.info("[get_current_time] response: %s", result)
        return result

    result = response.json()
    logger.info("[get_current_time] response: %s", result)
    return result


# Safe math evaluator — only allows literals and a whitelist of operators/functions
_SAFE_MATH_NODES = {
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
    ast.Mod, ast.Pow, ast.USub, ast.UAdd,
    ast.Call, ast.Name, ast.Load,
}
_SAFE_MATH_NAMES = {
    k: getattr(math, k)
    for k in dir(math)
    if not k.startswith("_") and callable(getattr(math, k))
}
_SAFE_MATH_NAMES.update({"abs": abs, "round": round, "min": min, "max": max})


def _safe_eval(node: ast.AST) -> float:
    if type(node) not in _SAFE_MATH_NODES:
        raise ValueError(f"Disallowed node type: {type(node).__name__}")
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        ops = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }
        return ops[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_safe_eval(node.operand)
        if isinstance(node.op, ast.UAdd):
            return _safe_eval(node.operand)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls allowed")
        fn = _SAFE_MATH_NAMES.get(node.func.id)
        if fn is None:
            raise ValueError(f"Unknown function: {node.func.id}")
        args = [_safe_eval(a) for a in node.args]
        return fn(*args)
    raise ValueError(f"Cannot evaluate node: {ast.dump(node)}")


@mcp.tool()
def calculate_math(expression: str) -> dict:
    """Safely evaluate a mathematical expression. Supports arithmetic operators (+, -, *, /, //, %, **),
    and math functions like sqrt, sin, cos, tan, log, log10, ceil, floor, factorial, etc.
    Example: 'sqrt(144) + 2**8'"""
    logger.info("[calculate_math] expression=%s", expression)
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        val = _safe_eval(tree)
        result = {"expression": expression, "result": val}
    except Exception as e:
        result = {"expression": expression, "error": str(e)}
    logger.info("[calculate_math] response: %s", result)
    return result


@mcp.tool()
async def get_public_holidays(country_code: str, year: int) -> dict:
    """Get public holidays for a country and year using the Nager.Date API (no API key required).
    Use ISO 3166-1 alpha-2 country codes, e.g. 'US', 'GB', 'DE', 'FR', 'JP'."""
    logger.info("[get_public_holidays] country_code=%s, year=%d", country_code, year)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code.upper()}"
        )
    if response.status_code == 404:
        result = {"error": f"No holiday data found for country '{country_code}' in {year}"}
        logger.info("[get_public_holidays] response: %s", result)
        return result
    if response.status_code != 200:
        result = {"error": f"API error: {response.status_code}"}
        logger.info("[get_public_holidays] response: %s", result)
        return result
    holidays = response.json()
    result = {
        "country": country_code.upper(),
        "year": year,
        "count": len(holidays),
        "holidays": [
            {"date": h["date"], "name": h["localName"], "global": h.get("global", True)}
            for h in holidays
        ],
    }
    logger.info("[get_public_holidays] response: count=%d", result["count"])
    return result


@mcp.tool()
async def delete_user_data(user_id: str, reason: str) -> dict:
    """Delete all data associated with a user ID. This is a destructive action.
    HITL Method 1: This tool is gated by an approval policy (pattern: delete_*) via the ApprovalHook.
    The hook intercepts the tool call BEFORE execution and requires human approval.
    Provide the user_id and reason for deletion."""
    logger.info("[delete_user_data] user_id=%s, reason=%s", user_id, reason)
    timestamp = datetime.now(timezone.utc).isoformat()
    result = {
        "status": "deleted",
        "user_id": user_id,
        "reason": reason,
        "deleted_at": timestamp,
        "message": f"All data for user '{user_id}' has been deleted (simulated).",
    }
    logger.info("[delete_user_data] response: %s", result)
    return result


class RevokeConfirmation(BaseModel):
    approved: bool


@mcp.tool()
async def revoke_user_access(user_id: str, service: str, ctx: Context) -> dict:
    """Revoke a user's access to a specific service. This action uses inline MCP elicitation
    to confirm with the operator before proceeding.
    HITL Method 3: This tool uses ctx.elicit() to ask for confirmation mid-execution.
    It does NOT rely on an approval policy or hook — the confirmation is built into the tool itself.
    Provide the user_id and the service name to revoke access from."""
    logger.info("[revoke_user_access] user_id=%s, service=%s", user_id, service)
    elicit_result = await ctx.elicit(
        message=f"ACCESS REVOCATION: Revoke access for user '{user_id}' to service '{service}'.\n\nDo you approve this revocation?",
        schema=RevokeConfirmation,
    )

    if elicit_result.action != "accept" or not elicit_result.data.approved:
        result = {
            "status": "cancelled",
            "user_id": user_id,
            "service": service,
            "message": "Access revocation was denied by operator.",
        }
        logger.info("[revoke_user_access] response: %s", result)
        return result

    timestamp = datetime.now(timezone.utc).isoformat()
    result = {
        "status": "revoked",
        "user_id": user_id,
        "service": service,
        "revoked_at": timestamp,
        "message": f"Access to '{service}' for user '{user_id}' has been revoked (simulated).",
    }
    logger.info("[revoke_user_access] response: %s", result)
    return result


class HeaderEchoMiddleware:
    """ASGI middleware that echoes the interceptor request header back as a response header."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract the custom header from the request
        req_headers = dict(scope.get("headers", []))
        custom_val = req_headers.get(CUSTOM_HEADER.encode(), b"")

        async def send_with_header(message):
            if message["type"] == "http.response.start" and custom_val:
                headers = list(message.get("headers", []))
                headers.append((CUSTOM_HEADER.encode(), custom_val))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)


class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "127.0.0.1" in msg and ("POST /mcp HTTP" in msg or "POST /mcp/ HTTP" in msg):
            return False
        return True


if __name__ == "__main__":
    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
    app = mcp.streamable_http_app()
    app = HeaderEchoMiddleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
