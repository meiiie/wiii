"""
Weather Service — Wiii's environmental awareness.

Sprint 176: "Wiii Soul AGI" — Phase 1B

Provides current weather and forecast via OpenWeatherMap API (free tier).
Used by the briefing system and heartbeat for contextual awareness.

Design:
    - Async HTTP client (httpx)
    - Feature-gated: living_agent_enable_weather
    - Caching: 30-min TTL to avoid excessive API calls
    - Vietnamese language labels
    - Graceful fallback when API unavailable
"""

import logging
import time
from typing import Optional

import httpx

from app.engine.living_agent.models import WeatherInfo, WeatherForecast

logger = logging.getLogger(__name__)

_OWM_BASE = "https://api.openweathermap.org/data/2.5"
_CACHE_TTL_SECONDS = 1800  # 30 minutes


class WeatherService:
    """Async weather client using OpenWeatherMap API.

    Usage:
        service = WeatherService()
        current = await service.get_current()
        forecast = await service.get_forecast_today()
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_ts: float = 0.0

    async def get_current(self, city: Optional[str] = None) -> Optional[WeatherInfo]:
        """Fetch current weather for the configured city.

        Returns:
            WeatherInfo or None if unavailable.
        """
        from app.core.config import settings

        if not settings.living_agent_enable_weather:
            return None

        api_key = settings.living_agent_weather_api_key
        if not api_key:
            logger.debug("[WEATHER] No API key configured")
            return None

        city = city or settings.living_agent_weather_city

        # Check cache
        cache_key = f"current:{city}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_OWM_BASE}/weather",
                    params={
                        "q": city,
                        "appid": api_key,
                        "units": "metric",
                        "lang": "vi",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            weather = WeatherInfo(
                city=city,
                temp=round(data["main"]["temp"], 1),
                feels_like=round(data["main"]["feels_like"], 1),
                humidity=data["main"]["humidity"],
                description=data["weather"][0]["description"] if data.get("weather") else "",
                icon=data["weather"][0]["icon"] if data.get("weather") else "",
                wind_speed=round(data.get("wind", {}).get("speed", 0), 1),
                rain_mm=data.get("rain", {}).get("1h", 0.0),
            )

            self._set_cached(cache_key, weather)
            logger.info("[WEATHER] Current: %s, %.1f°C, %s", city, weather.temp, weather.description)
            return weather

        except httpx.HTTPStatusError as e:
            logger.warning("[WEATHER] API error %d for %s", e.response.status_code, city)
        except Exception as e:
            logger.warning("[WEATHER] Failed to fetch current weather: %s", e)
        return None

    async def get_forecast_today(self, city: Optional[str] = None) -> list:
        """Fetch 3-hourly forecast for today.

        Returns:
            List of WeatherForecast for remaining hours today.
        """
        from app.core.config import settings

        if not settings.living_agent_enable_weather:
            return []

        api_key = settings.living_agent_weather_api_key
        if not api_key:
            return []

        city = city or settings.living_agent_weather_city

        cache_key = f"forecast:{city}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_OWM_BASE}/forecast",
                    params={
                        "q": city,
                        "appid": api_key,
                        "units": "metric",
                        "lang": "vi",
                        "cnt": 8,  # Next 24 hours (8 × 3h intervals)
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            forecasts = []
            for item in data.get("list", [])[:8]:
                forecasts.append(WeatherForecast(
                    dt_txt=item.get("dt_txt", ""),
                    temp=round(item["main"]["temp"], 1),
                    description=item["weather"][0]["description"] if item.get("weather") else "",
                    rain_probability=round(item.get("pop", 0) * 100),
                    rain_mm=item.get("rain", {}).get("3h", 0.0),
                ))

            self._set_cached(cache_key, forecasts)
            return forecasts

        except Exception as e:
            logger.warning("[WEATHER] Failed to fetch forecast: %s", e)
            return []

    def format_current_vi(self, weather: WeatherInfo) -> str:
        """Format current weather as Vietnamese text for briefing."""
        parts = [f"{weather.city}: {weather.temp}°C"]

        if weather.description:
            parts.append(weather.description)

        if weather.rain_mm > 0:
            parts.append(f"mua {weather.rain_mm:.1f}mm")

        parts.append(f"do am {weather.humidity}%")

        if weather.wind_speed > 5:
            parts.append(f"gio {weather.wind_speed}m/s")

        return ", ".join(parts)

    def should_alert_rain(self, forecasts: list) -> bool:
        """Check if rain is expected in the next few hours."""
        return any(f.rain_probability >= 60 for f in forecasts[:3])

    def _get_cached(self, key: str):
        """Retrieve from cache if within TTL."""
        if key in self._cache:
            ts, value = self._cache[key]
            if time.monotonic() - ts < _CACHE_TTL_SECONDS:
                return value
            del self._cache[key]
        return None

    def _set_cached(self, key: str, value) -> None:
        """Store in cache with current timestamp."""
        self._cache[key] = (time.monotonic(), value)


# =============================================================================
# Singleton
# =============================================================================

_service_instance: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Get the singleton WeatherService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = WeatherService()
    return _service_instance
