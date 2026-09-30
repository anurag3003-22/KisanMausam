import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ArrowLeft, Bell, CloudOff, Droplets, Gauge, Info, RefreshCw, Thermometer, Wind } from 'lucide-react';
import { Area, Bar, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useTranslation } from 'react-i18next';
import AdviceCard from '../components/AdviceCard';
import { getForecast } from '../lib/api';
import { notifyNewAlerts } from '../lib/notify';
import { CROPS, type Crop, type Forecast, type Lang, type Panchayat } from '../lib/types';
import { SEV, advisoryIcon, fmtDay, fmtNum, pick, timeAgo, wxInfo } from '../lib/weather';

const CROP_KEY = 'km.crop';
const lastCrop = (): Crop => { try { const c = localStorage.getItem(CROP_KEY); return (CROPS as readonly string[]).includes(c ?? '') ? (c as Crop) : 'general'; } catch { return 'general'; } };

export default function Dashboard({ p, onBack, onAlerts }: { p: Panchayat; onBack: () => void; onAlerts: () => void }) {
  const { t, i18n } = useTranslation();
  const lang: Lang = (i18n.language.split('-')[0] as Lang) || 'en';
  const [crop, setCrop] = useState<Crop>(lastCrop);
  const [f, setF] = useState<Forecast | null>(null);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [chartMetric, setChartMetric] = useState<'temp' | 'rain' | 'humidity' | 'wind'>('temp');
  const seq = useRef(0);

  const load = useCallback(async () => {
    const my = ++seq.current;
    setBusy(true); setErr('');
    try {
      const r = await getForecast(p, crop);
      if (my !== seq.current) return;
      setF(r.data); setCachedAt(r.cached ? r.cachedAt ?? '' : null);
      if (!r.cached && !r.data.meta.stale) void notifyNewAlerts(p.name, r.data.alerts, lang);
    } catch (e) {
      if (my === seq.current) setErr(e instanceof Error ? e.message : t('dash.error'));
    } finally { if (my === seq.current) setBusy(false); }
  }, [p, crop, lang, t]);
  useEffect(() => { void load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [p.code, crop]);
  useEffect(() => { try { localStorage.setItem(CROP_KEY, crop); } catch { /* ignore */ } }, [crop]);

  const today = f?.daily[0];
  const topToday = useMemo(() => {
    if (!f || !today) return null;

    const day = f.advisories.filter(
      (a) => a.valid_from <= today.date && today.date <= a.valid_to
    );

    if (!day.length) return null;

    // Safety advisories always take priority. Among normal/info items,
    // prefer Groq's crop-specific advice over the generic weather message.
    const safety = day.filter((a) => SEV[a.severity].rank > SEV.info.rank);
    if (safety.length) {
      return safety.reduce((m, a) =>
        SEV[a.severity].rank > SEV[m.severity].rank ? a : m
      );
    }

    const ai = day.find((a) => a.kind === 'ai_advisory');
    if (ai) return ai;

    return day.find((a) => a.kind !== 'good_weather') ?? day[0];
  }, [f, today]);

  return (
    <main className="mx-auto w-full max-w-5xl overflow-x-clip px-4 pb-36 pt-3 md:pb-12">
      <div className="flex items-center justify-between gap-2 py-2">
        <button onClick={onBack} className="btn btn-ghost !min-h-11 !px-3"><ArrowLeft size={18} aria-hidden />{t('dash.back')}</button>
        <button onClick={() => void load()} disabled={busy} className="btn btn-ghost !min-h-11 !px-3" aria-label={t('dash.refresh')}>
          <RefreshCw size={18} className={busy ? 'animate-spin' : ''} aria-hidden /><span className="hidden sm:inline">{t('dash.refresh')}</span>
        </button>
      </div>

      <header className="mb-3">
        <h1 className="text-3xl font-extrabold leading-tight">{p.name}</h1>
        <p className="text-slate-600">{p.block} · {p.district} · {p.state}</p>
        <p className="mt-0.5 text-xs text-slate-500">{t('dash.code', { sys: p.codeSystem, code: p.code })}{p.area ? ` · ${t('dash.area', { a: p.area })}` : ''}</p>
      </header>

      <div role="group" aria-label={t('dash.crop')} className="strip -mx-1 mb-4 flex gap-2 overflow-x-auto px-1 pb-2">
        {CROPS.map((c) => (
          <button key={c} aria-pressed={crop === c} onClick={() => setCrop(c)}
            className={`btn !min-h-11 shrink-0 !px-4 text-sm ${crop === c ? 'btn-primary' : 'btn-ghost'}`}>{t(`crop.${c}`)}</button>
        ))}
      </div>

      {(cachedAt !== null || f?.meta.stale) && (
        <div role="status" className="mb-3 flex items-start gap-2 rounded-2xl bg-amber-50 p-3 text-sm text-amber-900">
          <CloudOff size={18} className="mt-0.5 shrink-0" aria-hidden />
          <span>{cachedAt ? t('dash.offline', { when: cachedAt ? timeAgo(cachedAt, lang) : '' }) : t('dash.stale')}</span>
        </div>
      )}

      {!f && !err && (
        <div role="status" aria-live="polite" className="grid gap-3">
          <span className="sr-only">{t('dash.loading')}</span>
          <div className="skeleton h-52" /><div className="skeleton h-28" /><div className="skeleton h-40" />
        </div>
      )}
      {err && !f && (
        <div role="alert" className="card p-6 text-center">
          <CloudOff className="mx-auto text-slate-400" size={40} aria-hidden />
          <p className="mt-2 text-lg font-bold">{t('dash.error')}</p>
          <p className="text-slate-600">{t('dash.errorHint')}</p>
          <p className="mt-1 text-xs text-slate-400">{err}</p>
          <button className="btn btn-primary mt-4" onClick={() => void load()}><RefreshCw size={18} aria-hidden />{t('dash.refresh')}</button>
        </div>
      )}

      {f && today && (
        <div className="grid grid-cols-1 gap-4 [&>*]:min-w-0">
          {topToday && <AdviceCard a={topToday} place={p.name} lang={lang} crop={crop} />}

          <AlertsBanner f={f} lang={lang} onAlerts={onAlerts} />

          <section className="card p-5" aria-labelledby="now-h">
            <div className="flex items-baseline justify-between">
              <h2 id="now-h" className="text-lg font-extrabold">{t('dash.now')}</h2>
              <span className="text-xs text-slate-500">{t('dash.updated', { when: timeAgo(f.meta.updated_at, lang) })}</span>
            </div>
            <div className="mt-2 flex items-center gap-4">
              {(() => { const w = wxInfo(f.now?.code ?? today.code); const I = w.icon; return (<><I size={64} className={w.tone} aria-hidden /><div><div className="text-5xl font-black leading-none">{fmtNum(f.now?.temp ?? today.max_temp)}°</div><div className="mt-1 font-semibold text-slate-600">{t(w.key)}</div></div></>); })()}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric icon={<Thermometer size={20} />} label={t('dash.feels')} value={`${fmtNum(today.min_temp)}–${fmtNum(today.max_temp)}°C`} />
              <Metric icon={<Droplets size={20} />} label={t('dash.rainToday')} value={`${fmtNum(today.rain, 1)} ${t('dash.unit.mm')}`} sub={t('dash.chance', { p: fmtNum(today.rain_prob) })} />
              <Metric icon={<Wind size={20} />} label={t('dash.wind')} value={`${fmtNum(f.now?.wind ?? today.wind_max)} km/h`} sub={t('dash.gusts', { g: fmtNum(today.gust) })} />
              <Metric icon={<Gauge size={20} />} label={t('dash.humidity')} value={`${fmtNum(f.now?.humidity ?? today.humidity)}%`} />
            </div>
          </section>

          <section className="card p-5" aria-labelledby="fc-h">
            <h2 id="fc-h" className="mb-3 text-lg font-extrabold">{t('dash.forecast')}</h2>
            <div className="strip -mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
              {f.daily.map((d, i) => {
                const w = wxInfo(d.code); const I = w.icon;
                const a = f.advisories.filter((x) => x.valid_from <= d.date && d.date <= x.valid_to).reduce<Forecast['advisories'][number] | null>((m, x) => (!m || SEV[x.severity].rank > SEV[m.severity].rank ? x : m), null);
                const conf = f.confidence.find((c) => c.date === d.date);
                return (
                  <div key={d.date} className={`min-w-[6.6rem] flex-1 rounded-2xl border p-3 text-center ${a ? SEV[a.severity].card : 'border-leaf-100 bg-leaf-50'}`}>
                    <div className="text-sm font-bold">{i === 0 ? t('dash.today.short') : fmtDay(d.date, lang, { weekday: 'short' })}</div>
                    <div className="text-xs text-slate-500">{fmtDay(d.date, lang, { day: 'numeric', month: 'short' })}</div>
                    <I size={34} className={`mx-auto my-2 ${w.tone}`} aria-label={t(w.key)} />
                    <div className="font-extrabold">{fmtNum(d.max_temp)}° <span className="font-semibold text-slate-500">{fmtNum(d.min_temp)}°</span></div>
                    <div className="mt-1 flex items-center justify-center gap-1 text-sm font-semibold text-sky-700"><Droplets size={14} aria-hidden />{fmtNum(d.rain, 1)} {t('dash.unit.mm')}</div>
                    <div className="text-xs text-slate-500"><Wind className="mr-0.5 inline" size={12} aria-hidden />{fmtNum(d.gust)}</div>
                    {conf && <div className="mt-1 text-[11px] text-slate-500">{t('dash.confidence')}: <b>{t(`dash.${conf.level}`)}</b></div>}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="card overflow-hidden p-5" aria-labelledby="hr-h">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="hr-h" className="text-lg font-extrabold">{t('dash.hourly')}</h2>
                <p className="mt-1 text-sm text-slate-500">{t('dash.chartHint')}</p>
              </div>
              <div className="flex flex-wrap gap-1 rounded-2xl bg-leaf-50 p-1" role="tablist" aria-label={t('dash.chartMetrics')}>
                {([
                  ['temp', 'dash.chartTemp'],
                  ['rain', 'dash.chartRain'],
                  ['humidity', 'dash.chartHumidity'],
                  ['wind', 'dash.chartWind'],
                ] as const).map(([id, key]) => (
                  <button
                    key={id}
                    role="tab"
                    aria-selected={chartMetric === id}
                    onClick={() => setChartMetric(id)}
                    className={`rounded-xl px-3 py-2 text-xs font-bold transition ${chartMetric === id ? 'bg-white text-leaf-800 shadow-sm' : 'text-slate-600 hover:bg-white/70'}`}
                  >
                    {t(key)}
                  </button>
                ))}
              </div>
            </div>

            {(() => {
              const chartData = f.hourly.map((h) => ({
                ...h,
                hour: h.time.slice(11, 16),
              }));
              const meta = {
                temp: { key: 'temp', label: t('dash.chartTemp'), unit: '°C', color: '#e8590c' },
                rain: { key: 'rain', label: t('dash.chartRain'), unit: ' mm', color: '#3b82c4' },
                humidity: { key: 'humidity', label: t('dash.chartHumidity'), unit: '%', color: '#2f7d32' },
                wind: { key: 'wind', label: t('dash.chartWind'), unit: ' km/h', color: '#7a5a3a' },
              }[chartMetric];
              const values = chartData.map((d) => Number(d[meta.key as keyof typeof d])).filter((v) => Number.isFinite(v));
              const current = values.length ? values[0] : null;
              const min = values.length ? Math.min(...values) : null;
              const max = values.length ? Math.max(...values) : null;
              return (
                <>
                  <div className="mt-4 grid grid-cols-3 gap-2">
                    <div className="rounded-2xl bg-slate-50 p-3">
                      <div className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{t('dash.chartCurrent')}</div>
                      <div className="mt-1 text-lg font-extrabold">{current == null ? '–' : `${fmtNum(current, chartMetric === 'rain' ? 1 : 0)}${meta.unit}`}</div>
                    </div>
                    <div className="rounded-2xl bg-slate-50 p-3">
                      <div className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{t('dash.chartMin')}</div>
                      <div className="mt-1 text-lg font-extrabold">{min == null ? '–' : `${fmtNum(min, chartMetric === 'rain' ? 1 : 0)}${meta.unit}`}</div>
                    </div>
                    <div className="rounded-2xl bg-slate-50 p-3">
                      <div className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{t('dash.chartMax')}</div>
                      <div className="mt-1 text-lg font-extrabold">{max == null ? '–' : `${fmtNum(max, chartMetric === 'rain' ? 1 : 0)}${meta.unit}`}</div>
                    </div>
                  </div>
                  <div className="mt-3 h-64 w-full" role="img" aria-label={`${meta.label}, ${t('dash.hourly')}`}>
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={chartData} margin={{ top: 12, right: 8, bottom: 4, left: -10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e6eee2" vertical={false} />
                        <XAxis dataKey="hour" interval={2} tick={{ fontSize: 11 }} tickMargin={8} />
                        <YAxis
                          tick={{ fontSize: 11 }}
                          width={48}
                          tickFormatter={(v) => `${v}${meta.unit.trim()}`}
                          domain={['auto', 'auto']}
                        />
                        <Tooltip
                          labelFormatter={(label) => `${t('dash.time')}: ${label}`}
                          formatter={(value) => [
                            `${fmtNum(Number(Array.isArray(value) ? value[0] : value), chartMetric === 'rain' ? 1 : 0)}${meta.unit}`,
                            meta.label,
                          ]}
                          contentStyle={{ borderRadius: 14, border: '1px solid #dbe7d5', boxShadow: '0 8px 24px rgba(30,70,35,.12)' }}
                        />
                        {chartMetric === 'rain' ? (
                          <Bar dataKey="rain" name={meta.label} fill={meta.color} radius={[6, 6, 0, 0]} maxBarSize={22} />
                        ) : (
                          <Area
                            type="monotone"
                            dataKey={chartMetric}
                            name={meta.label}
                            stroke={meta.color}
                            fill={meta.color}
                            fillOpacity={0.10}
                            strokeWidth={3}
                            dot={{ r: 2 }}
                            activeDot={{ r: 5 }}
                          />
                        )}
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </>
              );
            })()}
          </section>

          <section className="card p-5" aria-labelledby="wk-h">
            <h2 id="wk-h" className="mb-3 text-lg font-extrabold">{t('dash.week')}</h2>
            <ul className="grid gap-2">
              {f.advisories.filter((a) => a.kind !== 'good_weather' || a.valid_from === today.date).map((a) => {
                const I = advisoryIcon(a.icon);
                return (
                  <li key={a.id} className={`flex gap-3 rounded-2xl border p-3 ${SEV[a.severity].card}`}>
                    <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white ${SEV[a.severity].ring}`}><I size={22} aria-hidden /></span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-sm">
                        <b>{fmtDay(a.valid_from, lang, { weekday: 'short', day: 'numeric', month: 'short' })}{a.valid_to !== a.valid_from ? ` – ${fmtDay(a.valid_to, lang, { day: 'numeric', month: 'short' })}` : ''}</b>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${SEV[a.severity].chip}`}>{t(`sev.${a.severity}`)}</span>
                      </div>
                      <div className="font-extrabold">{pick(a as never, 'title', lang)}</div>
                      <p className="text-[15px]">{pick(a as never, 'message', lang)}</p>
                      {a.crop_tip_en && <p className="mt-1 text-sm text-slate-700"><b>{t(`crop.${crop}`)}:</b> {pick(a as never, 'crop_tip', lang)}</p>}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          <HowCard f={f} p={p} />
        </div>
      )}
    </main>
  );
}

function Metric({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl bg-leaf-50 p-3">
      <div className="text-leaf-700" aria-hidden>{icon}</div>
      <div className="mt-1 text-xs font-semibold text-slate-500">{label}</div>
      <div className="text-lg font-extrabold leading-tight">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

function AlertsBanner({ f, lang, onAlerts }: { f: Forecast; lang: Lang; onAlerts: () => void }) {
  const { t } = useTranslation();
  const list = f.alerts;
  const worst = list.reduce<number>((m, a) => Math.max(m, SEV[a.severity].rank), 0);
  return (
    <button onClick={onAlerts} className={`card flex w-full items-center gap-3 p-4 text-left ${list.length ? SEV[worst >= 3 ? 'danger' : 'warning'].card : ''}`}>
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white shadow">{list.length ? <AlertTriangle className="text-orange-600" aria-hidden /> : <Bell className="text-leaf-700" aria-hidden />}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-extrabold">{t('dash.alertsTitle')}</span>
        <span className="block text-sm text-slate-700">{list.length ? list.slice(0, 2).map((a) => `${fmtDay(a.valid_from, lang, { weekday: 'short' })}: ${pick(a as never, 'title', lang)}`).join(' · ') : t('dash.noAlerts')}</span>
      </span>
      <span className="text-sm font-bold text-leaf-700">{t('dash.seeAlerts')} ›</span>
    </button>
  );
}

function HowCard({ f, p }: { f: Forecast; p: Panchayat }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const la = f.local_adjustment;
  const d0 = la.days?.[0];
  return (
    <section className="card p-5">
      <button className="flex w-full items-center gap-2 text-left" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Info className="text-leaf-700" size={20} aria-hidden /><span className="flex-1 font-extrabold">{t('dash.how')}</span><span aria-hidden>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="fade-in mt-3 grid gap-2 text-[15px]">
          <ol className="list-decimal space-y-1 pl-5">{[1, 2, 3, 4, 5].map((n) => <li key={n}>{t(`dash.how${n}`)}</li>)}</ol>
          {la.available && (
            <div className="mt-2 rounded-2xl bg-leaf-50 p-3 text-sm">
              <div className="font-bold">{t('dash.vsBlock')} ({p.block})</div>
              {la.panchayat_elevation_m != null && la.block_elevation_m != null && <p>{t('dash.elev', { a: Math.round(la.panchayat_elevation_m), b: Math.round(la.block_elevation_m) })}</p>}
              {la.height_effect_c != null && la.height_effect_c !== 0 && <p>{t('dash.elevEffect', { c: la.height_effect_c })}</p>}
              {d0 && (d0.max_temp_diff || d0.rain_diff) ? <p>{fmtNum(d0.max_temp_diff, 1)} °C · {fmtNum(d0.rain_diff, 1)} mm</p> : <p>{t('dash.vsSame')}</p>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
