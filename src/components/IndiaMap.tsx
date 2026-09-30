import { useEffect, useMemo } from 'react';
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useTranslation } from 'react-i18next';
import type { Manifest, Panchayat, StateIdx, StateMeta } from '../lib/types';

interface Props {
  manifest: Manifest | null; state: StateIdx | null; district: string; block: string; selected: Panchayat | null;
  onPickState: (m: StateMeta) => void; onPickDistrict: (name: string) => void; onPickBlock: (name: string) => void;
  onPickPanchayat: (p: Panchayat) => void; onMapClick: (lat: number, lng: number) => void;
}

const INDIA: L.LatLngBoundsExpression = [[6.5, 68.0], [35.8, 97.5]];

function Fit({ bounds, k }: { bounds: L.LatLngBoundsExpression; k: string }) {
  const map = useMap();
  useEffect(() => { map.fitBounds(bounds, { padding: [24, 24], maxZoom: 13, animate: true }); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [k, map]);
  return null;
}
function Clicks({ onClick }: { onClick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onClick(e.latlng.lat, e.latlng.lng) });
  return null;
}
function Resize({ k }: { k: string }) {
  const map = useMap();
  useEffect(() => { const t = setTimeout(() => map.invalidateSize(), 150); return () => clearTimeout(t); }, [k, map]);
  return null;
}

export default function IndiaMap(p: Props) {
  const { t, i18n } = useTranslation();
  const nf = useMemo(() => new Intl.NumberFormat(i18n.language === 'hi' ? 'hi-IN' : 'en-IN'), [i18n.language]);
  const { manifest, state, district, block, selected } = p;

  const dist = state?.districts.find((d) => d.name === district) ?? null;
  const blk = dist?.blocks.find((b) => b.name === block) ?? null;

  let caption = t('map.states');
  let bounds: L.LatLngBoundsExpression = INDIA;
  let key = 'india';
  const markers: { id: string; lat: number; lng: number; r: number; label: string; color: string; onClick: () => void }[] = [];

  if (!state) {
    for (const s of manifest?.states ?? []) {
      markers.push({ id: s.slug, lat: (s.bbox[1] + s.bbox[3]) / 2, lng: (s.bbox[0] + s.bbox[2]) / 2,
        r: 6 + Math.min(10, Math.sqrt(s.count) / 12), label: `${s.name} · ${nf.format(s.count)}`, color: '#2f7d32', onClick: () => p.onPickState(s) });
    }
  } else {
    const m = state.meta;
    bounds = [[m.bbox[1], m.bbox[0]], [m.bbox[3], m.bbox[2]]];
    key = `s-${m.slug}`;
    caption = t('map.districts', { state: m.name });
    if (!dist) {
      for (const d of state.districts) markers.push({ id: d.name, lat: d.lat, lng: d.lng, r: 6 + Math.min(9, Math.sqrt(d.count) / 4),
        label: `${d.name} · ${nf.format(d.count)}`, color: '#2f7d32', onClick: () => p.onPickDistrict(d.name) });
    } else if (!blk) {
      const pts = dist.blocks;
      bounds = L.latLngBounds(pts.map((b) => [b.lat, b.lng] as [number, number])).pad(0.25);
      key = `d-${m.slug}-${dist.name}`;
      caption = t('map.blocks', { district: dist.name });
      for (const b of pts) markers.push({ id: b.name, lat: b.lat, lng: b.lng, r: 7 + Math.min(8, Math.sqrt(b.gps.length) / 2),
        label: `${b.name} · ${nf.format(b.gps.length)}`, color: '#1d6fb8', onClick: () => p.onPickBlock(b.name) });
    } else {
      bounds = L.latLngBounds(blk.gps.map((g) => [g.lat, g.lng] as [number, number])).pad(0.2);
      key = `b-${m.slug}-${dist.name}-${blk.name}`;
      caption = t('map.gps', { block: blk.name });
      for (const g of blk.gps) markers.push({ id: g.code, lat: g.lat, lng: g.lng, r: selected?.code === g.code ? 11 : 6, label: g.name,
        color: selected?.code === g.code ? '#d9480f' : '#2f7d32', onClick: () => p.onPickPanchayat(g) });
    }
  }

  return (
    <div className="card flex h-full min-h-[22rem] flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-leaf-100 px-4 py-2.5 text-sm font-bold text-leaf-900">
        <span>{caption}</span>
        <span className="hidden text-xs font-semibold text-slate-500 sm:inline">{t('map.hint')}</span>
      </div>
      <div className="relative min-h-[18rem] flex-1" data-testid="map">
        <MapContainer bounds={INDIA} className="absolute inset-0" preferCanvas scrollWheelZoom={false} minZoom={4} maxBounds={[[0, 60], [42, 105]]} attributionControl>
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={17} />
          <Fit bounds={bounds} k={key} />
          <Resize k={key} />
          <Clicks onClick={p.onMapClick} />
          {markers.map((m) => (
            <CircleMarker key={`${key}-${m.id}`} center={[m.lat, m.lng]} radius={m.r} bubblingMouseEvents={false}
              pathOptions={{ color: '#fff', weight: 2, fillColor: m.color, fillOpacity: 0.85 }} eventHandlers={{ click: m.onClick }}>
              <Tooltip className="km-tip" direction="top" offset={[0, -4]}>{m.label}</Tooltip>
            </CircleMarker>
          ))}
          {selected && !blk && (
            <CircleMarker center={[selected.lat, selected.lng]} radius={10} pathOptions={{ color: '#fff', weight: 3, fillColor: '#d9480f', fillOpacity: 1 }} bubblingMouseEvents={false}>
              <Tooltip className="km-tip" permanent direction="top" offset={[0, -8]}>{selected.name}</Tooltip>
            </CircleMarker>
          )}
        </MapContainer>
      </div>
    </div>
  );
}
