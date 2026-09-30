import type { Advisory, Lang } from './types';

const SEEN = 'km.seen';
export const notificationsSupported = () => typeof window !== 'undefined' && 'Notification' in window;

export async function showNotification(title: string, body: string, tag: string) {
  if (!notificationsSupported() || Notification.permission !== 'granted') return false;
  try {
    const reg = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : undefined;
    if (reg) await reg.showNotification(title, { body, tag, icon: `${import.meta.env.BASE_URL}icons/icon-192.png`, badge: `${import.meta.env.BASE_URL}icons/icon-192.png` });
    else new Notification(title, { body, tag });
    return true;
  } catch { return false; }
}

/** Notify once per new warning/danger advisory (only when permission was granted by the farmer). */
export async function notifyNewAlerts(place: string, alerts: Advisory[], lang: Lang) {
  if (!notificationsSupported() || Notification.permission !== 'granted') return;
  let seen: string[] = [];
  try { seen = JSON.parse(localStorage.getItem(SEEN) || '[]') as string[]; } catch { /* ignore */ }
  const fresh = alerts.filter((a) => !seen.includes(`${place}|${a.id}`));
  if (!fresh.length) return;
  const top = [...fresh].sort((a, b) => (a.severity === 'danger' ? -1 : 1) - (b.severity === 'danger' ? -1 : 1))[0];
  await showNotification(`${place}: ${lang === 'hi' ? top.title_hi : top.title_en}`, lang === 'hi' ? top.message_hi : top.message_en, top.id);
  try { localStorage.setItem(SEEN, JSON.stringify([...seen, ...fresh.map((a) => `${place}|${a.id}`)].slice(-60))); } catch { /* ignore */ }
}
