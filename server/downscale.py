"""Panchayat-level refinement of a coarse forecast.

What this prototype really does (kept deliberately honest):
  * The forecast source is a ~9-25 km weather-model grid. Open-Meteo corrects
    temperature for the height difference between that grid cell and the exact
    point requested using a 90 m elevation model.
  * We request the forecast for the block centre AND for the Panchayat itself and
    show the difference, so a farmer/judge can see what "local" changed.
  * We add a spread between two weather models as a simple confidence range.
  * `trained_model_placeholder` is where a model trained on IMD/AWS station data
    would plug in.
"""

LAPSE_RATE_C_PER_KM = 6.5


def lapse_adjustment(block_elevation_m, panchayat_elevation_m):
    """Temperature change (deg C) expected from the height difference alone."""
    if block_elevation_m is None or panchayat_elevation_m is None:
        return None
    return round(-(panchayat_elevation_m - block_elevation_m) * LAPSE_RATE_C_PER_KM / 1000.0, 1)


def _diff(a, b):
    return None if a is None or b is None else round(a - b, 1)


def local_adjustment(pan, blk):
    """Compare Panchayat forecast with the block-centre forecast (both normalized dicts)."""
    if not blk:
        return {"available": False}
    days = []
    for p, b in zip(pan["daily"], blk["daily"]):
        days.append({
            "date": p["date"],
            "max_temp_diff": _diff(p["max_temp"], b["max_temp"]),
            "min_temp_diff": _diff(p["min_temp"], b["min_temp"]),
            "rain_diff": _diff(p["rain"], b["rain"]),
        })
    elev_diff = None
    if pan.get("elevation") is not None and blk.get("elevation") is not None:
        elev_diff = round(pan["elevation"] - blk["elevation"])
    return {
        "available": True,
        "block_elevation_m": blk.get("elevation"),
        "panchayat_elevation_m": pan.get("elevation"),
        "elevation_diff_m": elev_diff,
        "height_effect_c": lapse_adjustment(blk.get("elevation"), pan.get("elevation")),
        "days": days,
    }


def confidence(pan_daily, alt_daily):
    """Spread between two models -> min/likely/max and a High/Medium/Low label."""
    if not alt_daily:
        return []
    out = []
    for p, a in zip(pan_daily, alt_daily):
        if p["date"] != a["date"]:
            continue
        rains = [p["rain"], a["rain"]]
        tmaxs = [t for t in (p["max_temp"], a["max_temp"]) if t is not None]
        rain_spread = max(rains) - min(rains)
        t_spread = (max(tmaxs) - min(tmaxs)) if len(tmaxs) == 2 else 0.0
        if rain_spread <= 5 and t_spread <= 2:
            level = "high"
        elif rain_spread <= 15 and t_spread <= 4:
            level = "medium"
        else:
            level = "low"
        out.append({
            "date": p["date"],
            "rain_min": round(min(rains), 1), "rain_likely": round(p["rain"], 1), "rain_max": round(max(rains), 1),
            "tmax_min": round(min(tmaxs), 1) if tmaxs else None,
            "tmax_likely": round(p["max_temp"], 1) if p["max_temp"] is not None else None,
            "tmax_max": round(max(tmaxs), 1) if tmaxs else None,
            "level": level,
        })
    return out


def trained_model_placeholder(features):
    """Upgrade point: gradient boosting / ML model trained on local station data."""
    return None
