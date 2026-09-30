import { useEffect, useRef, useState } from 'react';
import { CloudSun, MapPin, Tractor } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function Onboarding({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const [i, setI] = useState(0);
  const btn = useRef<HTMLButtonElement>(null);
  const steps = [MapPin, CloudSun, Tractor];
  const Icon = steps[i];
  useEffect(() => { btn.current?.focus(); }, [i]);
  return (
    <div role="dialog" aria-modal="true" aria-label={t('app')} className="fixed inset-0 z-50 grid place-items-center bg-leaf-900/50 p-5 backdrop-blur-sm">
      <div className="card fade-in w-full max-w-sm p-7 text-center" key={i}>
        <div className="mx-auto mb-5 grid h-24 w-24 place-items-center rounded-full bg-leaf-100 text-leaf-700"><Icon size={48} aria-hidden /></div>
        <h2 className="mb-2 text-2xl font-extrabold">{t(`onb.${i + 1}.t`)}</h2>
        <p className="mb-6 text-slate-600">{t(`onb.${i + 1}.d`)}</p>
        <div className="mb-6 flex justify-center gap-2" aria-hidden>
          {steps.map((_, j) => <span key={j} className={`h-2 rounded-full transition-all ${j === i ? 'w-6 bg-leaf-600' : 'w-2 bg-slate-300'}`} />)}
        </div>
        <button ref={btn} className="btn btn-primary w-full" onClick={() => (i < 2 ? setI(i + 1) : onDone())}>{i < 2 ? t('onb.next') : t('onb.start')}</button>
        {i < 2 && <button className="btn mt-1 w-full text-slate-500" onClick={onDone}>{t('onb.skip')}</button>}
      </div>
    </div>
  );
}
