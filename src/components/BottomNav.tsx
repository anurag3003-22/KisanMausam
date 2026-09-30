import { Bell, CloudSun, Home, Info } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export type Page = 'home' | 'weather' | 'alerts' | 'about';

export default function BottomNav({ page, go, hasP }: { page: Page; go: (p: Page) => void; hasP: boolean }) {
  const { t } = useTranslation();
  const items: [Page, typeof Home, string, boolean][] = [
    ['home', Home, 'nav.home', true], ['weather', CloudSun, 'nav.weather', hasP], ['alerts', Bell, 'nav.alerts', hasP], ['about', Info, 'nav.about', true],
  ];
  return (
    <nav aria-label="Main" className="bottom-nav fixed inset-x-0 bottom-0 z-30 border-t border-leaf-100 bg-white/98 backdrop-blur" style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
      <ul className="mx-auto grid max-w-2xl grid-cols-4 px-2 sm:px-4">
        {items.map(([id, Icon, key, enabled]) => (
          <li key={id}>
            <button
              disabled={!enabled}
              onClick={() => go(id)}
              aria-current={page === id ? 'page' : undefined}
              className={`flex h-[4.35rem] w-full flex-col items-center justify-center gap-1 text-xs font-bold transition ${page === id ? 'text-leaf-800' : 'text-slate-500'} disabled:opacity-40`}
            >
              <span className={`grid h-9 w-16 place-items-center rounded-2xl ${page === id ? 'bg-leaf-100 shadow-sm ring-1 ring-leaf-200' : ''}`}><Icon size={22} aria-hidden /></span>
              {t(key)}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
