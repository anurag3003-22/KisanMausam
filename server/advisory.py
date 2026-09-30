"""
AI-powered agricultural advisory engine.

Architecture:
    Google Weather API
            ↓
      normalized forecast
            ↓
    deterministic safety rules
            ↓
          Groq AI
            ↓
   farmer-friendly advisory

The rule engine remains the safety boundary.
Groq interprets the live weather + crop context and creates
natural, contextual recommendations.

IMPORTANT:
- Never expose GROQ_API_KEY to the frontend.
- API key is loaded from server/.env.
- If Groq is unavailable, deterministic advisories still work.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# PATHS / ENV
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
ENV_FILE = _HERE / ".env"

# Explicitly load server/.env
load_dotenv(dotenv_path=ENV_FILE)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Current Groq-supported reasoning model.
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

GROQ_TIMEOUT_SECONDS = float(
    os.getenv("GROQ_TIMEOUT_SECONDS", "25")
)

GROQ_REASONING_EFFORT = os.getenv(
    "GROQ_REASONING_EFFORT",
    "low"
)


# ---------------------------------------------------------------------------
# LOAD LOCAL AGRICULTURAL KNOWLEDGE
# ---------------------------------------------------------------------------

RULES = json.loads(
    (_HERE / "advisory_rules.json").read_text(
        encoding="utf-8"
    )
)

CROP_TIPS = json.loads(
    (_HERE / "crop_advice.json").read_text(
        encoding="utf-8"
    )
)

T = RULES["thresholds"]
KINDS = RULES["kinds"]

CROPS = [
    "general"
] + [
    k for k in CROP_TIPS
    if not k.startswith("_")
]

SEVERITY_RANK = {
    "info": 0,
    "watch": 1,
    "warning": 2,
    "danger": 3,
}


# ---------------------------------------------------------------------------
# SIMPLE IN-MEMORY AI CACHE
# ---------------------------------------------------------------------------

# Avoid calling Groq repeatedly for exactly the same forecast.
_AI_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}

AI_CACHE_SECONDS = int(
    os.getenv("GROQ_CACHE_SECONDS", "600")
)


# ---------------------------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------------------------

def _make(
    kind,
    date,
    valid_to=None,
    crop="general",
    **vals
):
    """
    Create a standard advisory object compatible with the existing frontend.
    """

    k = KINDS[kind]

    tip = (
        CROP_TIPS
        .get(crop, {})
        .get(k["category"])
    )

    return {
        "id": f"{date}-{kind}",
        "kind": kind,
        "category": k["category"],
        "severity": k["severity"],
        "icon": k["icon"],

        "title_en": k["title_en"],
        "title_hi": k["title_hi"],

        "message_en": k["en"].format(**vals),
        "message_hi": k["hi"].format(**vals),

        "crop": crop if tip else None,

        "crop_tip_en": (
            tip["en"]
            if tip
            else None
        ),

        "crop_tip_hi": (
            tip["hi"]
            if tip
            else None
        ),

        "valid_from": date,
        "valid_to": valid_to or date,
    }


def _f(v):
    """
    Safely convert a value to float.
    """

    try:
        f = float(v)

        if f != f:
            return None

        return f

    except (TypeError, ValueError):
        return None


def _clean_text(value):
    """
    Safely convert model output to a clean string.
    """

    if value is None:
        return ""

    return str(value).strip()


# ---------------------------------------------------------------------------
# DETERMINISTIC WEATHER RULE ENGINE
# ---------------------------------------------------------------------------

def day_advisories(
    day,
    crop="general"
):
    """
    Generate deterministic safety advisories for one forecast day.

    Expected weather structure:

        date
        rain
        rain_prob
        min_temp
        max_temp
        gust
        wind_max
        humidity
        code
    """

    date = day["date"]

    rain = _f(day.get("rain")) or 0.0
    gust = _f(day.get("gust")) or 0.0

    tmax = _f(day.get("max_temp"))
    tmin = _f(day.get("min_temp"))

    code = day.get("code")

    if isinstance(code, (int, float)):
        code = int(code)
    else:
        code = -1

    vals = {
        "rain": round(rain),
        "wind": round(gust),
        "temp": "",
        "days": 1,
    }

    out = []

    # -----------------------------------------------------------------------
    # RAIN
    # -----------------------------------------------------------------------

    if rain >= T["flood_rain_mm"]:

        out.append(
            _make(
                "flood_risk",
                date,
                crop=crop,
                **vals
            )
        )

    elif rain >= T["heavy_rain_mm"]:

        out.append(
            _make(
                "heavy_rain",
                date,
                crop=crop,
                **vals
            )
        )

    elif rain >= T["moderate_rain_mm"]:

        out.append(
            _make(
                "moderate_rain",
                date,
                crop=crop,
                **vals
            )
        )

    # -----------------------------------------------------------------------
    # WIND
    # -----------------------------------------------------------------------

    if gust >= T["gale_gust_kmh"]:

        out.append(
            _make(
                "gale",
                date,
                crop=crop,
                **vals
            )
        )

    elif gust >= T["wind_gust_kmh"]:

        out.append(
            _make(
                "strong_wind",
                date,
                crop=crop,
                **vals
            )
        )

    # -----------------------------------------------------------------------
    # MAX TEMPERATURE
    # -----------------------------------------------------------------------

    if tmax is not None:

        if tmax >= T["severe_heat_c"]:

            out.append(
                _make(
                    "severe_heat",
                    date,
                    crop=crop,
                    **{
                        **vals,
                        "temp": round(tmax),
                    }
                )
            )

        elif tmax >= T["heat_c"]:

            out.append(
                _make(
                    "heat",
                    date,
                    crop=crop,
                    **{
                        **vals,
                        "temp": round(tmax),
                    }
                )
            )

    # -----------------------------------------------------------------------
    # MIN TEMPERATURE
    # -----------------------------------------------------------------------

    if tmin is not None:

        if tmin <= T["frost_c"]:

            out.append(
                _make(
                    "frost",
                    date,
                    crop=crop,
                    **{
                        **vals,
                        "temp": round(tmin),
                    }
                )
            )

        elif tmin <= T["cold_night_c"]:

            out.append(
                _make(
                    "cold",
                    date,
                    crop=crop,
                    **{
                        **vals,
                        "temp": round(tmin),
                    }
                )
            )

    # -----------------------------------------------------------------------
    # HAIL / THUNDERSTORM
    # -----------------------------------------------------------------------

    if code in T["hail_codes"]:

        out.append(
            _make(
                "hail",
                date,
                crop=crop,
                **vals
            )
        )

    elif code in T["thunderstorm_codes"]:

        out.append(
            _make(
                "thunderstorm",
                date,
                crop=crop,
                **vals
            )
        )

    return out


# ---------------------------------------------------------------------------
# DRY SPELL DETECTION
# ---------------------------------------------------------------------------

def _dry_spell_advisory(
    daily,
    crop
):
    """
    Detect prolonged hot + dry weather.
    """

    if len(daily) < 5:
        return None

    total_rain = sum(
        _f(d.get("rain")) or 0.0
        for d in daily
    )

    hot = [
        t
        for t in (
            _f(d.get("max_temp"))
            for d in daily
        )
        if t is not None
    ]

    if not hot:
        return None

    average_temp = sum(hot) / len(hot)

    if (
        total_rain < T["dry_spell_rain_mm"]
        and average_temp >= T["dry_spell_hot_c"]
    ):

        return _make(
            "dry_spell",
            daily[0]["date"],
            valid_to=daily[-1]["date"],
            crop=crop,
            rain=0,
            wind=0,
            temp="",
            days=len(daily),
        )

    return None


# ---------------------------------------------------------------------------
# WEATHER RISK SUMMARY FOR AI
# ---------------------------------------------------------------------------

def _calculate_rule_risk(
    daily,
    crop
):
    """
    Build a compact deterministic risk summary.

    This is sent to Groq so that AI recommendations cannot ignore
    detected severe weather.
    """

    result = []

    for day in daily:

        advisories = day_advisories(
            day,
            crop
        )

        for advisory in advisories:

            result.append({
                "date": advisory["valid_from"],
                "kind": advisory["kind"],
                "severity": advisory["severity"],
                "category": advisory["category"],
                "title": advisory["title_en"],
            })

    return result


# ---------------------------------------------------------------------------
# CROP KNOWLEDGE FOR AI
# ---------------------------------------------------------------------------

def _crop_context(crop):
    """
    Only send the selected crop's knowledge to Groq.
    """

    if crop not in CROP_TIPS:
        return {}

    return CROP_TIPS[crop]


# ---------------------------------------------------------------------------
# AI PROMPT
# ---------------------------------------------------------------------------

def _build_ai_prompt(
    daily,
    crop,
    rule_risks,
    current=None,
):
    """
    Build a grounded, crop-specific prompt for Groq.

    The deterministic rule engine remains the safety boundary.
    Groq is responsible for turning the supplied weather + crop context
    into farmer-friendly language.
    """

    crop_name = crop or "general"
    selected_crop_tips = _crop_context(crop_name)

    weather_payload = []

    for day in daily:
        weather_payload.append({
            "date": day.get("date"),
            "min_temp_c": day.get("min_temp"),
            "max_temp_c": day.get("max_temp"),
            "rain_mm": day.get("rain"),
            "rain_probability_percent": day.get("rain_prob"),
            "humidity_percent": day.get("humidity"),
            "wind_kmh": day.get("wind_max"),
            "gust_kmh": day.get("gust"),
            "weather_code": day.get("code"),
            "condition": day.get("condition"),
            "condition_text": day.get("condition_text"),
        })

    current_payload = None
    if current:
        current_payload = {
            "temp_c": current.get("temp"),
            "humidity_percent": current.get("humidity"),
            "rain_mm": current.get("rain"),
            "rain_probability_percent": current.get("rain_prob"),
            "wind_kmh": current.get("wind"),
            "gust_kmh": current.get("gust"),
            "weather_code": current.get("code"),
        }

    return f"""
You are KisanMausam's crop-specific agricultural weather advisory assistant
for Indian farmers.

Your output will be displayed directly inside a farmer-facing "Today's Advice"
card. Make it practical, short, specific to the selected crop, and based only
on the supplied data.

SELECTED CROP:
{json.dumps(crop_name, ensure_ascii=False)}

CROP KNOWLEDGE:
{json.dumps(selected_crop_tips, ensure_ascii=False)}

CURRENT WEATHER:
{json.dumps(current_payload, ensure_ascii=False)}

10-DAY WEATHER FORECAST:
{json.dumps(weather_payload, ensure_ascii=False)}

DETERMINISTIC WEATHER RISKS:
{json.dumps(rule_risks, ensure_ascii=False)}

RULES:

1. Never invent weather values, rainfall, temperature, humidity, wind, or
   forecast conditions.
2. Never contradict a deterministic danger/warning.
3. If heavy rain or flood risk exists, never recommend irrigation.
4. If meaningful rain is expected, do not recommend spraying or fertilizer
   immediately before the rain.
5. If strong wind exists, do not recommend spraying.
6. Use the selected crop knowledge to make the advice DIFFERENT for each crop.
   Do not give generic advice that would apply equally to every crop.
7. Do not assume a crop growth stage unless it is explicitly supplied.
8. If weather is suitable, explain a useful crop-specific field activity or
   check instead of repeating "weather is good".
9. Rain probability is a forecast signal, not guaranteed rainfall.
10. Do not diagnose pests/diseases from weather alone.
11. Do not give pesticide names, chemical doses, fertilizer doses, or medicine
    doses.
12. Keep message_en/message_hi to 1-2 short sentences.
13. Give 2-3 concise actions and one monitoring point.
14. The title should describe the actual recommendation, not just say
    "AI Crop Advisory".
15. Generate exactly one advisory for EACH supplied forecast date.
16. Return ONLY JSON matching the supplied schema.

The "crop_tip" fields must contain advice specifically about the selected crop.
""".strip()


# ---------------------------------------------------------------------------
# JSON EXTRACTION
# ---------------------------------------------------------------------------

def _extract_json(text):
    """
    Extract JSON even if the model accidentally wraps it in markdown fences.
    """

    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown fences
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    # Direct JSON
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to locate JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:

        candidate = cleaned[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    return None


# ---------------------------------------------------------------------------
# GROQ REQUEST
# ---------------------------------------------------------------------------

AI_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "advisories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "title_en": {"type": "string"},
                    "title_hi": {"type": "string"},
                    "message_en": {"type": "string"},
                    "message_hi": {"type": "string"},
                    "crop_tip_en": {"type": "string"},
                    "crop_tip_hi": {"type": "string"},
                    "actions_en": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "actions_hi": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "watch_en": {"type": "string"},
                    "watch_hi": {"type": "string"},
                },
                "required": [
                    "date",
                    "title_en",
                    "title_hi",
                    "message_en",
                    "message_hi",
                    "crop_tip_en",
                    "crop_tip_hi",
                    "actions_en",
                    "actions_hi",
                    "watch_en",
                    "watch_hi",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["advisories"],
    "additionalProperties": False,
}


async def _call_groq(
    daily,
    crop,
    rule_risks,
    current=None,
):
    """
    Call Groq with strict Structured Outputs.

    The API key stays server-side in server/.env.
    """

    if not GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY is not configured. "
            "Using deterministic advisory engine only."
        )
        return []

    prompt = _build_ai_prompt(
        daily=daily,
        crop=crop,
        rule_risks=rule_risks,
        current=current,
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful agricultural advisory assistant. "
                    "Follow the JSON schema exactly. "
                    "Never invent weather data."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
        "max_completion_tokens": 5000,
        "reasoning_effort": GROQ_REASONING_EFFORT,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "kisanmausam_crop_advisories",
                "strict": True,
                "schema": AI_JSON_SCHEMA,
            },
        },
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(
            timeout=GROQ_TIMEOUT_SECONDS
        ) as client:
            response = await client.post(
                GROQ_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = (
            data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        parsed = _extract_json(content)

        if not isinstance(parsed, dict):
            logger.error(
                "Groq returned invalid structured advisory JSON."
            )
            return None

        advisories = parsed.get("advisories")

        if not isinstance(advisories, list) or not advisories:
            logger.error(
                "Groq returned no advisory items for crop=%s",
                crop,
            )
            return None

        logger.info(
            "Groq generated %d crop-specific advisory item(s) for crop=%s",
            len(advisories),
            crop,
        )

        return advisories

    except Exception as exc:
        logger.exception(
            "Groq advisory generation failed: %s",
            exc
        )
        # Weather dashboard must still work if Groq is unavailable.
        return None


# ---------------------------------------------------------------------------
# AI CACHE KEY
# ---------------------------------------------------------------------------

def _cache_key(
    daily,
    crop
):
    """
    Create stable cache key from forecast + crop.
    """

    compact = []

    for d in daily:

        compact.append({
            "date": d.get("date"),
            "min_temp": d.get("min_temp"),
            "max_temp": d.get("max_temp"),
            "rain": d.get("rain"),
            "rain_prob": d.get("rain_prob"),
            "humidity": d.get("humidity"),
            "wind_max": d.get("wind_max"),
            "gust": d.get("gust"),
            "code": d.get("code"),
        })

    return json.dumps(
        {
            "crop": crop,
            "weather": compact,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _get_cached_ai(key):
    now = datetime.now(
        timezone.utc
    ).timestamp()

    item = _AI_CACHE.get(key)

    if not item:
        return None

    created_at, data = item

    if now - created_at > AI_CACHE_SECONDS:

        _AI_CACHE.pop(
            key,
            None
        )

        return None

    return data


def _set_cached_ai(
    key,
    data
):
    now = datetime.now(
        timezone.utc
    ).timestamp()

    _AI_CACHE[key] = (
        now,
        data
    )


# ---------------------------------------------------------------------------
# CONVERT AI OUTPUT TO EXISTING FRONTEND FORMAT
# ---------------------------------------------------------------------------

def _convert_ai_advisories(
    ai_items,
    daily,
    crop
):
    """
    Convert strict Groq JSON into the existing frontend Advisory shape.
    """

    daily_dates = {
        str(d.get("date"))
        for d in daily
    }

    result = []

    for item in ai_items:
        if not isinstance(item, dict):
            continue

        date = str(item.get("date", "")).strip()
        if date not in daily_dates:
            continue

        message_en = _clean_text(item.get("message_en"))
        message_hi = _clean_text(item.get("message_hi"))

        if not message_en and not message_hi:
            continue

        actions_en = item.get("actions_en", [])
        actions_hi = item.get("actions_hi", [])

        if not isinstance(actions_en, list):
            actions_en = []
        if not isinstance(actions_hi, list):
            actions_hi = []

        action_lines_en = [
            _clean_text(a) for a in actions_en[:3] if _clean_text(a)
        ]
        action_lines_hi = [
            _clean_text(a) for a in actions_hi[:3] if _clean_text(a)
        ]

        if action_lines_en:
            message_en += (
                "\n\nWhat to do:\n"
                + "\n".join(f"• {a}" for a in action_lines_en)
            )

        if action_lines_hi:
            message_hi += (
                "\n\nक्या करें:\n"
                + "\n".join(f"• {a}" for a in action_lines_hi)
            )

        watch_en = _clean_text(item.get("watch_en"))
        watch_hi = _clean_text(item.get("watch_hi"))

        if watch_en:
            message_en += f"\n\nWatch: {watch_en}"
        if watch_hi:
            message_hi += f"\n\nनिगरानी: {watch_hi}"

        result.append({
            "id": f"{date}-ai-advisory",
            "kind": "ai_advisory",
            "category": "ai",
            "severity": "info",
            "icon": "leaf",
            "title_en": _clean_text(item.get("title_en")) or "Today's crop advice",
            "title_hi": _clean_text(item.get("title_hi")) or "आज की फसल सलाह",
            "message_en": message_en,
            "message_hi": message_hi,
            "crop": crop,
            "crop_tip_en": _clean_text(item.get("crop_tip_en")) or None,
            "crop_tip_hi": _clean_text(item.get("crop_tip_hi")) or None,
            "valid_from": date,
            "valid_to": date,
            "source": "Groq AI",
        })

    logger.info(
        "Converted %d/%d Groq advisory item(s) for crop=%s",
        len(result),
        len(ai_items),
        crop,
    )

    return result


# ---------------------------------------------------------------------------
# PUBLIC ADVISORY BUILDER
# ---------------------------------------------------------------------------

async def build_advisories(
    daily,
    crop="general",
    current=None,
):
    """
    Generate complete advisory set.

    1. Deterministic safety rules
    2. Dry-spell detection
    3. Groq AI contextual advice
    4. Merge everything

    IMPORTANT:
    This function is async because Groq is an external API.
    """

    crop = (
        crop
        if crop in CROPS
        else "general"
    )

    # -----------------------------------------------------------------------
    # RULE-BASED ADVISORIES
    # -----------------------------------------------------------------------

    result = []

    # The daily forecast describes the whole day, while the dashboard also
    # shows the live/current weather.  A live thunderstorm must therefore
    # override a generic "good weather" message for TODAY even when the
    # provider's daytime daily condition is still clear.
    current_items = []
    if current and daily:
        current_day = {
            "date": daily[0]["date"],
            "rain": 0,  # current hourly rain is not a daily rainfall total
            "gust": current.get("gust", 0),
            "max_temp": current.get("temp"),
            "min_temp": current.get("temp"),
            "code": current.get("code"),
        }
        current_items = day_advisories(current_day, crop)

    for index, d in enumerate(daily):

        items = day_advisories(
            d,
            crop
        )

        # Merge live/current safety hazards into today's advisories.
        if index == 0 and current_items:
            existing = {item["kind"] for item in items}
            items.extend(
                item for item in current_items
                if item["kind"] not in existing
            )

        if not items:

            items = [
                _make(
                    "good_weather",
                    d["date"],
                    crop=crop,
                    rain=0,
                    wind=0,
                    temp="",
                    days=1,
                )
            ]

        result.extend(items)

    # -----------------------------------------------------------------------
    # DRY SPELL
    # -----------------------------------------------------------------------

    dry_spell = _dry_spell_advisory(
        daily,
        crop
    )

    if dry_spell:

        result.append(
            dry_spell
        )

    # -----------------------------------------------------------------------
    # GROQ AI
    # -----------------------------------------------------------------------

    rule_risks = _calculate_rule_risk(
        daily,
        crop
    )

    cache_key = _cache_key(
        daily,
        crop
    )

    ai_items = _get_cached_ai(
        cache_key
    )

    if ai_items is None:

        ai_items = await _call_groq(
            daily=daily,
            crop=crop,
            rule_risks=rule_risks,
            current=current,
        )

        # Cache only successful Groq results.
        # A temporary API/model/JSON failure must not be cached for 10 minutes.
        if ai_items is not None:
            _set_cached_ai(
                cache_key,
                ai_items
            )
        else:
            ai_items = []

    ai_advisories = _convert_ai_advisories(
        ai_items,
        daily,
        crop
    )

    # When Groq successfully produces a crop-specific advice for a normal
    # weather day, replace the generic "Good weather" placeholder for that
    # same date. Safety advisories (watch/warning/danger) are never removed.
    ai_dates = {
        a["valid_from"]
        for a in ai_advisories
    }

    result = [
        a
        for a in result
        if not (
            a.get("kind") == "good_weather"
            and a.get("valid_from") in ai_dates
        )
    ]

    result.extend(ai_advisories)

    # -----------------------------------------------------------------------
    # SORT
    # -----------------------------------------------------------------------

    result.sort(
        key=lambda a: (
            a["valid_from"],
            -SEVERITY_RANK.get(
                a.get("severity"),
                0
            ),
        )
    )

    return result


# ---------------------------------------------------------------------------
# TOP ADVISORY
# ---------------------------------------------------------------------------

def top_for_day(
    advisories,
    date
):
    """
    Return highest-severity advisory for a date.
    """

    day = [
        a
        for a in advisories
        if (
            a["valid_from"]
            <= date
            <= a["valid_to"]
        )
    ]

    return (
        max(
            day,
            key=lambda a:
            SEVERITY_RANK.get(
                a.get("severity"),
                0
            )
        )
        if day
        else None
    )


# ---------------------------------------------------------------------------
# ALERTS
# ---------------------------------------------------------------------------

def alerts(
    advisories,
    dates,
    min_severity="warning"
):
    """
    Return serious alerts only.

    AI advisories are severity=info, therefore they do not accidentally
    become safety alerts.
    """

    limit = SEVERITY_RANK[
        min_severity
    ]

    keep = set(dates)

    return [
        a
        for a in advisories
        if (
            SEVERITY_RANK.get(
                a.get("severity"),
                0
            ) >= limit
            and a["valid_from"] in keep
        )
    ]