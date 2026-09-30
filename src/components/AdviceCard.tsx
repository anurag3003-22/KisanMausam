import { useEffect, useState } from 'react';
import { Share2, Square, Volume2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { Advisory, Lang } from '../lib/types';
import { SEV, advisoryIcon, pick } from '../lib/weather';

export function adviceText(a: Advisory, lang: Lang, withCrop = true) {
  return [pick(a as never, 'message', lang), withCrop && a.crop_tip_en ? pick(a as never, 'crop_tip', lang) : ''].filter(Boolean).join(' ');
}

export default function AdviceCard({ a, place, lang, crop }: { a: Advisory; place: string; lang: Lang; crop: string }) {
  const { t } = useTranslation();
  const [speaking, setSpeaking] = useState(false);
  const [noVoice, setNoVoice] = useState(false);
  const s = SEV[a.severity];
  const Icon = advisoryIcon(a.icon);
  const text = adviceText(a, lang);
  const title = pick(a as never, 'title', lang);

  useEffect(() => () => { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); }, []);
  useEffect(() => { if ('speechSynthesis' in window) { window.speechSynthesis.cancel(); setSpeaking(false); } }, [lang, a.id]);

  function speak() {
    if (!('speechSynthesis' in window)) { setNoVoice(true); return; }
    const synth = window.speechSynthesis;
    if (speaking) { synth.cancel(); setSpeaking(false); return; }
    const u = new SpeechSynthesisUtterance(`${title}. ${text}`);
    const voiceLocale: Record<Lang, string> = {
      en: 'en-IN', hi: 'hi-IN', bn: 'bn-IN', gu: 'gu-IN', mr: 'mr-IN', ta: 'ta-IN',
      te: 'te-IN', kn: 'kn-IN', ml: 'ml-IN', pa: 'pa-IN', or: 'or-IN', as: 'as-IN', ur: 'ur-IN',
    };
    u.lang = voiceLocale[lang] ?? 'en-IN';
    const v = synth.getVoices().find((x) => x.lang.toLowerCase().startsWith(u.lang.toLowerCase().slice(0, 2)));
    if (v) u.voice = v; else if (lang === 'hi') setNoVoice(true);
    u.onend = u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    synth.speak(u);
  }
  const share = () => window.open(`https://wa.me/?text=${encodeURIComponent(`KisanMausam – ${place}\n${title}: ${text}`)}`, '_blank', 'noopener');

  return (
    <section className={`card fade-in overflow-hidden border-2 ${s.card}`} aria-labelledby="advice-h">
      <div className={`h-1.5 ${s.bar}`} aria-hidden />
      <div className="p-5">
        <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-slate-600">
          <span className={`rounded-full px-2.5 py-0.5 text-xs ${s.chip}`}>{t(`sev.${a.severity}`)}</span>{t('dash.today')}
        </div>
        <div className="mt-3 flex items-start gap-3">
          <span className={`grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-white shadow ${s.ring}`}><Icon size={30} aria-hidden /></span>
          <div className="min-w-0">
            <h2 id="advice-h" className="text-2xl font-extrabold leading-tight">{title}</h2>
            <p className="mt-2 text-lg leading-relaxed">{pick(a as never, 'message', lang)}</p>
          </div>
        </div>
        {a.crop_tip_en && (
          <div className="mt-4 rounded-2xl bg-white/80 p-3 text-base">
            <div className="text-xs font-bold uppercase text-leaf-700">{t('dash.forCrop')}: {t(`crop.${crop}`)}</div>
            <p className="mt-1">{pick(a as never, 'crop_tip', lang)}</p>
          </div>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="btn btn-ghost" onClick={speak}>{speaking ? <Square size={18} aria-hidden /> : <Volume2 size={18} aria-hidden />}{speaking ? t('dash.stopReading') : t('dash.readAloud')}</button>
          <button className="btn btn-ghost" onClick={share}><Share2 size={18} aria-hidden />{t('dash.share')}</button>
        </div>
        {noVoice && <p role="status" className="mt-2 text-sm text-slate-600">{t('dash.noVoice')}</p>}
      </div>
    </section>
  );
}
