import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import type { Panchayat } from '../lib/types';

interface Props {
  label: string; placeholder: string; hint: string; emptyText: string; disabled?: boolean;
  value: Panchayat | null;
  getOptions: (q: string) => Panchayat[];
  onSelect: (p: Panchayat) => void;
  onClear: () => void;
  showBlock?: boolean;
}

export default function Combobox({ label, placeholder, hint, emptyText, disabled, value, getOptions, onSelect, onClear, showBlock }: Props) {
  const id = useId();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const opts = useMemo(() => (open ? getOptions(q) : []), [open, q, getOptions]);
  useEffect(() => setActive(0), [q, open]);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  useEffect(() => { document.getElementById(`${id}-o${active}`)?.scrollIntoView({ block: 'nearest' }); }, [active, id]);

  const choose = (p: Panchayat) => { onSelect(p); setQ(''); setOpen(false); };
  const shown = value && !open ? value.name : q;

  return (
    <div ref={boxRef} className="relative">
      <label htmlFor={id} className="mb-1 block text-sm font-bold text-leaf-900">{label}</label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={20} aria-hidden />
        <input
          id={id} role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list"
          aria-activedescendant={open && opts[active] ? `${id}-o${active}` : undefined}
          className="field !pl-10 !pr-11" disabled={disabled} autoComplete="off" autoCapitalize="off" spellCheck={false}
          placeholder={placeholder} value={shown}
          onFocus={() => { setOpen(true); if (value) setQ(''); }}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, Math.max(0, opts.length - 1))); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            else if (e.key === 'Enter' && open && opts[active]) { e.preventDefault(); choose(opts[active]); }
            else if (e.key === 'Escape') setOpen(false);
          }}
        />
        {(value || q) && !disabled && (
          <button type="button" aria-label="Clear" className="absolute right-1 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full text-slate-500 hover:bg-slate-100"
            onClick={() => { setQ(''); onClear(); }}><X size={18} aria-hidden /></button>
        )}
      </div>
      {open && !disabled && (
        <ul id={`${id}-list`} role="listbox" className="absolute z-40 mt-1 max-h-72 w-full overflow-auto rounded-2xl border border-leaf-100 bg-white p-1 shadow-xl">
          {opts.length === 0 && <li className="px-3 py-3 text-sm text-slate-500">{q.trim().length < 2 ? hint : emptyText}</li>}
          {opts.map((p, i) => (
            <li key={p.code} id={`${id}-o${i}`} role="option" aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()} onClick={() => choose(p)} onMouseEnter={() => setActive(i)}
              className={`cursor-pointer rounded-xl px-3 py-2.5 ${i === active ? 'bg-leaf-100' : ''}`}>
              <div className="font-bold">{p.name}</div>
              <div className="text-xs text-slate-500">{showBlock ? `${p.block} · ` : ''}{p.district}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
