# Open-Meteo migration

KisanMausam now uses the Open-Meteo Forecast API instead of Google Weather API.

- No Google Weather API key is required.
- Primary forecast: Open-Meteo `best_match`.
- Confidence comparison: Open-Meteo `ecmwf_ifs025`.
- Forecast data includes current/hourly conditions and 7-day daily data.
- The existing advisory, alert, crop, graph, multilingual, and frontend response shapes are preserved.
- `server/.env` may still contain `GROQ_API_KEY` for crop-specific AI advice; never commit real secrets.
