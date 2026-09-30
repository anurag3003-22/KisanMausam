import { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import BottomNav, { type Page } from './components/BottomNav';
import Header from './components/Header';
import Onboarding from './components/Onboarding';
import { loadSelected } from './lib/data';
import type { Panchayat } from './lib/types';
import About from './pages/About';
import Alerts from './pages/Alerts';
import Home from './pages/Home';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const PAGES: Page[] = ['home', 'weather', 'alerts', 'about'];
const fromHash = (): Page => { const h = location.hash.replace('#/', ''); return (PAGES as string[]).includes(h) ? (h as Page) : 'home'; };

export default function App() {
  const [p, setP] = useState<Panchayat | null>(loadSelected);
  const [page, setPage] = useState<Page>(fromHash);
  const [onboard, setOnboard] = useState(() => { try { return localStorage.getItem('km.onboarded') !== '1'; } catch { return false; } });

  useEffect(() => {
    const h = () => setPage(fromHash());
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);
  const go = useCallback((next: Page) => { location.hash = `#/${next}`; window.scrollTo({ top: 0 }); }, []);
  const effective: Page = (page === 'weather' || page === 'alerts') && !p ? 'home' : page;

  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-white focus:p-2">Skip to content</a>
      <Header onHome={() => go('home')} />
      <div id="main">
        {effective === 'home' && <Home current={p} onSelect={(x) => { setP(x); go('weather'); }} />}
        {effective === 'weather' && p && (
          <Suspense fallback={<div className="mx-auto max-w-5xl p-4"><div className="skeleton h-52" /></div>}>
            <Dashboard p={p} onBack={() => go('home')} onAlerts={() => go('alerts')} />
          </Suspense>
        )}
        {effective === 'alerts' && p && <Alerts p={p} onBack={() => go('weather')} />}
        {effective === 'about' && <About />}
      </div>
      <BottomNav page={effective} go={go} hasP={!!p} />
      {onboard && <Onboarding onDone={() => { try { localStorage.setItem('km.onboarded', '1'); } catch { /* ignore */ } setOnboard(false); }} />}
    </>
  );
}
