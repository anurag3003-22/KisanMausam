"""Open-Meteo weather client: fetch, normalize, cache and serve KisanMausam forecasts.

Open-Meteo is used instead of Google Weather API. The public Forecast API
does not require an API key for non-commercial use and exposes the variables
needed by this application.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from cachetools import LRUCache, TTLCache

from server import advisory as adv
from server import downscale

log = logging.getLogger("kisanmausam.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Primary is Open-Meteo's automatic/best-match forecast.
# A second deterministic model is requested only for the confidence range.
PRIMARY_MODEL = "best_match"
SECOND_MODEL = "ecmwf_ifs025"

TTL_SECONDS = 1800
_fresh = TTLCache(maxsize=4096, ttl=TTL_SECONDS)
_last_good = LRUCache(maxsize=4096)

# Tests can replace this with httpx.MockTransport.
_transport = None


class WeatherUnavailable(Exception):
    pass


def num(v, default=None):
    try:
        f = float(v)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def _r(v, nd=1):
    return None if v is None else round(v, nd)



def _condition_text(code):
    labels = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        56: "Light freezing drizzle", 57: "Dense freezing drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Heavy freezing rain",
        71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
        77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
        82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
    }
    return labels.get(int(code), "Unknown") if code is not None else None


def _client():
    kwargs = {
        "timeout": httpx.Timeout(20.0),
        "headers": {"User-Agent": "KisanMausam/2.0 (SIH Weather Intelligence)"},
    }
    if _transport is not None:
        kwargs["transport"] = _transport
    return httpx.AsyncClient(**kwargs)


async def _open_meteo_get(lat, lng, *, model=None, include_hourly=True):
    """Fetch one normalized Open-Meteo JSON response."""
    params = {
        "latitude": f"{float(lat):.6f}",
        "longitude": f"{float(lng):.6f}",
        "timezone": "auto",
        "forecast_days": 7,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "daily": ",".join([
            "temperature_2m_min",
            "temperature_2m_max",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "weather_code",
        ]),
    }

    if include_hourly:
        params["hourly"] = ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation_probability",
            "precipitation",
            "wind_speed_10m",
            "wind_gusts_10m",
            "weather_code",
            "apparent_temperature",
            "cloud_cover",
            "surface_pressure",
        ])

    if model and model != "best_match":
        params["models"] = model

    async with _client() as client:
        response = await client.get(OPEN_METEO_URL, params=params)

    if response.status_code != 200:
        log.error("Open-Meteo API error: %s %s", response.status_code, response.text[:1000])
        response.raise_for_status()

    return response.json()


def _hourly_humidity_by_date(raw):
    hourly = raw.get("hourly") or {}
    dates = {}
    for i, timestamp in enumerate(hourly.get("time") or []):
        value = num((hourly.get("relative_humidity_2m") or [None] * len(hourly.get("time") or []))[i])
        if value is None:
            continue
        date = str(timestamp)[:10]
        dates.setdefault(date, []).append(value)
    return {d: round(sum(v) / len(v)) for d, v in dates.items() if v}


def normalize_hourly(raw):
    h = raw.get("hourly") or {}
    times = h.get("time") or []
    n = len(times)

    def arr(name, default=None):
        values = h.get(name)
        if values is None:
            return [default] * n
        return values

    result = []
    for i, time in enumerate(times):
        code = arr("weather_code", None)[i]
        result.append({
            "time": time,
            "temp": _r(num(arr("temperature_2m", None)[i])),
            "humidity": _r(num(arr("relative_humidity_2m", None)[i]), 0),
            "rain_prob": _r(num(arr("precipitation_probability", 0)[i], 0), 0),
            "rain": _r(num(arr("precipitation", 0)[i], 0.0)),
            "wind": _r(num(arr("wind_speed_10m", 0)[i], 0.0), 0),
            "gust": _r(num(arr("wind_gusts_10m", 0)[i], 0.0), 0),
            "code": int(code) if code is not None else 3,
            "condition": _condition_text(code),
            "condition_text": _condition_text(code),
            "feels_like": _r(num(arr("apparent_temperature", None)[i])),
            "cloud_cover": _r(num(arr("cloud_cover", None)[i]), 0),
            "pressure": _r(num(arr("surface_pressure", None)[i]), 1),
        })
    return result


def normalize_daily(raw):
    d = raw.get("daily") or {}
    dates = d.get("time") or []
    n = len(dates)
    humidity = _hourly_humidity_by_date(raw)

    def arr(name, default=None):
        values = d.get(name)
        if values is None:
            return [default] * n
        return values

    result = []
    for i, date in enumerate(dates):
        code = arr("weather_code", None)[i]
        result.append({
            "date": date,
            "min_temp": _r(num(arr("temperature_2m_min", None)[i])),
            "max_temp": _r(num(arr("temperature_2m_max", None)[i])),
            "rain": _r(num(arr("precipitation_sum", 0)[i], 0.0)),
            "rain_prob": _r(num(arr("precipitation_probability_max", 0)[i], 0), 0),
            "gust": _r(num(arr("wind_gusts_10m_max", 0)[i], 0.0), 0),
            "wind_max": _r(num(arr("wind_speed_10m_max", 0)[i], 0.0), 0),
            "humidity": humidity.get(date),
            "code": int(code) if code is not None else 3,
            "condition": _condition_text(code),
            "condition_text": _condition_text(code),
        })
    return result


async def _fetch_open_meteo_weather(lat, lng):
    """Fetch the primary Open-Meteo forecast."""

    primary_raw = await _open_meteo_get(
        lat,
        lng,
        model=PRIMARY_MODEL,
        include_hourly=True,
    )

    if isinstance(primary_raw, Exception):
        raise primary_raw

    daily = normalize_daily(primary_raw)
    hourly = normalize_hourly(primary_raw)

    if not daily and not hourly:
        raise ValueError("Open-Meteo returned an empty forecast")

    return {
        "daily": daily,
        "hourly": hourly,
        "second_daily": [],
        "elevation": num(primary_raw.get("elevation")),
        "utc_offset_seconds": int(primary_raw.get("utc_offset_seconds") or 0),
        "timezone": primary_raw.get("timezone"),
    }


async def get_norm(lat, lng, model=None, light=False):
    """Return (normalized_data, stale), using a 30-minute cache and last-good fallback."""
    key = ("open-meteo", round(float(lat), 4), round(float(lng), 4))

    if key in _fresh:
        return _fresh[key], False

    try:
        data = await _fetch_open_meteo_weather(lat, lng)
        if not data["daily"] and not data["hourly"]:
            raise ValueError("empty Open-Meteo forecast")

        _fresh[key] = data
        _last_good[key] = data
        return data, False

    except Exception as exc:
        log.warning("Open-Meteo fetch failed for %s: %s: %s", key, type(exc).__name__, exc)
        if key in _last_good:
            log.warning("Serving last known good Open-Meteo weather for %s", key)
            return _last_good[key], True
        raise WeatherUnavailable(type(exc).__name__) from exc


def _now_slice(pan):
    """Find the current local forecast hour using Open-Meteo's timezone offset."""
    hourly = pan.get("hourly") or []
    if not hourly:
        return 0

    offset = timedelta(seconds=int(pan.get("utc_offset_seconds") or 0))
    now_local = datetime.now(timezone.utc) + offset

    for index, item in enumerate(hourly):
        value = item.get("time")
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                if parsed >= now_local.replace(tzinfo=None):
                    return index
            elif parsed >= now_local:
                return index
        except ValueError:
            continue

    return len(hourly) - 1


async def forecast_bundle(lat, lng, block_lat=None, block_lng=None, crop="general"):
    """Return the complete KisanMausam forecast bundle from Open-Meteo."""

    same_block = (
        block_lat is None
        or block_lng is None
        or (abs(block_lat - lat) < 1e-4 and abs(block_lng - lng) < 1e-4)
    )

    tasks = [get_norm(lat, lng)]
    if not same_block:
        tasks.append(get_norm(block_lat, block_lng))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    if isinstance(results[0], Exception):
        if isinstance(results[0], WeatherUnavailable):
            raise results[0]
        raise WeatherUnavailable(type(results[0]).__name__)

    pan, stale = results[0]

    blk = None
    if not same_block and len(results) > 1 and not isinstance(results[1], Exception):
        blk = results[1][0]

    idx = _now_slice(pan)
    hourly24 = pan["hourly"][idx:idx + 24]
    now = pan["hourly"][idx] if pan["hourly"] and idx < len(pan["hourly"]) else None

    advisories = await adv.build_advisories(pan["daily"], crop, current=now)
    dates3 = [d["date"] for d in pan["daily"][:3]]

    confidence = []
    try:
        confidence = downscale.confidence(pan["daily"], pan.get("second_daily"))
    except Exception as exc:
        log.warning("Confidence calculation skipped: %s", exc)

    try:
        local_adjustment = downscale.local_adjustment(pan, blk)
    except Exception as exc:
        log.warning("Local adjustment failed: %s", exc)
        local_adjustment = None

    return {
        "location": {
            "lat": lat,
            "lng": lng,
            "elevation_m": pan.get("elevation"),
            "timezone": pan.get("timezone"),
        },
        "now": now,
        "daily": pan["daily"],
        "hourly": hourly24,
        "confidence": confidence,
        "local_adjustment": local_adjustment,
        "block_daily": blk["daily"] if blk else [],
        "advisories": advisories,
        "alerts": adv.alerts(advisories, dates3),
        "meta": {
            "source": "Open-Meteo",
            "second_model": SECOND_MODEL if pan.get("second_daily") else None,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stale": stale,
            "crop": crop,
            "point_weather": True,
            "coordinates": {"latitude": lat, "longitude": lng},
        },
    }
