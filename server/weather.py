"""Google Weather API client: fetch, validate, normalize and cache forecasts."""

import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime, timezone

import httpx
from cachetools import LRUCache, TTLCache
from dotenv import load_dotenv


# Always load .env from the server directory,
# regardless of where Uvicorn is started from.
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)

from server import advisory as adv
from server import downscale


log = logging.getLogger("kisanmausam.weather")


# ============================================================
# GOOGLE WEATHER API
# ============================================================

GOOGLE_HOURLY_URL = (
    "https://weather.googleapis.com/v1/forecast/hours:lookup"
)

GOOGLE_DAILY_URL = (
    "https://weather.googleapis.com/v1/forecast/days:lookup"
)

GOOGLE_API_KEY = os.getenv("GOOGLE_WEATHER_API_KEY")
if GOOGLE_API_KEY:
    log.info(
        "Google Weather API key loaded successfully from %s",
        ENV_FILE
    )
else:
    log.error(
        "Google Weather API key NOT FOUND. Expected .env at %s",
        ENV_FILE
    )


# ============================================================
# CACHE
# ============================================================

TTL_SECONDS = 1800

_fresh = TTLCache(
    maxsize=4096,
    ttl=TTL_SECONDS
)

_last_good = LRUCache(
    maxsize=4096
)


class WeatherUnavailable(Exception):
    pass


# ============================================================
# HELPERS
# ============================================================

def num(v, default=None):
    try:
        f = float(v)

        if f != f:
            return default

        return f

    except (TypeError, ValueError):
        return default


def _r(v, nd=1):
    return None if v is None else round(v, nd)


# ============================================================
# GOOGLE CONDITION -> EXISTING WMO STYLE CODE
#
# Frontend already understands weather_code.
# So we normalize Google conditions into familiar codes.
# ============================================================

def google_condition_to_code(condition):
    condition = str(condition or "").upper()

    mapping = {

        # Clear / cloudy
        "CLEAR": 0,
        "MOSTLY_CLEAR": 1,
        "PARTLY_CLOUDY": 2,
        "MOSTLY_CLOUDY": 3,
        "CLOUDY": 3,

        # Fog
        "FOG": 45,

        # Rain
        "LIGHT_RAIN": 61,
        "MODERATE_RAIN": 63,
        "HEAVY_RAIN": 65,

        "RAIN": 63,

        "RAIN_SHOWERS": 80,
        "SCATTERED_SHOWERS": 80,
        "HEAVY_SHOWERS": 82,

        # Thunderstorms
        "THUNDERSTORM": 95,
        "SEVERE_THUNDERSTORM": 96,

        "LIGHT_THUNDERSTORM_RAIN": 95,
        "HEAVY_THUNDERSTORM_RAIN": 96,
        "THUNDERSHOWER": 95,
        "SCATTERED_THUNDERSTORMS": 95,

        # Snow
        "LIGHT_SNOW": 71,
        "MODERATE_SNOW": 73,
        "HEAVY_SNOW": 75,

        # Mixed
        "RAIN_AND_SNOW": 67,
        "SLEET": 67,

        # Hail
        "HAIL": 96,

        # Wind + rain
        "WIND_AND_RAIN": 63,
    }

    return mapping.get(condition, 3)


# ============================================================
# GOOGLE API REQUEST
# ============================================================

async def _google_get(url, lat, lng, params=None):
    """
    Call Google Weather API for an exact latitude/longitude.
    """

    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_WEATHER_API_KEY is not configured"
        )

    query = {
        "key": GOOGLE_API_KEY,

        "location.latitude": f"{float(lat):.6f}",
        "location.longitude": f"{float(lng):.6f}",

        "unitsSystem": "METRIC",
    }

    if params:
        query.update(params)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        headers={
            "User-Agent": (
                "KisanMausam/2.0 "
                "(SIH Weather Intelligence)"
            )
        }
    ) as client:

        response = await client.get(
            url,
            params=query
        )

        if response.status_code != 200:

            log.error(
                "Google Weather API error: %s %s",
                response.status_code,
                response.text[:1000]
            )

        response.raise_for_status()

        return response.json()


# ============================================================
# HOURLY NORMALIZATION
# ============================================================

def normalize_hourly(raw):
    """
    Convert Google hourly response into existing
    KisanMausam internal format.
    """

    result = []

    forecast_hours = raw.get(
        "forecastHours",
        []
    )

    for item in forecast_hours:

        interval = item.get(
            "interval",
            {}
        )

        time = interval.get(
            "startTime"
        )

        condition = (
            item.get(
                "weatherCondition",
                {}
            )
            .get(
                "type",
                "CLOUDY"
            )
        )

        temperature = item.get(
            "temperature",
            {}
        )

        precipitation = item.get(
            "precipitation",
            {}
        )

        probability = precipitation.get(
            "probability",
            {}
        )

        qpf = precipitation.get(
            "qpf",
            {}
        )

        wind = item.get(
            "wind",
            {}
        )

        wind_speed = wind.get(
            "speed",
            {}
        )

        wind_gust = wind.get(
            "gust",
            {}
        )

        wind_direction = wind.get(
            "direction",
            {}
        )

        result.append({

            "time": time,

            "temp": _r(
                num(
                    temperature.get(
                        "degrees"
                    )
                )
            ),

            "humidity": _r(
                num(
                    item.get(
                        "relativeHumidity"
                    )
                ),
                0
            ),

            "rain_prob": _r(
                num(
                    probability.get(
                        "percent"
                    ),
                    0
                ),
                0
            ),

            "rain": _r(
                num(
                    qpf.get(
                        "quantity"
                    ),
                    0.0
                )
            ),

            "wind": _r(
                num(
                    wind_speed.get(
                        "value"
                    ),
                    0.0
                ),
                0
            ),

            "gust": _r(
                num(
                    wind_gust.get(
                        "value"
                    ),
                    0.0
                ),
                0
            ),

            "wind_direction": _r(
                num(
                    wind_direction.get(
                        "degrees"
                    )
                ),
                0
            ),

            "wind_direction_cardinal": (
                wind_direction.get(
                    "cardinal"
                )
            ),

            "code": google_condition_to_code(
                condition
            ),

            "condition": condition,

            "condition_text": (
                item.get(
                    "weatherCondition",
                    {}
                )
                .get(
                    "description",
                    {}
                )
                .get(
                    "text"
                )
            ),

            "feels_like": _r(
                num(
                    item.get(
                        "feelsLikeTemperature",
                        {}
                    )
                    .get(
                        "degrees"
                    )
                )
            ),

            "uv_index": _r(
                num(
                    item.get(
                        "uvIndex"
                    )
                ),
                0
            ),

            "cloud_cover": _r(
                num(
                    item.get(
                        "cloudCover"
                    )
                ),
                0
            ),

            "pressure": _r(
                num(
                    item.get(
                        "airPressure",
                        {}
                    )
                    .get(
                        "meanSeaLevelMillibars"
                    )
                ),
                1
            ),
        })

    return result


# ============================================================
# DAILY NORMALIZATION
# ============================================================

def normalize_daily(raw):
    """
    Convert Google daily forecast into the existing
    KisanMausam daily format.
    """

    result = []

    forecast_days = raw.get(
        "forecastDays",
        []
    )

    for day in forecast_days:

        display_date = day.get(
            "displayDate",
            {}
        )

        year = display_date.get(
            "year"
        )

        month = display_date.get(
            "month"
        )

        date_value = display_date.get(
            "day"
        )

        if not all(
            value is not None
            for value in [
                year,
                month,
                date_value
            ]
        ):
            continue

        date = (
            f"{int(year):04d}-"
            f"{int(month):02d}-"
            f"{int(date_value):02d}"
        )

        daytime = day.get(
            "daytimeForecast",
            {}
        )

        nighttime = day.get(
            "nighttimeForecast",
            {}
        )

        # ----------------------------------------------------
        # Temperature
        # ----------------------------------------------------

        min_temp = num(
            day.get(
                "minTemperature",
                {}
            ).get(
                "degrees"
            )
        )

        max_temp = num(
            day.get(
                "maxTemperature",
                {}
            ).get(
                "degrees"
            )
        )

        # ----------------------------------------------------
        # Day precipitation
        # ----------------------------------------------------

        day_precip = daytime.get(
            "precipitation",
            {}
        )

        night_precip = nighttime.get(
            "precipitation",
            {}
        )

        day_probability = num(
            day_precip.get(
                "probability",
                {}
            ).get(
                "percent"
            ),
            0
        )

        night_probability = num(
            night_precip.get(
                "probability",
                {}
            ).get(
                "percent"
            ),
            0
        )

        day_qpf = num(
            day_precip.get(
                "qpf",
                {}
            ).get(
                "quantity"
            ),
            0.0
        )

        night_qpf = num(
            night_precip.get(
                "qpf",
                {}
            ).get(
                "quantity"
            ),
            0.0
        )

        # ----------------------------------------------------
        # Humidity
        # ----------------------------------------------------

        humidity_values = []

        day_humidity = num(
            daytime.get(
                "relativeHumidity"
            )
        )

        night_humidity = num(
            nighttime.get(
                "relativeHumidity"
            )
        )

        if day_humidity is not None:
            humidity_values.append(
                day_humidity
            )

        if night_humidity is not None:
            humidity_values.append(
                night_humidity
            )

        humidity = None

        if humidity_values:
            humidity = round(
                sum(humidity_values)
                / len(humidity_values)
            )

        # ----------------------------------------------------
        # Wind
        # ----------------------------------------------------

        day_wind = daytime.get(
            "wind",
            {}
        )

        night_wind = nighttime.get(
            "wind",
            {}
        )

        day_speed = num(
            day_wind.get(
                "speed",
                {}
            ).get(
                "value"
            ),
            0.0
        )

        night_speed = num(
            night_wind.get(
                "speed",
                {}
            ).get(
                "value"
            ),
            0.0
        )

        day_gust = num(
            day_wind.get(
                "gust",
                {}
            ).get(
                "value"
            ),
            0.0
        )

        night_gust = num(
            night_wind.get(
                "gust",
                {}
            ).get(
                "value"
            ),
            0.0
        )

        wind_max = max(
            day_speed,
            night_speed
        )

        gust = max(
            day_gust,
            night_gust
        )

        # ----------------------------------------------------
        # Weather condition
        # ----------------------------------------------------

        condition = (
            daytime.get(
                "weatherCondition",
                {}
            )
            .get(
                "type",
                "CLOUDY"
            )
        )

        condition_text = (
            daytime.get(
                "weatherCondition",
                {}
            )
            .get(
                "description",
                {}
            )
            .get(
                "text"
            )
        )

        result.append({

            "date": date,

            "min_temp": _r(
                min_temp
            ),

            "max_temp": _r(
                max_temp
            ),

            "rain": _r(
                day_qpf + night_qpf
            ),

            "rain_prob": _r(
                max(
                    day_probability,
                    night_probability
                ),
                0
            ),

            "gust": _r(
                gust,
                0
            ),

            "wind_max": _r(
                wind_max,
                0
            ),

            "humidity": humidity,

            "code": google_condition_to_code(
                condition
            ),

            "condition": condition,

            "condition_text": condition_text,
        })

    return result


# ============================================================
# GOOGLE WEATHER FETCH
# ============================================================

async def _fetch_google_weather(
    lat,
    lng
):
    """
    Fetch hourly + daily Google weather
    for the exact Panchayat coordinates.
    """

    hourly_task = _google_get(
        GOOGLE_HOURLY_URL,
        lat,
        lng,
        {
            "hours": 240,
            "pageSize": 240,
        }
    )

    daily_task = _google_get(
        GOOGLE_DAILY_URL,
        lat,
        lng,
        {
            "days": 10,
            "pageSize": 10,
        }
    )

    hourly_raw, daily_raw = await asyncio.gather(
        hourly_task,
        daily_task
    )

    hourly = normalize_hourly(
        hourly_raw
    )

    daily = normalize_daily(
        daily_raw
    )

    if not hourly and not daily:
        raise ValueError(
            "Google returned empty forecast"
        )

    # Google response timezone
    timezone_info = (
        hourly_raw.get(
            "timeZone"
        )
        or daily_raw.get(
            "timeZone"
        )
        or {}
    )

    timezone_name = (
        timezone_info.get(
            "id"
        )
        if isinstance(
            timezone_info,
            dict
        )
        else None
    )

    # Some API responses expose timezone
    # through displayDateTime.utcOffset.
    utc_offset_seconds = 0

    if hourly:
        first_hour = (
            hourly_raw
            .get(
                "forecastHours",
                []
            )
        )

        if first_hour:

            display_dt = first_hour[0].get(
                "displayDateTime",
                {}
            )

            offset_value = display_dt.get(
                "utcOffset"
            )

            if isinstance(
                offset_value,
                str
            ):
                try:
                    # Example:
                    # "-28800s"
                    utc_offset_seconds = int(
                        offset_value.rstrip("s")
                    )
                except ValueError:
                    utc_offset_seconds = 0

    return {
        "daily": daily,
        "hourly": hourly,
        "elevation": None,
        "utc_offset_seconds": utc_offset_seconds,
        "timezone": timezone_name,
    }


# ============================================================
# NORMALIZED WEATHER WITH CACHE + FALLBACK
# ============================================================

async def get_norm(
    lat,
    lng,
    model=None,
    light=False
):
    """
    Return:
        (normalized_data, stale)

    Google Weather is the primary source.

    model/light are retained in the function signature
    for compatibility with the existing code.
    """

    # Google Weather does not need Open-Meteo's model argument.
    key = (
        "google",
        round(float(lat), 4),
        round(float(lng), 4),
    )

    if key in _fresh:
        return _fresh[key], False

    try:

        data = await _fetch_google_weather(
            lat,
            lng
        )

        if not data["daily"] and not data["hourly"]:
            raise ValueError(
                "empty Google forecast"
            )

        _fresh[key] = data
        _last_good[key] = data

        return data, False

    except Exception as exc:

        log.warning(
            "Google Weather fetch failed for %s: %s: %s",
            key,
            type(exc).__name__,
            exc
        )

        # ----------------------------------------------------
        # Last known good data
        # ----------------------------------------------------

        if key in _last_good:

            log.warning(
                "Serving last known good Google weather for %s",
                key
            )

            return (
                _last_good[key],
                True
            )

        raise WeatherUnavailable(
            type(exc).__name__
        ) from exc


# ============================================================
# FIND CURRENT HOUR
# ============================================================

def _now_slice(pan):
    """
    Google gives ISO timestamps in UTC.
    Find the forecast hour closest to current time.
    """

    if not pan.get("hourly"):
        return 0

    now_utc = datetime.now(
        timezone.utc
    )

    times = []

    for item in pan["hourly"]:

        value = item.get(
            "time"
        )

        if not value:
            continue

        try:

            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

            times.append(
                parsed
            )

        except ValueError:
            continue

    if not times:
        return 0

    for index, timestamp in enumerate(times):

        if timestamp >= now_utc:
            return index

    return len(times) - 1


# ============================================================
# COMPLETE FORECAST BUNDLE
# ============================================================

async def forecast_bundle(
    lat,
    lng,
    block_lat=None,
    block_lng=None,
    crop="general"
):
    """
    Complete Panchayat weather response.

    Primary weather:
        Google Weather API

    Coordinates:
        Exact Panchayat lat/lng

    Optional:
        Block weather for local comparison.
    """

    same_block = (
        block_lat is None
        or block_lng is None
        or (
            abs(
                block_lat - lat
            ) < 1e-4

            and

            abs(
                block_lng - lng
            ) < 1e-4
        )
    )

    # --------------------------------------------------------
    # Panchayat weather
    # --------------------------------------------------------

    tasks = [
        get_norm(
            lat,
            lng
        )
    ]

    # --------------------------------------------------------
    # Block weather
    # --------------------------------------------------------

    if not same_block:

        tasks.append(
            get_norm(
                block_lat,
                block_lng
            )
        )

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    # --------------------------------------------------------
    # Panchayat failure
    # --------------------------------------------------------

    if isinstance(
        results[0],
        Exception
    ):

        if isinstance(
            results[0],
            WeatherUnavailable
        ):
            raise results[0]

        raise WeatherUnavailable(
            type(
                results[0]
            ).__name__
        )

    pan, stale = results[0]

    # --------------------------------------------------------
    # Block result
    # --------------------------------------------------------

    blk = None

    if (
        not same_block
        and
        len(results) > 1
        and
        not isinstance(
            results[1],
            Exception
        )
    ):
        blk = results[1][0]

    # --------------------------------------------------------
    # Current hour
    # --------------------------------------------------------

    idx = _now_slice(
        pan
    )

    hourly24 = pan["hourly"][
        idx:idx + 24
    ]

    now = (
        pan["hourly"][idx]
        if pan["hourly"]
        and idx < len(pan["hourly"])
        else None
    )

    # --------------------------------------------------------
    # Advisory engine
    # --------------------------------------------------------

    advisories = await adv.build_advisories(
        pan["daily"],
        crop,
        current=now,
    )

    dates3 = [
        d["date"]
        for d in pan["daily"][:3]
    ]

    # --------------------------------------------------------
    # Confidence
    #
    # Google is primary.
    # There is no second Open-Meteo model here.
    # Keep confidence compatible with frontend.
    # --------------------------------------------------------

    confidence = []

    try:

        confidence = downscale.confidence(
            pan["daily"],
            None
        )

    except Exception as exc:

        log.warning(
            "Confidence calculation skipped: %s",
            exc
        )

    # --------------------------------------------------------
    # Local adjustment
    # --------------------------------------------------------

    try:

        local_adjustment = (
            downscale.local_adjustment(
                pan,
                blk
            )
        )

    except Exception as exc:

        log.warning(
            "Local adjustment failed: %s",
            exc
        )

        local_adjustment = None

    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {

        "location": {

            "lat": lat,

            "lng": lng,

            "elevation_m": (
                pan.get(
                    "elevation"
                )
            ),

            "timezone": (
                pan.get(
                    "timezone"
                )
            ),
        },

        "now": now,

        "daily": pan["daily"],

        "hourly": hourly24,

        "confidence": confidence,

        "local_adjustment": local_adjustment,

        "block_daily": (
            blk["daily"]
            if blk
            else []
        ),

        "advisories": advisories,

        "alerts": adv.alerts(
            advisories,
            dates3
        ),

        "meta": {

            "source": "Google Weather API",

            "second_model": None,

            "updated_at": (
                datetime.now(
                    timezone.utc
                ).isoformat(
                    timespec="seconds"
                )
            ),

            "stale": stale,

            "crop": crop,

            "point_weather": True,

            "coordinates": {
                "latitude": lat,
                "longitude": lng,
            },
        },
    }