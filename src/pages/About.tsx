import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fmtCount, loadManifest } from '../lib/data';
import type { Manifest } from '../lib/types';

export default function About() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'hi' ? 'hi' : 'en';
  const [m, setM] = useState<Manifest | null>(null);
  useEffect(() => { loadManifest().then(setM).catch(() => undefined); }, []);
  const S = ({ h, children }: { h: string; children: React.ReactNode }) => <section className="card p-5"><h2 className="mb-1 text-lg font-extrabold">{h}</h2>{children}</section>;
  return (
    <main className="mx-auto w-full overflow-x-clip max-w-3xl px-4 pb-28 pt-4 md:pb-10">
      <h1 className="text-3xl font-extrabold">{t('about.title')}</h1>
      <p className="mt-2 rounded-2xl bg-leaf-50 p-4 text-lg font-semibold text-leaf-900">{t('about.purpose')}</p>
      <div className="mt-4 grid gap-4">
        <S h={t('about.data')}>
          {m && <p>{t('about.dataDesc', { n: fmtCount(m.total_panchayats, lang), s: m.states.length })}</p>}
          <p className="mt-2 text-sm text-slate-600">{t('about.dataNote')}</p>
          <p className="mt-2 text-sm text-slate-600">{t('about.gaps')}</p>
          {m?.sources.map((s) => <p key={s.id} className="mt-2 text-xs text-slate-500"><b>{t('about.source')}:</b> {s.name}. {s.license}.</p>)}
        </S>
        <S h={t('about.weather')}><p>{t('about.weatherDesc')}</p></S>
        <S h={t('about.advice')}><p>{t('about.adviceDesc')}</p></S>
        {m && (
          <S h={t('about.states')}>
            <div className="max-h-96 overflow-auto rounded-xl border border-leaf-100">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-leaf-50 text-left"><tr><th className="p-2">{t('select.state')}</th><th className="p-2 text-right">{t('stat.panchayats')}</th><th className="p-2">{t('about.source')}</th></tr></thead>
                <tbody>{m.states.map((s) => <tr key={s.slug} className="border-t border-leaf-100"><td className="p-2">{s.name}</td><td className="p-2 text-right tabular-nums">{fmtCount(s.count, lang)}</td><td className="p-2 text-xs text-slate-500">{s.code_system}</td></tr>)}</tbody>
              </table>
            </div>
          </S>
        )}
        <p className="text-sm text-slate-600">{t('about.install')}</p>
        <p className="text-xs text-slate-500">{t('footer.disclaimer')}</p>
      </div>
    </main>
  );
}
