import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowRight, Loader2, LocateFixed, MapPin } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import Combobox from '../components/Combobox';
import IndiaMap from '../components/IndiaMap';
import { fmtCount, loadManifest, loadRecent, loadState, nearest, nearestAnywhere, saveSelected, searchState } from '../lib/data';
import type { Manifest, Panchayat, StateIdx, StateMeta } from '../lib/types';

export default function Home({ current, onSelect }: { current: Panchayat | null; onSelect: (p: Panchayat) => void }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'hi' ? 'hi' : 'en';
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loadErr, setLoadErr] = useState(false);
  const [state, setState] = useState<StateIdx | null>(null);
  const [stateLoading, setStateLoading] = useState(false);
  const [district, setDistrict] = useState('');
  const [block, setBlock] = useState('');
  const [pick, setPick] = useState<Panchayat | null>(null);
  const [locMsg, setLocMsg] = useState<{ kind: 'info' | 'error'; text: string } | null>(null);
  const [locating, setLocating] = useState(false);
  const reqId = useRef(0);
  const recent = useMemo(() => loadRecent().filter((r) => r.code !== current?.code).slice(0, 4), [current]);

  const init = useCallback(() => {
    setLoadErr(false);
    loadManifest().then(setManifest).catch(() => setLoadErr(true));
  }, []);
  useEffect(init, [init]);

  const chooseState = useCallback(async (meta: StateMeta | null) => {
    const my = ++reqId.current;
    setDistrict(''); setBlock(''); setPick(null); setLocMsg(null);
    if (!meta) { setState(null); return; }
    setStateLoading(true); setLoadErr(false);
    try {
      const idx = await loadState(meta);
      if (my === reqId.current) setState(idx);
    } catch { if (my === reqId.current) setLoadErr(true); }
    finally { if (my === reqId.current) setStateLoading(false); }
  }, []);

  /** Set the whole hierarchy from a Panchayat (loads its state if needed). */
  const applyPanchayat = useCallback(async (p: Panchayat, m: Manifest) => {
    const meta = m.states.find((s) => s.slug === p.stateSlug);
    if (!meta) return;
    const idx = await loadState(meta);
    reqId.current++;
    setState(idx); setDistrict(p.district); setBlock(p.block); setPick(p);
  }, []);

  const dist = state?.districts.find((d) => d.name === district) ?? null;
  const blk = dist?.blocks.find((b) => b.name === block) ?? null;

  const getOptions = useCallback((q: string): Panchayat[] => {
    if (!state) return [];
    if (blk) {
      const s = q.trim().toLowerCase();
      return (s ? blk.gps.filter((g) => g.name.toLowerCase().includes(s)) : blk.gps).slice(0, 200);
    }
    const found = searchState(state, q, 120);
    return dist ? found.filter((g) => g.district === dist.name).slice(0, 40) : found.slice(0, 40);
  }, [state, dist, blk]);

  function locate() {
    if (!manifest) return;
    if (!navigator.geolocation) { setLocMsg({ kind: 'error', text: t('select.locFail') }); return; }
    setLocating(true); setLocMsg({ kind: 'info', text: t('select.locating') });
    navigator.geolocation.getCurrentPosition(async (pos) => {
      try {
        const r = await nearestAnywhere(manifest, pos.coords.latitude, pos.coords.longitude);
        if (!r || r.km > 60) { setLocMsg({ kind: 'error', text: t('select.locFar', { km: Math.round(r?.km ?? 999) }) }); return; }
        await applyPanchayat(r.p, manifest);
        setLocMsg({ kind: 'info', text: t('select.locFound', { name: r.p.name, km: r.km.toFixed(1) }) });
      } catch { setLocMsg({ kind: 'error', text: t('select.locFail') }); }
      finally { setLocating(false); }
    }, (err) => {
      setLocating(false);
      setLocMsg({ kind: 'error', text: err.code === err.PERMISSION_DENIED ? t('select.locDenied') : t('select.locFail') });
    }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 });
  }

  async function onMapClick(lat: number, lng: number) {
    if (!manifest) return;
    if (state && lat >= state.meta.bbox[1] - 0.6 && lat <= state.meta.bbox[3] + 0.6 && lng >= state.meta.bbox[0] - 0.6 && lng <= state.meta.bbox[2] + 0.6) {
      const pool = blk ? blk.gps : dist ? dist.blocks.flatMap((b) => b.gps) : state.all;
      const n = nearest(pool, lat, lng);
      if (n) { await applyPanchayat(n.p, manifest); return; }
    }
    const r = await nearestAnywhere(manifest, lat, lng);
    if (r && r.km < 60) await applyPanchayat(r.p, manifest);
    else setLocMsg({ kind: 'error', text: t('select.locFar', { km: Math.round(r?.km ?? 999) }) });
  }

  const go = () => { if (pick) { saveSelected(pick); onSelect(pick); } };
  const nf = (n: number) => fmtCount(n, lang);

  return (
    <main className="mx-auto w-full overflow-x-clip max-w-6xl px-4 pb-28 pt-4 md:pb-10">
      <section className="hero-bg fade-in relative overflow-hidden rounded-3xl p-6 text-white sm:p-9">
        <div className="absolute -right-6 -top-6 h-40 w-40 rounded-full bg-white/10" aria-hidden />
        <div className="relative max-w-2xl">
          <h1 className="text-3xl font-extrabold leading-tight sm:text-4xl">{t('tagline')}</h1>
          <p className="mt-2 text-base text-white/90 sm:text-lg">{t('tagline.sub')}</p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <button className="btn bg-white text-leaf-800 shadow-lg hover:bg-leaf-50" onClick={locate} disabled={!manifest || locating}>
              {locating ? <Loader2 className="animate-spin" size={20} aria-hidden /> : <LocateFixed size={20} aria-hidden />}{t('select.locate')}
            </button>
            {current && (
              <button className="btn border-2 border-white/60 text-white hover:bg-white/10" onClick={() => onSelect(current)}>
                <MapPin size={18} aria-hidden />{current.name}<ArrowRight size={18} aria-hidden />
              </button>
            )}
          </div>
        </div>
        <dl className="relative mt-6 grid max-w-xl grid-cols-3 gap-3 text-center">
          {[[manifest ? nf(manifest.total_panchayats) : '…', t('stat.panchayats')], [manifest ? nf(manifest.states.length) : '…', t('stat.states')], ['₹0', t('stat.free')]].map(([v, l]) => (
            <div key={l} className="rounded-2xl bg-white/15 px-2 py-3 backdrop-blur"><dt className="sr-only">{l}</dt><dd className="text-xl font-extrabold sm:text-2xl">{v}</dd><dd className="text-[11px] leading-tight text-white/85 sm:text-xs">{l}</dd></div>
          ))}
        </dl>
      </section>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <section className="card fade-in p-5" aria-labelledby="pick-h">
          <h2 id="pick-h" className="mb-4 text-xl font-extrabold">{t('select.title')}</h2>
          {loadErr && (
            <div role="alert" className="mb-4 flex items-start gap-2 rounded-2xl bg-red-50 p-3 text-sm text-red-800">
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden />
              <div>{t('select.loadFail')}<button className="ml-2 font-bold underline" onClick={init}>{t('select.retry')}</button></div>
            </div>
          )}
          <div className="grid gap-4">
            <label className="grid gap-1">
              <span className="text-sm font-bold text-leaf-900">{t('select.state')}</span>
              <select className="field" value={state?.meta.slug ?? ''} disabled={!manifest}
                onChange={(e) => void chooseState(manifest?.states.find((s) => s.slug === e.target.value) ?? null)}>
                <option value="">{t('select.choose')}</option>
                {manifest?.states.map((s) => <option key={s.slug} value={s.slug}>{s.name} ({nf(s.count)})</option>)}
              </select>
            </label>
            <label className="grid gap-1">
              <span className="text-sm font-bold text-leaf-900">{t('select.district')}</span>
              <select className="field" value={district} disabled={!state}
                onChange={(e) => { setDistrict(e.target.value); setBlock(''); setPick(null); }}>
                <option value="">{state ? t('select.all') : t('select.pickState')}</option>
                {state?.districts.map((d) => <option key={d.name} value={d.name}>{d.name}</option>)}
              </select>
            </label>
            <label className="grid gap-1">
              <span className="text-sm font-bold text-leaf-900">{t('select.block')}</span>
              <select className="field" value={block} disabled={!dist} onChange={(e) => { setBlock(e.target.value); setPick(null); }}>
                <option value="">{t('select.all')}</option>
                {dist?.blocks.map((b) => <option key={b.name} value={b.name}>{b.name} ({nf(b.gps.length)})</option>)}
              </select>
            </label>
            {stateLoading ? (
              <div className="skeleton h-12" role="status" aria-label={t('select.loading')} />
            ) : (
              <Combobox
                label={`${t('select.panchayat')}${blk ? ` (${t('select.count', { n: nf(blk.gps.length) })})` : ''}`}
                placeholder={state ? t('select.searchIn', { state: state.meta.name }) : t('select.pickState')}
                hint={t('select.type2')} emptyText={t('select.noResults')} disabled={!state}
                value={pick} getOptions={getOptions} showBlock={!blk}
                onSelect={(g) => { setPick(g); void (manifest && applyPanchayat(g, manifest)); }}
                onClear={() => setPick(null)}
              />
            )}
          </div>
          {locMsg && (
            <p role="status" className={`mt-3 rounded-xl p-3 text-sm ${locMsg.kind === 'error' ? 'bg-amber-50 text-amber-900' : 'bg-leaf-50 text-leaf-900'}`}>{locMsg.text}</p>
          )}
          <button className="btn btn-primary mt-5 w-full text-lg" disabled={!pick} onClick={go}>{t('select.view')}<ArrowRight size={20} aria-hidden /></button>
          {pick && <p className="mt-2 text-center text-xs text-slate-500">{pick.name} · {pick.block} · {pick.district} · {pick.state}</p>}
          {recent.length > 0 && (
            <div className="mt-5 border-t border-leaf-100 pt-4">
              <h3 className="mb-2 text-sm font-bold text-slate-600">{t('select.recent')}</h3>
              <div className="flex flex-wrap gap-2">
                {recent.map((r) => (
                  <button key={r.code} className="btn btn-ghost !min-h-10 !px-3 text-sm" onClick={() => { saveSelected(r); onSelect(r); }}>{r.name}<span className="font-normal text-slate-500">· {r.district}</span></button>
                ))}
              </div>
            </div>
          )}
        </section>

        <IndiaMap
          manifest={manifest} state={state} district={district} block={block} selected={pick}
          onPickState={(m) => void chooseState(m)}
          onPickDistrict={(n) => { setDistrict(n); setBlock(''); setPick(null); }}
          onPickBlock={(n) => { setBlock(n); setPick(null); }}
          onPickPanchayat={(g) => { setPick(g); }}
          onMapClick={(la, ln) => void onMapClick(la, ln)}
        />
      </div>
    </main>
  );
}
