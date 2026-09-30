import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Bell, BellRing, Check, Loader2, Mail, Smartphone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getForecast, subscribe } from '../lib/api';
import { notificationsSupported, showNotification } from '../lib/notify';
import type { Forecast, Lang, Panchayat } from '../lib/types';
import { SEV, advisoryIcon, fmtDay, pick } from '../lib/weather';

export default function Alerts({ p, onBack }: { p: Panchayat; onBack: () => void }) {
  const { t, i18n } = useTranslation();
  const lang: Lang = i18n.language === 'hi' ? 'hi' : 'en';
  const [f, setF] = useState<Forecast | null>(null);
  const [failed, setFailed] = useState(false);
  const [perm, setPerm] = useState<NotificationPermission | 'unsupported'>(notificationsSupported() ? Notification.permission : 'unsupported');
  const [channel, setChannel] = useState<'sms' | 'email'>('sms');
  const [contact, setContact] = useState('');
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<{ ok: boolean; text: string; preview?: string } | null>(null);
  const crop = (() => { try { return localStorage.getItem('km.crop') || 'general'; } catch { return 'general'; } })();

  const load = useCallback(() => {
    setFailed(false);
    getForecast(p, crop).then((r) => setF(r.data)).catch(() => setFailed(true));
  }, [p, crop]);
  useEffect(load, [load]);

  async function enable() {
    if (!notificationsSupported()) return;
    setPerm(await Notification.requestPermission());
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setRes(null);
    try {
      const notifyLang: 'en' | 'hi' = lang === 'hi' ? 'hi' : 'en';
      const r = await subscribe({ channel, contact, code: p.code, name: p.name, lat: p.lat, lng: p.lng, block_lat: p.blockLat, block_lng: p.blockLng, lang: notifyLang, crop });
      setRes({ ok: true, text: r.message, preview: r.preview });
    } catch (err) { setRes({ ok: false, text: err instanceof Error ? err.message : 'Error' }); }
    finally { setBusy(false); }
  }

  return (
    <main className="mx-auto w-full overflow-x-clip max-w-3xl px-4 pb-28 pt-3 md:pb-10">
      <button onClick={onBack} className="btn btn-ghost !min-h-11 !px-3"><ArrowLeft size={18} aria-hidden />{t('nav.weather')}</button>
      <h1 className="mt-3 text-3xl font-extrabold">{t('alerts.title', { name: p.name })}</h1>
      <p className="text-slate-600">{t('alerts.desc')}</p>

      <section className="mt-4 grid gap-3" aria-live="polite">
        {!f && !failed && <div className="skeleton h-28" role="status" aria-label={t('dash.loading')} />}
        {failed && <div role="alert" className="card p-4">{t('dash.error')} <button className="font-bold text-leaf-700 underline" onClick={load}>{t('dash.refresh')}</button></div>}
        {f && f.alerts.length === 0 && <div className="card flex items-center gap-3 p-5"><Check className="text-leaf-700" aria-hidden />{t('alerts.none')}</div>}
        {f?.alerts.map((a) => {
          const I = advisoryIcon(a.icon);
          return (
            <article key={a.id} className={`card flex gap-3 border-2 p-4 ${SEV[a.severity].card}`}>
              <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-white ${SEV[a.severity].ring}`}><I size={26} aria-hidden /></span>
              <div>
                <div className="flex flex-wrap items-center gap-2 text-sm"><b>{fmtDay(a.valid_from, lang, { weekday: 'long', day: 'numeric', month: 'short' })}</b>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${SEV[a.severity].chip}`}>{t(`sev.${a.severity}`)}</span></div>
                <h2 className="text-lg font-extrabold">{pick(a as never, 'title', lang)}</h2>
                <p>{pick(a as never, 'message', lang)}</p>
                {a.crop_tip_en && <p className="mt-1 text-sm"><b>{t(`crop.${crop}`)}:</b> {pick(a as never, 'crop_tip', lang)}</p>}
              </div>
            </article>
          );
        })}
      </section>

      <section className="card mt-5 p-5">
        <h2 className="flex items-center gap-2 text-lg font-extrabold"><BellRing size={20} className="text-leaf-700" aria-hidden />{t('alerts.notify')}</h2>
        <p className="mt-1 text-slate-600">{t('alerts.notifyDesc')}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {perm === 'default' && <button className="btn btn-primary" onClick={() => void enable()}><Bell size={18} aria-hidden />{t('alerts.enable')}</button>}
          {perm === 'granted' && (<>
            <span className="inline-flex items-center gap-2 rounded-xl bg-leaf-50 px-3 font-bold text-leaf-800"><Check size={18} aria-hidden />{t('alerts.enabled')}</span>
            <button className="btn btn-ghost" onClick={() => void showNotification(t('alerts.testTitle'), t('alerts.testBody'), 'km-test')}>{t('alerts.test')}</button>
          </>)}
          {perm === 'denied' && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{t('alerts.blocked')}</p>}
          {perm === 'unsupported' && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{t('alerts.unsupported')}</p>}
        </div>
      </section>

      <section className="card mt-5 p-5">
        <h2 className="flex items-center gap-2 text-lg font-extrabold"><Smartphone size={20} className="text-leaf-700" aria-hidden />{t('alerts.sms')}</h2>
        <p className="mt-1 rounded-xl bg-amber-50 p-2.5 text-sm text-amber-900">{t('alerts.smsDemo')}</p>
        <form onSubmit={save} className="mt-3 grid gap-3">
          <fieldset><legend className="mb-1 text-sm font-bold">{t('alerts.sms.channel')}</legend>
            <div className="grid grid-cols-2 gap-2">
              {(['sms', 'email'] as const).map((c) => (
                <label key={c} className={`btn cursor-pointer border-2 ${channel === c ? 'border-leaf-600 bg-leaf-50 text-leaf-800' : 'border-leaf-100'}`}>
                  <input type="radio" name="ch" className="sr-only" checked={channel === c} onChange={() => { setChannel(c); setContact(''); setRes(null); }} />
                  {c === 'sms' ? <Smartphone size={18} aria-hidden /> : <Mail size={18} aria-hidden />}{t(`alerts.sms.${c}`)}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="grid gap-1"><span className="text-sm font-bold">{channel === 'sms' ? t('alerts.sms.phone') : t('alerts.sms.emailField')}</span>
            <input className="field" required value={contact} onChange={(e) => setContact(e.target.value)}
              type={channel === 'sms' ? 'tel' : 'email'} inputMode={channel === 'sms' ? 'numeric' : 'email'} autoComplete={channel === 'sms' ? 'tel-national' : 'email'}
              placeholder={channel === 'sms' ? '98765 43210' : 'name@example.com'} maxLength={60} /></label>
          <button className="btn btn-primary" disabled={busy || !contact.trim()}>{busy ? <Loader2 className="animate-spin" size={18} aria-hidden /> : null}{busy ? t('alerts.sms.saving') : t('alerts.sms.save')}</button>
        </form>
        {res && (
          <div role="status" className={`mt-3 rounded-2xl p-3 text-sm ${res.ok ? 'bg-leaf-50 text-leaf-900' : 'bg-red-50 text-red-800'}`}>
            <p>{res.text}</p>
            {res.preview && <div className="mt-2 rounded-xl bg-white p-3"><div className="text-xs font-bold uppercase text-slate-500">{t('alerts.sms.preview')}</div><p className="mt-1">{res.preview}</p></div>}
          </div>
        )}
      </section>
    </main>
  );
}
