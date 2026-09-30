import json
from server import notify, weather


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and "wheat" in r.json()["crops"]


def test_forecast_shape(client, mock_api):
    r = client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6, "block_lat": 22.9, "block_lng": 75.7, "crop": "wheat"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["daily"]) == 7 and len(j["hourly"]) <= 24 and j["now"]
    assert j["location"]["elevation_m"] == 585.0
    assert j["local_adjustment"]["available"] and j["local_adjustment"]["elevation_diff_m"] == 65
    assert j["local_adjustment"]["height_effect_c"] == -0.4  # 65 m higher -> about 0.4 C cooler
    assert len(j["confidence"]) == 7 and j["confidence"][3]["rain_max"] == 70
    assert any(a["kind"] == "heavy_rain" for a in j["advisories"])
    assert j["meta"]["stale"] is False and j["meta"]["crop"] == "wheat"
    assert j["daily"][0]["humidity"] == 60


def test_hourly_starts_at_current_hour(client):
    from datetime import datetime, timedelta, timezone
    j = client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6}).json()
    local = datetime.now(timezone.utc) + timedelta(seconds=19800)
    assert j["hourly"][0]["time"] == local.strftime("%Y-%m-%dT%H:00")


def test_second_model_and_block_are_optional(client, mock_api):
    mock_api["fail_models"] = True
    j = client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6}).json()
    assert j["confidence"] == [] and j["local_adjustment"] == {"available": False} and j["block_daily"] == []


def test_cache_prevents_repeat_calls(client, mock_api):
    client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6})
    n = len(mock_api["calls"])
    client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6, "crop": "rice"})
    assert len(mock_api["calls"]) == n


def test_stale_fallback_then_503(client, mock_api):
    client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6})
    weather._fresh.clear()
    mock_api["fail"] = True
    j = client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6}).json()
    assert j["meta"]["stale"] is True
    r = client.get("/api/forecast", params={"lat": 25.0, "lng": 80.0})
    assert r.status_code == 503


def test_validation(client):
    assert client.get("/api/forecast", params={"lat": 51, "lng": 75}).status_code == 422
    assert client.get("/api/forecast", params={"lat": 22}).status_code == 422
    j = client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6, "crop": "bogus"}).json()
    assert j["meta"]["crop"] == "general"


def test_subscribe_validates_and_previews(client, tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "STORE", tmp_path / "subs.json")
    body = {"channel": "sms", "contact": "98765 43210", "code": "140096", "name": "Agra", "lat": 22.8, "lng": 75.6, "lang": "hi"}
    r = client.post("/api/alerts/subscribe", json=body)
    assert r.status_code == 200 and r.json()["demo"] and r.json()["preview"].startswith("KisanMausam - Agra")
    saved = json.loads((tmp_path / "subs.json").read_text())
    assert saved[0]["contact"] == "+919876543210"
    assert client.post("/api/alerts/subscribe", json={**body, "contact": "12345"}).status_code == 422
    assert client.post("/api/alerts/subscribe", json={**body, "channel": "email", "contact": "a@b.in"}).status_code == 200
    u = client.post("/api/alerts/unsubscribe", json={"channel": "sms", "contact": "9876543210", "code": "140096"})
    assert u.json()["removed"] == 1


def test_compose_truncates_and_handles_no_alerts():
    assert "No warnings" in notify.compose("X", [], "en")
    assert "कोई चेतावनी नहीं" in notify.compose("X", [], "hi")
    long = [{"severity": "danger", "title_en": "T", "title_hi": "T", "message_en": "m" * 500, "message_hi": "m", "valid_from": "2026-10-01"}]
    assert len(notify.compose("X", long, "en")) <= 300


def test_rate_limit(client):
    from server import main
    main.LIMIT = 3
    try:
        codes = [client.get("/api/forecast", params={"lat": 22.8, "lng": 75.6}).status_code for _ in range(5)]
    finally:
        main.LIMIT = 90
    assert 429 in codes
