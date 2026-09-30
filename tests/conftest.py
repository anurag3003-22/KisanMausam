import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_payload(elevation=550.0, rain=None, tmax=None, tmin=None, gust=None, code=None, light=False, offset=19800):
    """Synthetic response in the documented Open-Meteo shape (IST offset)."""
    today = (datetime.now(timezone.utc) + timedelta(seconds=offset)).date()
    days = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    rain = rain or [0, 2, 10, 70, 0, 0, 0]
    tmax = tmax or [34, 33, 31, 29, 33, 35, 36]
    tmin = tmin or [22, 21, 20, 20, 19, 21, 22]
    gust = gust or [20, 25, 30, 45, 20, 18, 22]
    code = code or [1, 3, 61, 65, 2, 0, 0]
    out = {"latitude": 22.8, "longitude": 75.5, "elevation": elevation, "utc_offset_seconds": offset,
           "timezone": "Asia/Kolkata",
           "daily": {"time": days, "temperature_2m_min": tmin, "temperature_2m_max": tmax,
                     "precipitation_sum": rain}}
    if not light:
        out["daily"].update({"wind_gusts_10m_max": gust, "wind_speed_10m_max": [g - 8 for g in gust],
                             "precipitation_probability_max": [10, 30, 60, 90, 20, 5, 0], "weather_code": code})
        times, hours = [], []
        start = datetime.combine(today, datetime.min.time())
        for h in range(7 * 24):
            times.append((start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00"))
        out["hourly"] = {"time": times, "temperature_2m": [25 + (h % 24) / 3 for h in range(len(times))],
                         "relative_humidity_2m": [60] * len(times),
                         "precipitation_probability": [20] * len(times), "precipitation": [0.1] * len(times),
                         "wind_speed_10m": [12] * len(times), "weather_code": [1] * len(times)}
    return out


@pytest.fixture
def mock_api(monkeypatch):
    """Route every Open-Meteo call to a fake. Returns a dict to tweak behaviour and inspect calls."""
    from server import weather
    state = {"calls": [], "fail": False, "fail_models": False, "block_elev": 520.0, "pan_elev": 585.0}

    def handler(request: httpx.Request):
        p = dict(request.url.params)
        state["calls"].append(p)
        if state["fail"]:
            return httpx.Response(500, json={"error": True})
        if p.get("models") and state["fail_models"]:
            return httpx.Response(400, json={"error": True, "reason": "bad model"})
        light = "hourly" not in p
        lat = float(p["latitude"])
        elev = state["pan_elev"] if abs(lat - 22.8) < 0.01 else state["block_elev"]
        if p.get("models"):
            return httpx.Response(200, json=make_payload(elevation=elev, rain=[0, 3, 20, 40, 0, 0, 0], light=True))
        return httpx.Response(200, json=make_payload(elevation=elev, light=light))

    weather._fresh.clear()
    weather._last_good.clear()
    monkeypatch.setattr(weather, "_transport", httpx.MockTransport(handler))
    return state


@pytest.fixture
def client(mock_api):
    from fastapi.testclient import TestClient
    from server.main import app, _hits
    _hits.clear()
    return TestClient(app)
