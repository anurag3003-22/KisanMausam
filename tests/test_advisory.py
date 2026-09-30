from server import advisory as adv


def day(**k):
    base = {"date": "2026-09-30", "rain": 0, "gust": 10, "max_temp": 30, "min_temp": 20, "code": 1}
    base.update(k)
    return base


def kinds(d, crop="general"):
    return {a["kind"] for a in adv.day_advisories(d, crop)}


def test_rain_bands():
    assert kinds(day(rain=20)) == {"moderate_rain"}
    assert kinds(day(rain=70)) == {"heavy_rain"}
    assert kinds(day(rain=130)) == {"flood_risk"}
    assert kinds(day(rain=15.5)) == set()


def test_heavy_rain_not_overwritten_by_wind():
    # old engine let wind replace rain; now both are reported and sorted by severity
    out = adv.build_advisories([day(rain=70, gust=45)] * 1)
    assert {a["kind"] for a in out} == {"heavy_rain", "strong_wind"}


def test_wind_heat_cold_thresholds():
    assert kinds(day(gust=41)) == {"strong_wind"}
    assert kinds(day(gust=70)) == {"gale"}
    assert kinds(day(max_temp=41)) == {"heat"}
    assert kinds(day(max_temp=46)) == {"severe_heat"}
    assert kinds(day(min_temp=4)) == {"cold"}
    assert kinds(day(min_temp=1)) == {"frost"}


def test_cold_message_uses_minimum_not_maximum_temperature():
    a = adv.day_advisories(day(min_temp=3, max_temp=28))[0]
    assert "3°C" in a["message_en"] and "28" not in a["message_en"]


def test_hail_and_thunderstorm():
    assert kinds(day(code=96)) == {"hail"}
    assert kinds(day(code=95)) == {"thunderstorm"}


def test_current_thunderstorm_overrides_good_today():
    import asyncio

    daily = [day(code=0)]
    current = {"code": 95, "temp": 34, "gust": 3}
    out = asyncio.run(adv.build_advisories(daily, "general", current=current))

    today = [a for a in out if a["valid_from"] == daily[0]["date"]]
    assert any(a["kind"] == "thunderstorm" for a in today)
    assert adv.top_for_day(out, daily[0]["date"])["kind"] == "thunderstorm"


def test_good_weather_and_sorting():
    out = adv.build_advisories([day(), day(date="2026-10-01", rain=70)])
    assert out[0]["kind"] == "good_weather"
    assert out[1]["kind"] == "heavy_rain"


def test_dry_spell_only_when_hot_and_dry():
    hot_dry = [day(date=f"2026-10-0{i}", max_temp=38, rain=0) for i in range(1, 8)]
    assert any(a["kind"] == "dry_spell" for a in adv.build_advisories(hot_dry))
    cool_dry = [day(date=f"2026-10-0{i}", max_temp=28, rain=0) for i in range(1, 8)]
    assert not any(a["kind"] == "dry_spell" for a in adv.build_advisories(cool_dry))


def test_crop_tip_attached_and_general_has_none():
    a = adv.build_advisories([day(rain=70)], "soybean")[0]
    assert a["crop"] == "soybean" and "waterlogging" in a["crop_tip_en"]
    assert adv.build_advisories([day(rain=70)], "general")[0]["crop_tip_en"] is None
    assert adv.build_advisories([day(rain=70)], "not-a-crop")[0]["crop_tip_en"] is None


def test_every_message_formats_and_has_both_languages():
    for key, k in adv.KINDS.items():
        for lang in ("en", "hi"):
            k[lang].format(rain=1, wind=1, temp=1, days=1)
        assert k["title_en"] and k["title_hi"]
    for crop, cats in adv.CROP_TIPS.items():
        if crop.startswith("_"):
            continue
        for cat, tip in cats.items():
            assert tip["en"] and tip["hi"], (crop, cat)


def test_alerts_filter():
    out = adv.build_advisories([day(rain=20), day(date="2026-10-01", rain=70), day(date="2026-10-05", rain=70)])
    got = adv.alerts(out, ["2026-09-30", "2026-10-01"])
    assert [a["kind"] for a in got] == ["heavy_rain"]
