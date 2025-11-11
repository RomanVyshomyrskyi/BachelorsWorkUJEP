# DataAnalysesMCP/tools.py
import modelcontextprotocol as mcp
import httpx  # You'll need to install this: pip install httpx
import logging

logger = logging.getLogger(__name__)

# --- Helper Functions ---
NWS_API_BASE = "https://api.weather.gov"

async def make_nws_request(url: str) -> dict:
    """A helper to make async web requests."""
    try:
        async with httpx.AsyncClient() as client:
            # The NWS API requires a User-Agent header
            headers = {"User-Agent": "MCP-Example-Client (your@email.com)"}
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"HTTP request failed: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {}

def format_alert(feature: dict) -> str:
    """A helper to format a single alert."""
    props = feature.get("properties", {})
    return f"""
Event: {props.get('event')}
Headline: {props.get('headline')}
Areas: {props.get('areaDesc')}
"""
# --- End Helper Functions ---


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.
    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."
    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)
    if not points_data:
        return "Unable to fetch forecast data for this location."

    forecast_url = points_data.get("properties", {}).get("forecast")
    if not forecast_url:
        return "Could not find forecast URL in points data."

    forecast_data = await make_nws_request(forecast_url)
    if not forecast_data:
        return "Unable to fetch detailed forecast."

    periods = forecast_data.get("properties", {}).get("periods", [])
    forecasts = []
    for period in periods[:5]: # Next 5 periods
        forecast = f"""
{period['name']}:
  Temperature: {period['temperature']}°{period['temperatureUnit']}
  Wind: {period['windSpeed']} {period['windDirection']}
  Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)