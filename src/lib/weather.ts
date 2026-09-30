import {
  Cloud, CloudDrizzle, CloudFog, CloudHail, CloudLightning, CloudRain, CloudSun, Flame, Snowflake, Sun, Thermometer, Waves, Wind,
  type LucideIcon,
} from 'lucide-react';
import type { Lang, Severity } from './types';

/** WMO weather code -> icon + translation key */
export function wxInfo(code: number): { icon: LucideIcon; key: string; tone: string } {
  if (code === 0) return { icon: Sun, key: 'wx.clear', tone: 'text-amber-500' };
  if (code === 1 || code === 2) return { icon: CloudSun, key: 'wx.partly', tone: 'text-amber-500' };
  if (code === 3) return { icon: Cloud, key: 'wx.cloudy', tone: 'text-slate-500' };
  if (code === 45 || code === 48) return { icon: CloudFog, key: 'wx.fog', tone: 'text-slate-500' };
  if (code >= 51 && code <= 57) return { icon: CloudDrizzle, key: 'wx.drizzle', tone: 'text-sky-600' };
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return { icon: CloudRain, key: 'wx.rain', tone: 'text-sky-600' };
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return { icon: Snowflake, key: 'wx.snow', tone: 'text-cyan-600' };
  if (code === 96 || code === 99) return { icon: CloudHail, key: 'wx.hail', tone: 'text-indigo-600' };
  if (code === 95) return { icon: CloudLightning, key: 'wx.storm', tone: 'text-violet-600' };
  return { icon: Cloud, key: 'wx.cloudy', tone: 'text-slate-500' };
}

export function advisoryIcon(icon: string): LucideIcon {
  switch (icon) {
    case 'flood': return Waves;
    case 'rain': return CloudRain;
    case 'dry': return Sun;
    case 'wind': return Wind;
    case 'heat': return Flame;
    case 'cold': return Thermometer;
    case 'hail': return CloudHail;
    case 'storm': return CloudLightning;
    default: return Sun;
  }
}

export const SEV: Record<Severity, { card: string; chip: string; bar: string; ring: string; rank: number }> = {
  info: { card: 'bg-emerald-50 border-emerald-200', chip: 'bg-emerald-100 text-emerald-900', bar: 'bg-emerald-500', ring: 'text-emerald-700', rank: 0 },
  watch: { card: 'bg-amber-50 border-amber-300', chip: 'bg-amber-100 text-amber-900', bar: 'bg-amber-400', ring: 'text-amber-700', rank: 1 },
  warning: { card: 'bg-orange-50 border-orange-300', chip: 'bg-orange-100 text-orange-900', bar: 'bg-orange-500', ring: 'text-orange-700', rank: 2 },
  danger: { card: 'bg-red-50 border-red-300', chip: 'bg-red-100 text-red-900', bar: 'bg-red-600', ring: 'text-red-700', rank: 3 },
};

export function parseDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
}
const LOCALE: Record<Lang, string> = {
  en: 'en-IN', hi: 'hi-IN', bn: 'bn-IN', gu: 'gu-IN', mr: 'mr-IN', ta: 'ta-IN',
  te: 'te-IN', kn: 'kn-IN', ml: 'ml-IN', pa: 'pa-IN', or: 'or-IN', as: 'as-IN', ur: 'ur-IN',
};
export function fmtDay(iso: string, lang: Lang, opts: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(LOCALE[lang] ?? 'en-IN', opts).format(parseDate(iso));
}
export function fmtNum(n: number | null | undefined, digits = 0): string {
  return n == null || Number.isNaN(n) ? '–' : n.toFixed(digits);
}
export function timeAgo(iso: string, lang: Lang): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  const rtf = new Intl.RelativeTimeFormat((LOCALE[lang] ?? 'en-IN').split('-')[0], { numeric: 'auto' });
  if (mins < 60) return rtf.format(-mins, 'minute');
  if (mins < 60 * 24) return rtf.format(-Math.round(mins / 60), 'hour');
  return rtf.format(-Math.round(mins / 1440), 'day');
}
export function pick<T extends Record<string, unknown>>(o: T, base: string, lang: Lang): string {
  return String(o[`${base}_${lang}`] ?? o[`${base}_en`] ?? '');
}
