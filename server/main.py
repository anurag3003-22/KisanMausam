"""KisanMausam API (FastAPI).

Run from the project root:   python -m uvicorn server.main:app --port 8000
If a built frontend exists in ./dist it is served at http://127.0.0.1:8000/
"""
import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server import notify, weather
from server.advisory import CROPS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kisanmausam")

app = FastAPI(title="KisanMausam API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- tiny in-memory rate limit so a public demo cannot be used as a free proxy ---
_hits = defaultdict(deque)
LIMIT, WINDOW = 90, 60


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        ip = request.client.host if request.client else "?"
        q, now = _hits[ip], time.time()
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= LIMIT:
            return JSONResponse({"detail": "Too many requests. Please wait a minute."}, status_code=429)
        q.append(now)
    return await call_next(request)


# India bounding box (generous) - rejects obviously wrong coordinates
LAT = dict(ge=6.0, le=38.0)
LNG = dict(ge=67.0, le=98.0)


@app.get("/api/health")
def health():
    return {"ok": True, "crops": CROPS}


@app.get("/api/forecast")
async def forecast(
    lat: float = Query(..., **LAT),
    lng: float = Query(..., **LNG),
    block_lat: Optional[float] = Query(None, **LAT),
    block_lng: Optional[float] = Query(None, **LNG),
    crop: str = Query("general", max_length=20),
):
    if crop not in CROPS:
        crop = "general"
    try:
        return await weather.forecast_bundle(lat, lng, block_lat, block_lng, crop)
    except weather.WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Weather service unavailable ({exc}). Please try again shortly.")


class Subscription(BaseModel):
    channel: Literal["sms", "email"]
    contact: str = Field(..., max_length=120)
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=120)
    lat: float = Field(..., **LAT)
    lng: float = Field(..., **LNG)
    block_lat: Optional[float] = Field(None, **LAT)
    block_lng: Optional[float] = Field(None, **LNG)
    lang: Literal["en", "hi"] = "en"
    crop: str = Field("general", max_length=20)


@app.post("/api/alerts/subscribe")
async def subscribe(sub: Subscription):
    try:
        contact = notify.normalize_contact(sub.channel, sub.contact)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    crop = sub.crop if sub.crop in CROPS else "general"
    try:
        data = await weather.forecast_bundle(sub.lat, sub.lng, sub.block_lat, sub.block_lng, crop)
        preview = notify.compose(sub.name, data["alerts"], sub.lang)
    except weather.WeatherUnavailable:
        preview = notify.compose(sub.name, [], sub.lang)
    notify.subscribe({"channel": sub.channel, "contact": contact, "code": sub.code, "name": sub.name,
                      "lat": sub.lat, "lng": sub.lng, "block_lat": sub.block_lat, "block_lng": sub.block_lng,
                      "lang": sub.lang, "crop": crop})
    notify.send(sub.channel, contact, preview)
    return {"ok": True, "demo": True, "preview": preview,
            "message": "Saved. Demo mode: no real SMS/email is sent; the message below is what would be delivered."}


class Unsub(BaseModel):
    channel: Literal["sms", "email"]
    contact: str = Field(..., max_length=120)
    code: str = Field(..., max_length=20)


@app.post("/api/alerts/unsubscribe")
def unsubscribe(u: Unsub):
    try:
        contact = notify.normalize_contact(u.channel, u.contact)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "removed": notify.unsubscribe(contact, u.code)}


# Serve the built frontend (npm run build) from the same server - one process, no CORS, works offline-first.
DIST = Path(__file__).resolve().parent.parent / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="site")
else:
    @app.get("/")
    def root():
        return {"message": "KisanMausam API is running. Build the frontend with `npm run build` or run `npm run dev`."}
