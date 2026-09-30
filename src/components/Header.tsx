import { useEffect, useState } from 'react';
import { Download, Globe, Leaf } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { setLanguage } from '../i18n';

interface InstallEvent extends Event { prompt: () => Promise<void> }

export default function Header({ onHome }: { onHome: () => void }) {
  const { t, i18n } = useTranslation();
  const [installEvt, setInstallEvt] = useState<InstallEvent | null>(null);
  useEffect(() => {
    const h = (e: Event) => { e.preventDefault(); setInstallEvt(e as InstallEvent); };
    window.addEventListener('beforeinstallprompt', h);
    return () => window.removeEventListener('beforeinstallprompt', h);
  }, []);
  const LANGUAGES = [
  ['en', 'English'], ['hi', 'हिन्दी'], ['bn', 'বাংলা'], ['gu', 'ગુજરાતી'], ['mr', 'मराठी'],
  ['ta', 'தமிழ்'], ['te', 'తెలుగు'], ['kn', 'ಕನ್ನಡ'], ['ml', 'മലയാളം'], ['pa', 'ਪੰਜਾਬੀ'],
  ['or', 'ଓଡ଼ିଆ'], ['as', 'অসমীয়া'], ['ur', 'اردو'],
] as const;
  return (
    <header className="sticky top-0 z-30 border-b border-leaf-100 bg-white/95 backdrop-blur" style={{ paddingTop: 'env(safe-area-inset-top)' }}>
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-2.5">
        <button onClick={onHome} className="flex items-center gap-2 rounded-xl py-1 pr-2 text-left" aria-label={t('nav.home')}>
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-leaf-600 text-white"><Leaf size={20} aria-hidden /></span>
          <span className="text-xl font-extrabold tracking-tight text-leaf-900">{t('app')}</span>
        </button>
        <div className="flex items-center gap-2">
          {installEvt && (
            <button className="btn btn-ghost !min-h-11 !px-3 text-sm" onClick={() => { void installEvt.prompt(); setInstallEvt(null); }}>
              <Download size={16} aria-hidden /><span className="hidden sm:inline">{t('install')}</span>
            </button>
          )}
          <label className="language-picker" title={t('lang.label')}>
            <Globe size={18} aria-hidden />
            <span className="sr-only">{t('lang.label')}</span>
            <select
              className="language-select"
              value={i18n.language.split('-')[0]}
              onChange={(e) => setLanguage(e.target.value as Parameters<typeof setLanguage>[0])}
              aria-label={t('lang.label')}
            >
              {LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
          </label>
        </div>
      </div>
    </header>
  );
}
