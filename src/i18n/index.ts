import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import hi from './hi.json';
import bn from './bn.json';
import gu from './gu.json';
import mr from './mr.json';
import ta from './ta.json';
import te from './te.json';
import kn from './kn.json';
import ml from './ml.json';
import pa from './pa.json';
import or_ from './or.json';
import as_ from './as.json';
import ur from './ur.json';

const saved = (() => { try { return localStorage.getItem('km.lang'); } catch { return null; } })();
const SUPPORTED = ['en','hi','bn','gu','mr','ta','te','kn','ml','pa','or','as','ur'] as const;
type SupportedLang = typeof SUPPORTED[number];
const initial: SupportedLang = SUPPORTED.includes((saved ?? '') as SupportedLang)
  ? (saved as SupportedLang)
  : (SUPPORTED.find((l) => navigator.language?.toLowerCase().startsWith(l)) ?? 'en');

// Add another language by dropping a JSON file here and registering it below.
i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en }, hi: { translation: hi }, bn: { translation: bn }, gu: { translation: gu },
    mr: { translation: mr }, ta: { translation: ta }, te: { translation: te }, kn: { translation: kn },
    ml: { translation: ml }, pa: { translation: pa }, or: { translation: or_ }, as: { translation: as_ },
    ur: { translation: ur },
  },
  lng: initial,
  fallbackLng: 'en',
  keySeparator: false,
  nsSeparator: false,
  interpolation: { escapeValue: false },
});
document.documentElement.lang = initial;
document.documentElement.dir = initial === 'ur' ? 'rtl' : 'ltr';

export function setLanguage(l: SupportedLang) {
  i18n.changeLanguage(l);
  document.documentElement.lang = l;
  document.documentElement.dir = l === 'ur' ? 'rtl' : 'ltr';
  try { localStorage.setItem('km.lang', l); } catch { /* ignore */ }
}
export default i18n;
