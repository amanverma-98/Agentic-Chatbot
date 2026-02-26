"""Tool definitions for the chatbot."""

import requests
import re
import math
from typing import List, Dict, Any
from langchain_core.tools import tool, BaseTool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_mcp_adapters.client import MultiServerMCPClient
from core.async_utils import run_async


# Built-in tools
search_tool = DuckDuckGoSearchRun(region="us-en")


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA')
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=C9PE94QUEW9VWGFM"
    r = requests.get(url)
    return r.json()


@tool
def get_weather(location: str) -> dict:
    """
    Get current weather information for a specific location.

    Args:
        location: City name (e.g., "New York", "London")

    Returns:
        Dictionary with temperature, weather conditions, and other info
    """
    try:
        # Using Open-Meteo API (free, no key required)
        # First, get coordinates for the location
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
        geo_response = requests.get(geo_url)
        geo_data = geo_response.json()

        if "results" not in geo_data or len(geo_data["results"]) == 0:
            return {"error": f"Location '{location}' not found"}

        result = geo_data["results"][0]
        latitude = result["latitude"]
        longitude = result["longitude"]
        place_name = result.get("name", location)
        country = result.get("country", "")

        # Get weather data
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()

        current = weather_data.get("current", {})
        location_str = f"{place_name}, {country}" if country else place_name

        return {
            "location": location_str,
            "temperature": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "unit": "Celsius"
        }
    except Exception as e:
        return {"error": f"Failed to get weather: {str(e)}"}


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.

    Args:
        expression: Mathematical expression (e.g., "2 + 2", "sqrt(16)", "sin(pi/2)")

    Returns:
        The result of the calculation
    """
    try:
        # Remove spaces for cleaner evaluation
        expression = expression.replace(" ", "")

        # Define safe math functions
        safe_dict = {
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "pi": math.pi,
            "e": math.e,
            "log": math.log,
            "log10": math.log10,
            "abs": abs,
            "round": round,
            "ceil": math.ceil,
            "floor": math.floor,
        }

        # Validate expression contains only safe characters
        if not re.match(r'^[0-9+\-*/()\.\,\s\w]+$', expression):
            return "Error: Expression contains invalid characters"

        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return f"Result: {result}"
    except ZeroDivisionError:
        return "Error: Division by zero"
    except ValueError as e:
        return f"Error: Invalid value - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def extract_url_content(url: str) -> str:
    """
    Fetch and summarize content from a URL.

    Args:
        url: The URL to fetch content from

    Returns:
        The first 1000 characters of the page content
    """
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Remove HTML tags and get text
        import html
        text = response.text
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = ' '.join(text.split())

        return f"Content from {url}:\n\n{text[:1000]}..."
    except requests.exceptions.MissingSchema:
        return "Error: Invalid URL format"
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to the URL"
    except requests.exceptions.Timeout:
        return "Error: Request timed out"
    except Exception as e:
        return f"Error: Failed to fetch URL - {str(e)}"


# MCP Integration
async def _load_mcp_tools_async() -> List[BaseTool]:
    """Load tools from MCP servers (async)."""
    try:
        client = MultiServerMCPClient(
            {
                "expense": {
                    "transport": "streamable_http",
                    "url": "https://splendid-gold-dingo.fastmcp.app/mcp"
                }
            }
        )
        return await client.get_tools()
    except Exception as e:
        print(f"Warning: Could not load MCP tools: {e}")
        return []


def _load_mcp_tools() -> List[BaseTool]:
    """Load tools from MCP servers (sync wrapper)."""
    try:
        return run_async(_load_mcp_tools_async())
    except Exception:
        return []


# Built-in tools list (always available)
_BUILTIN_TOOLS: List[BaseTool] = [
    search_tool, get_stock_price, get_weather, calculator, extract_url_content
]

# MCP tools (loaded once at startup)
_MCP_TOOLS: List[BaseTool] = _load_mcp_tools()

# Combined tools list
_ALL_TOOLS: List[BaseTool] = _BUILTIN_TOOLS + _MCP_TOOLS


def get_all_tools() -> List[BaseTool]:
    """Get all available tools."""
    return _ALL_TOOLS
