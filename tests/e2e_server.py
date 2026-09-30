"""Serve the built site + API with a MOCKED weather feed (for offline UI testing only)."""
import sys
from pathlib import Path
import httpx
import uvicorn
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import make_payload  # noqa: E402
from server import notify, weather  # noqa: E402

MODE = {"fail": False}

def handler(request: httpx.Request):
    if MODE["fail"]:
        return httpx.Response(500, json={})
    p = dict(request.url.params)
    light = "hourly" not in p
    if p.get("models"):
        return httpx.Response(200, json=make_payload(elevation=430, rain=[0, 3, 20, 40, 0, 0, 0], light=True))
    lat = float(p["latitude"])
    return httpx.Response(200, json=make_payload(elevation=430 + (lat % 1) * 100, light=light,
                                                  tmin=[22, 21, 20, 20, 3, 21, 22], code=[1, 3, 61, 65, 2, 0, 0]))

weather._transport = httpx.MockTransport(handler)
notify.STORE = Path("/tmp/km_subs.json")
if __name__ == "__main__":
    from server.main import app
    from fastapi import Response
    def toggle(on: int):
        MODE["fail"] = bool(on); weather._fresh.clear(); return {"fail": MODE["fail"]}
    app.add_api_route("/__fail/{on}", toggle, methods=["GET"])
    app.router.routes.insert(0, app.router.routes.pop())  # must come before the "/" static mount
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
