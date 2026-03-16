import ast
import logging
import math
import operator
import uvicorn
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from mcp.server.fastmcp import FastMCP, Context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CUSTOM_HEADER = "x-amzn-bedrock-agentcore-runtime-custom-interceptor-demo"

mcp = FastMCP("interceptors-demo", host="0.0.0.0", port=8000, stateless_http=True)


@mcp.tool()
def hello_world(name: str, ctx: Context) -> dict:
    """Says hello to the given name. Used to demonstrate Gateway interceptors."""
    timestamp = datetime.now(timezone.utc).isoformat()
    interceptor_header = None
    request = ctx.request_context.request
    if request is not None:
        interceptor_header = request.headers.get(CUSTOM_HEADER)
        logger.info("Request headers: %s", dict(request.headers))
        logger.info("Interceptor header: %s", interceptor_header)
    return {
        "greeting": f"Hello, {name}!",
        "timestamp": timestamp,
        "interceptor_header": interceptor_header,
    }


@mcp.tool()
async def fetch_webpage(url: str) -> dict:
    """Fetch the text content of a webpage or HTTP endpoint. Returns status code and body text."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        response = await client.get(url, headers={"User-Agent": "mcp-tool/1.0"})
    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "body": response.text[:8000],  # cap to avoid huge payloads
    }


@mcp.tool()
async def geocode_location(address: str) -> dict:
    """Convert a street address or place name to latitude/longitude coordinates using OpenStreetMap Nominatim."""
    params = {"q": address, "format": "json", "limit": 1}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={"User-Agent": "mcp-tool/1.0"},
        )
    results = response.json()
    if not results:
        return {"error": f"No results found for: {address}"}
    r = results[0]
    return {
        "display_name": r["display_name"],
        "latitude": float(r["lat"]),
        "longitude": float(r["lon"]),
        "type": r.get("type", ""),
        "importance": r.get("importance", 0),
    }


@mcp.tool()
async def reverse_geocode(latitude: float, longitude: float) -> dict:
    """Convert latitude/longitude coordinates to a human-readable address using OpenStreetMap Nominatim."""
    params = {"lat": latitude, "lon": longitude, "format": "json"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://nominatim.openstreetmap.org/reverse",
            params=params,
            headers={"User-Agent": "mcp-tool/1.0"},
        )
    data = response.json()
    if "error" in data:
        return {"error": data["error"]}
    return {
        "display_name": data.get("display_name", ""),
        "address": data.get("address", {}),
        "latitude": latitude,
        "longitude": longitude,
    }


@mcp.tool()
async def get_weather(city: str) -> dict:
    """Get current weather conditions for a city using Open-Meteo (no API key required).
    First geocodes the city name, then fetches weather data."""
    # Step 1: geocode
    geo = await geocode_location(city)
    if "error" in geo:
        return geo
    lat, lon = geo["latitude"], geo["longitude"]

    # Step 2: fetch weather
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
    units = data.get("current_units", {})

    # WMO weather code descriptions (subset)
    wmo_descriptions = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 99: "Thunderstorm with hail",
    }
    code = current.get("weather_code", -1)
    return {
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


@mcp.tool()
async def get_exchange_rate(base_currency: str, target_currency: str) -> dict:
    """Get the current exchange rate between two currencies using the Frankfurter API (ECB data, no API key required).
    Example currencies: USD, EUR, GBP, JPY, CAD, AUD, CHF, CNY."""
    base = base_currency.upper()
    target = target_currency.upper()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://api.frankfurter.app/latest",
            params={"from": base, "to": target},
        )
    if response.status_code != 200:
        return {"error": f"Failed to fetch exchange rate: {response.text}"}
    data = response.json()
    rate = data.get("rates", {}).get(target)
    return {
        "base": base,
        "target": target,
        "rate": rate,
        "date": data.get("date"),
        "description": f"1 {base} = {rate} {target}",
    }


@mcp.tool()
async def get_ip_info(ip_address: str) -> dict:
    """Look up geolocation and network info for an IP address using ip-api.com (free tier, no API key required)."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"http://ip-api.com/json/{ip_address}")
    data = response.json()
    if data.get("status") == "fail":
        return {"error": data.get("message", "Lookup failed"), "ip": ip_address}
    return {
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


@mcp.tool()
async def web_search(query: str) -> dict:
    """Search the web using DuckDuckGo Instant Answers API. Returns an abstract summary and related topics."""
    params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.duckduckgo.com/", params=params)
    data = response.json()
    related = [
        {"text": t.get("Text", ""), "url": t.get("FirstURL", "")}
        for t in data.get("RelatedTopics", [])[:5]
        if isinstance(t, dict) and t.get("Text")
    ]
    return {
        "query": query,
        "abstract": data.get("AbstractText", ""),
        "abstract_source": data.get("AbstractSource", ""),
        "abstract_url": data.get("AbstractURL", ""),
        "answer": data.get("Answer", ""),
        "answer_type": data.get("AnswerType", ""),
        "related_topics": related,
    }


@mcp.tool()
def get_current_time(timezone_name: str = "UTC") -> dict:
    """Get the current date and time in the specified timezone (e.g. 'America/New_York', 'Europe/London', 'UTC').
    Returns ISO 8601 formatted datetime."""
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return {"error": f"Unknown timezone: {timezone_name}. Use IANA names like 'America/New_York'."}
    now = datetime.now(tz)
    return {
        "timezone": timezone_name,
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "utc_offset": now.strftime("%z"),
    }


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
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


@mcp.tool()
async def get_public_holidays(country_code: str, year: int) -> dict:
    """Get public holidays for a country and year using the Nager.Date API (no API key required).
    Use ISO 3166-1 alpha-2 country codes, e.g. 'US', 'GB', 'DE', 'FR', 'JP'."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code.upper()}"
        )
    if response.status_code == 404:
        return {"error": f"No holiday data found for country '{country_code}' in {year}"}
    if response.status_code != 200:
        return {"error": f"API error: {response.status_code}"}
    holidays = response.json()
    return {
        "country": country_code.upper(),
        "year": year,
        "count": len(holidays),
        "holidays": [
            {"date": h["date"], "name": h["localName"], "global": h.get("global", True)}
            for h in holidays
        ],
    }


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


if __name__ == "__main__":
    app = mcp.streamable_http_app()
    app = HeaderEchoMiddleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
