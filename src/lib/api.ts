import type { Forecast, Panchayat } from './types';

const API = (import.meta.env.VITE_API_URL as string | undefined) || '';
const CACHE = 'km.fc.';

export interface ForecastResult { data: Forecast; cached: boolean; cachedAt?: string }

export async function getForecast(p: Panchayat, crop: string, signal?: AbortSignal): Promise<ForecastResult> {
  const qs = new URLSearchParams({ lat: String(p.lat), lng: String(p.lng), block_lat: String(p.blockLat), block_lng: String(p.blockLng), crop });
  const key = `${CACHE}${p.code}.${crop}`;
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 25000);
    signal?.addEventListener('abort', () => ctl.abort());
    const r = await fetch(`${API}/api/forecast?${qs}`, { signal: ctl.signal });
    clearTimeout(timer);
    if (!r.ok) {
      let detail = `Weather service error (${r.status})`;
      try { detail = (await r.json()).detail || detail; } catch { /* ignore */ }
      throw new Error(detail);
    }
    const data = (await r.json()) as Forecast;
    try { localStorage.setItem(key, JSON.stringify({ at: new Date().toISOString(), data })); } catch { /* quota */ }
    return { data, cached: false };
  } catch (err) {
    if (signal?.aborted) throw err;
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const { at, data } = JSON.parse(raw) as { at: string; data: Forecast };
        return { data, cached: true, cachedAt: at };
      }
    } catch { /* ignore */ }
    throw err instanceof Error ? err : new Error('Network error');
  }
}

export interface SubscribeBody {
  channel: 'sms' | 'email'; contact: string; code: string; name: string; lat: number; lng: number;
  block_lat: number; block_lng: number; lang: 'en' | 'hi'; crop: string;
}
export async function subscribe(body: SubscribeBody): Promise<{ preview: string; message: string }> {
  const r = await fetch(`${API}/api/alerts/subscribe`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Could not save. Check the details and try again.');
  return j;
}
