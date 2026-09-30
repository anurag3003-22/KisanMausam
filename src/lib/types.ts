export type Lang = 'en' | 'hi' | 'bn' | 'gu' | 'mr' | 'ta' | 'te' | 'kn' | 'ml' | 'pa' | 'or' | 'as' | 'ur';
export type Severity = 'info' | 'watch' | 'warning' | 'danger';

export interface StateMeta {
  slug: string; name: string; count: number; districts: number; blocks: number;
  source: 'lgd' | 'bhuvan' | 'csv'; code_system: string; bbox: [number, number, number, number]; bytes: number;
}
export interface Manifest {
  generated: string; total_panchayats: number; states: StateMeta[];
  sources: { id: string; name: string; license: string; note: string }[]; note: string;
}

export interface Panchayat {
  code: string; name: string; block: string; district: string; state: string; stateSlug: string;
  lat: number; lng: number; area: number; blockLat: number; blockLng: number; codeSystem: string;
}
export interface BlockIdx { name: string; district: string; lat: number; lng: number; gps: Panchayat[] }
export interface DistrictIdx { name: string; lat: number; lng: number; blocks: BlockIdx[]; count: number }
export interface StateIdx { meta: StateMeta; districts: DistrictIdx[]; all: Panchayat[]; lower: string[] }

export interface HourPoint { time: string; temp: number | null; humidity: number | null; rain_prob: number; rain: number; wind: number; code: number }
export interface DayPoint {
  date: string; min_temp: number | null; max_temp: number | null; rain: number; rain_prob: number;
  gust: number; wind_max: number; humidity: number | null; code: number;
}
export interface Advisory {
  id: string; kind: string; category: string; severity: Severity; icon: string;
  title_en: string; title_hi: string; message_en: string; message_hi: string;
  crop: string | null; crop_tip_en: string | null; crop_tip_hi: string | null;
  valid_from: string; valid_to: string; source?: string;
}
export interface Confidence {
  date: string; rain_min: number; rain_likely: number; rain_max: number;
  tmax_min: number | null; tmax_likely: number | null; tmax_max: number | null; level: 'high' | 'medium' | 'low';
}
export interface LocalAdjustment {
  available: boolean; block_elevation_m?: number | null; panchayat_elevation_m?: number | null;
  elevation_diff_m?: number | null; height_effect_c?: number | null;
  days?: { date: string; max_temp_diff: number | null; min_temp_diff: number | null; rain_diff: number | null }[];
}
export interface Forecast {
  location: { lat: number; lng: number; elevation_m: number | null; timezone: string | null };
  now: HourPoint | null; daily: DayPoint[]; hourly: HourPoint[]; confidence: Confidence[];
  local_adjustment: LocalAdjustment; block_daily: DayPoint[]; advisories: Advisory[]; alerts: Advisory[];
  meta: { source: string; second_model: string | null; updated_at: string; stale: boolean; crop: string; demo?: boolean };
}
export const CROPS = ['general', 'wheat', 'rice', 'maize', 'soybean', 'cotton', 'sugarcane', 'pulses', 'vegetables'] as const;
export type Crop = (typeof CROPS)[number];
