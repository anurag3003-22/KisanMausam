import type { BlockIdx, DistrictIdx, Manifest, Panchayat, StateIdx, StateMeta } from './types';

const BASE = import.meta.env.BASE_URL;
let manifestP: Promise<Manifest> | null = null;
const stateCache = new Map<string, Promise<StateIdx>>();

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Could not load ${url} (${r.status})`);
  return r.json() as Promise<T>;
}

export function loadManifest(): Promise<Manifest> {
  if (!manifestP) manifestP = getJson<Manifest>(`${BASE}data/manifest.json`).catch((e) => { manifestP = null; throw e; });
  return manifestP;
}

interface RawState { state: string; slug: string; source: string; count: number; d: { n: string; b: { n: string; lat: number; lng: number; g: [string, string, number, number, number][] }[] }[] }

export function loadState(meta: StateMeta): Promise<StateIdx> {
  let p = stateCache.get(meta.slug);
  if (!p) {
    p = getJson<RawState>(`${BASE}data/states/${meta.slug}.json`).then((raw) => indexState(meta, raw));
    p.catch(() => stateCache.delete(meta.slug));
    stateCache.set(meta.slug, p);
  }
  return p;
}

function indexState(meta: StateMeta, raw: RawState): StateIdx {
  const all: Panchayat[] = [];
  const districts: DistrictIdx[] = raw.d.map((d) => {
    const blocks: BlockIdx[] = d.b.map((b) => {
      const gps: Panchayat[] = b.g.map(([name, code, lat, lng, area]) => ({
        code, name, block: b.n, district: d.n, state: meta.name, stateSlug: meta.slug, lat, lng, area,
        blockLat: b.lat, blockLng: b.lng, codeSystem: meta.code_system,
      }));
      all.push(...gps);
      return { name: b.n, district: d.n, lat: b.lat, lng: b.lng, gps };
    });
    const count = blocks.reduce((s, b) => s + b.gps.length, 0);
    return {
      name: d.n, blocks, count,
      lat: blocks.reduce((s, b) => s + b.lat, 0) / blocks.length,
      lng: blocks.reduce((s, b) => s + b.lng, 0) / blocks.length,
    };
  });
  return { meta, districts, all, lower: all.map((p) => p.name.toLowerCase()) };
}

/** Search Panchayat names (or LGD code) inside one state. Prefix matches rank first. */
export function searchState(idx: StateIdx, query: string, limit = 40): Panchayat[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const starts: Panchayat[] = [];
  const contains: Panchayat[] = [];
  const isCode = /^\d+$/.test(q);
  for (let i = 0; i < idx.all.length; i++) {
    const p = idx.all[i];
    if (isCode) {
      if (p.code.startsWith(q) && starts.length < limit) starts.push(p);
    } else {
      const n = idx.lower[i];
      if (n.startsWith(q)) { if (starts.length < limit) starts.push(p); }
      else if (contains.length < limit && n.includes(q)) contains.push(p);
    }
    if (starts.length >= limit) break;
  }
  return starts.concat(contains).slice(0, limit);
}

const rad = Math.PI / 180;
/** Approximate distance in km (equirectangular; fine for "nearest" ranking). */
export function distKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const x = (lng2 - lng1) * Math.cos(((lat1 + lat2) / 2) * rad);
  const y = lat2 - lat1;
  return Math.hypot(x, y) * 111.195;
}

export function nearest(list: Panchayat[], lat: number, lng: number): { p: Panchayat; km: number } | null {
  let best: Panchayat | null = null;
  let bd = Infinity;
  for (const p of list) {
    const d = (p.lat - lat) ** 2 + ((p.lng - lng) * Math.cos(lat * rad)) ** 2;
    if (d < bd) { bd = d; best = p; }
  }
  return best ? { p: best, km: distKm(lat, lng, best.lat, best.lng) } : null;
}

/** States whose bounding box contains the point, nearest bbox centre first; falls back to the closest state. */
export function statesForPoint(m: Manifest, lat: number, lng: number): StateMeta[] {
  const centre = (s: StateMeta) => distKm(lat, lng, (s.bbox[1] + s.bbox[3]) / 2, (s.bbox[0] + s.bbox[2]) / 2);
  const inside = m.states.filter((s) => lng >= s.bbox[0] - 0.05 && lng <= s.bbox[2] + 0.05 && lat >= s.bbox[1] - 0.05 && lat <= s.bbox[3] + 0.05);
  const pool = inside.length ? inside : [...m.states].sort((a, b) => centre(a) - centre(b)).slice(0, 2);
  return pool.sort((a, b) => centre(a) - centre(b));
}

/** Resolve the closest Panchayat anywhere in India by loading only the candidate state files. */
export async function nearestAnywhere(m: Manifest, lat: number, lng: number): Promise<{ p: Panchayat; km: number } | null> {
  let best: { p: Panchayat; km: number } | null = null;
  for (const s of statesForPoint(m, lat, lng).slice(0, 3)) {
    const idx = await loadState(s);
    const n = nearest(idx.all, lat, lng);
    if (n && (!best || n.km < best.km)) best = n;
  }
  return best;
}

export const STORE_KEY = 'km.selected';
export const RECENT_KEY = 'km.recent';
export function saveSelected(p: Panchayat) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(p));
    const recent = loadRecent().filter((r) => r.code !== p.code);
    localStorage.setItem(RECENT_KEY, JSON.stringify([p, ...recent].slice(0, 5)));
  } catch { /* private mode: ignore */ }
}
export function loadSelected(): Panchayat | null {
  try { const v = localStorage.getItem(STORE_KEY); return v ? (JSON.parse(v) as Panchayat) : null; } catch { return null; }
}
export function loadRecent(): Panchayat[] {
  try { const v = localStorage.getItem(RECENT_KEY); return v ? (JSON.parse(v) as Panchayat[]) : []; } catch { return []; }
}

export function fmtCount(n: number, lang: 'en' | 'hi'): string {
  return new Intl.NumberFormat(lang === 'hi' ? 'hi-IN' : 'en-IN').format(n);
}
