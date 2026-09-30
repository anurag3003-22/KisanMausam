# KisanMausam

Mobile-first web app that turns weather forecasts into **Panchayat-specific farm advice** for Indian farmers (Smart India Hackathon prototype).

*"Transform block-level weather forecast into Panchayat-specific, actionable agricultural advice using AI, helping farmers make better crop management decisions."*

## What it does
* **236,308 Panchayats, 33 states/UTs** (LGD + Bhuvan open data). Pick State → District → Block → Panchayat, search by name or code, use your GPS location, or tap the drill-down map. See `DATA_SOURCES.md` for exactly what is and is not covered.
* **7-day forecast + next 24 hours** per Panchayat (rain, temperature, wind gusts, humidity, weather icons) with a confidence level from a two-model comparison.
* **Advice engine** (rain / flood risk, dry spell, wind, heat, cold & frost, hail, thunderstorm) in **Hindi and English**, with **crop-specific tips** for 8 crops, read-aloud and WhatsApp share.
* **Alerts**: in-app list, browser notifications, and SMS/email subscription in **demo mode** (no real messages are sent).
* **PWA**: installable, offline shell, last forecast saved for offline viewing. Responsive, large touch targets, screen-reader friendly.

## Run it (Windows)
Requirements: Node.js LTS and Python 3.11+ (with "Add to PATH"). Internet is needed the first time.

1. Double-click **`START_KISANMAUSAM.bat`**. It installs packages, builds the site and starts one server.
2. The browser opens at **http://127.0.0.1:8000**. Keep the server window open.
3. **`STOP_KISANMAUSAM.bat`** stops it. After editing code, delete the `dist` folder and start again (or use `START_DEV.bat` for hot reload).

macOS/Linux: `./start.sh`.

Manual:
```bash
npm install && npm run build
python -m venv .venv && .venv/Scripts/pip install -r server/requirements.txt   # Linux/mac: .venv/bin/pip
.venv/Scripts/python -m uvicorn server.main:app --port 8000                    # run from this folder
```

## Test
```bash
npm run typecheck && npm test                 # TypeScript + frontend unit tests
pip install -r server/requirements-dev.txt && python -m pytest -q   # 20 backend tests (mocked Open-Meteo)
```

## Architecture
```
Browser (React + Tailwind + Leaflet, PWA)
   |  /data/manifest.json, /data/states/<state>.json   (static, loaded one state at a time)
   |  /api/forecast?lat&lng&block_lat&block_lng&crop
   v
FastAPI  --> weather.py  --> Open-Meteo (Panchayat point, block centre, 2nd model), 30-min cache, stale fallback
         --> downscale.py    height/local adjustment + model-spread confidence  (ML upgrade point)
         --> advisory.py     rules from advisory_rules.json + crop_advice.json
         --> notify.py       subscriptions + MOCK SMS/email
```

### How "downscaling" works today (honest version)
The forecast is requested for the **Panchayat's exact coordinates**; Open-Meteo corrects temperature for the difference between its model grid (about 10-25 km) and the point's terrain height. We also fetch the **block centre** and show the difference, and compare **two models** for a confidence range. This is a baseline, not a trained ML model. The planned upgrade is a gradient-boosting model trained on IMD/AWS station observations, plugged in at `downscale.trained_model_placeholder`.

## Rebuild or extend the Panchayat data
`python scripts/build_data.py` (downloads about 1.3 GB of open data once, needs `pip install pyarrow shapely numpy`), or `--csv` with an official LGD export.

## Add a language
Copy `src/i18n/en.json` to e.g. `mr.json`, translate, register it in `src/i18n/index.ts` and add a switch option in `Header.tsx`.

## Before real-world use
* Have a KVK / agriculture expert review `server/advisory_rules.json` and `server/crop_advice.json`.
* Connect a real SMS gateway in `server/notify.py` and a scheduler; today SMS/email are demo-only.
* Check Open-Meteo's terms for commercial use and consider an IMD data agreement.


## Groq crop-specific advice

The weather backend can generate crop-specific "Today's Advice" with Groq.
The Groq key stays on the Python server and is never sent to the React app.

1. Open `server/.env`.
2. Set `GROQ_API_KEY=your_groq_key`.
3. Keep `GROQ_MODEL=openai/gpt-oss-20b` unless you have a reason to change it.
4. Keep the Google Weather API key configured because it remains the source of live weather data.
5. Restart the backend after changing `.env`.

Groq receives the selected crop, live weather, forecast, and deterministic weather risks.
It returns structured JSON. If Groq is unavailable, the deterministic safety advisories still work.


## UI upgrade in this version

- Language selector now supports English, Hindi, Bengali, Gujarati, Marathi, Tamil, Telugu, Kannada, Malayalam, Punjabi, Odia, Assamese and Urdu.
- Urdu switches the document direction to RTL.
- Dashboard's 24-hour graph now has separate Temperature, Rain, Humidity and Wind views with current/min/max summaries and improved tooltips.
- Bottom navigation has a clearer active state, stronger contrast and a larger touch target.
- The app keeps English as the fallback when a dynamic advisory does not yet have a translation for the selected language.
