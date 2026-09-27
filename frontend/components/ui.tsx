"use client";
import { Dumbbell, Footprints, Salad } from "lucide-react";
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { PactType } from "@/lib/api";
import { useT } from "@/lib/i18n";

export const TYPES: Record<PactType, { c: [string, string]; icon: typeof Dumbbell }> = {
  gym: { c: ["#ff2d55", "#ff8a5c"], icon: Dumbbell },
  steps: { c: ["#9be22d", "#30d158"], icon: Footprints },
  nutrition: { c: ["#32ade6", "#00d4c8"], icon: Salad },
};
export const grad = (t: PactType) => `linear-gradient(135deg, ${TYPES[t].c[0]}, ${TYPES[t].c[1]})`;
export const css = (o: Record<string, string | number>) => o as CSSProperties;

export function Rings({ items, size = 240 }: { items: { value: number; c: [string, string] }[]; size?: number }) {
  const id = useId().replace(/[^\w-]/g, "");
  const s = size * 0.09, h = size / 2;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="max-w-full h-auto" aria-hidden>
      {items.map((it, i) => {
        const r = h - s / 2 - i * s * 1.18, c = 2 * Math.PI * r;
        return (
          <g key={i} transform={`rotate(-90 ${h} ${h})`}>
            <defs>
              <linearGradient id={id + i} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={it.c[0]} /><stop offset="1" stopColor={it.c[1]} /></linearGradient>
            </defs>
            <circle cx={h} cy={h} r={r} fill="none" stroke={it.c[1]} strokeOpacity={0.16} strokeWidth={s} />
            <circle className="ring-arc" cx={h} cy={h} r={r} fill="none" stroke={`url(#${id}${i})`} strokeWidth={s} strokeLinecap="round"
              strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(it.value, 1))} style={css({ "--c": c, "--gc": it.c[0], animationDelay: `${i * 140}ms` })} />
          </g>
        );
      })}
    </svg>
  );
}

export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    const a = from.current, t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, Math.max(0, (t - t0) / 1400));
      setV(Math.round(a + (value - a) * (1 - (1 - p) ** 4)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { from.current = value; cancelAnimationFrame(raf); };
  }, [value]);
  return <span className="tabular-nums">{format(v)}</span>;
}

export function Bar({ value, bg }: { value: number; bg: string }) {
  return <div className="bar"><i style={{ width: `${Math.min(value, 1) * 100}%`, background: bg }} /></div>;
}

export function Sheet({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current!;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="sheet" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <div className="sheet-body">
        <div className="mx-auto mb-4 h-1.5 w-10 rounded-full bg-line md:hidden" />
        {open && children}
      </div>
    </dialog>
  );
}

export function HoldButton({ label, onDone, ms = 1300 }: { label: string; onDone: () => void; ms?: number }) {
  const [p, setP] = useState(0);
  const raf = useRef(0);
  const start = () => {
    const t0 = performance.now();
    const tick = (t: number) => {
      const x = Math.min(1, (t - t0) / ms);
      setP(x);
      if (x < 1) raf.current = requestAnimationFrame(tick);
      else { navigator.vibrate?.([20, 40, 30]); onDone(); }
    };
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(tick);
  };
  const stop = () => { cancelAnimationFrame(raf.current); setP((x) => (x >= 1 ? 1 : 0)); };
  return (
    <button type="button" className="btn btn-primary hold w-full h-14 text-base" style={css({ "--p": p })}
      onPointerDown={start} onPointerUp={stop} onPointerLeave={stop} onPointerCancel={stop} onContextMenu={(e) => e.preventDefault()}
      onKeyDown={(e) => (e.key === " " || e.key === "Enter") && !e.repeat && (e.preventDefault(), start())} onKeyUp={stop}>
      <span className="hold-fill" />
      <span className="relative" style={{ color: p > 0.5 ? "#fff" : undefined }}>{label}</span>
    </button>
  );
}

export function Success({ label }: { label: string }) {
  return (
    <div className="grid place-items-center gap-3 py-8 text-center">
      <div className="burst">
        {Array.from({ length: 12 }, (_, k) => <i key={k} style={css({ "--k": k })} />)}
        <svg width="84" height="84" viewBox="0 0 84 84" aria-hidden>
          <circle cx="42" cy="42" r="40" fill="var(--good)" />
          <path className="check-draw" d="M26 43l11 11 22-24" fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-2xl font-black">{label}</p>
    </div>
  );
}

export function Loading() {
  return (
    <div className="space-y-5" aria-busy>
      <div className="skeleton h-16 w-2/3" />
      <div className="skeleton h-72" />
      <div className="grid gap-4 sm:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-44" />)}</div>
    </div>
  );
}

export function Failed({ retry }: { retry: () => void }) {
  const { t } = useT();
  return (
    <div className="card grid place-items-center gap-4 p-10 text-center">
      <p className="text-lg font-bold">{t.err.generic}</p>
      <button className="btn btn-primary" onClick={retry}>{t.retry}</button>
    </div>
  );
}

export function Toast({ msg }: { msg: string }) {
  return (
    <div role="status" aria-live="polite" className={`glass fixed start-1/2 top-4 z-50 rounded-full px-5 py-3 font-bold shadow-xl transition-all duration-500 ltr:-translate-x-1/2 rtl:translate-x-1/2 ${msg ? "opacity-100" : "pointer-events-none -translate-y-20 opacity-0"}`}>
      {msg}
    </div>
  );
}

export function useToast() {
  const [msg, setMsg] = useState("");
  useEffect(() => {
    if (!msg) return;
    const id = setTimeout(() => setMsg(""), 2400);
    return () => clearTimeout(id);
  }, [msg]);
  return [msg, setMsg] as const;
}

export function PageTitle({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) {
  return (
    <header className="rise mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {sub && <p className="mb-1 text-sm font-semibold text-muted">{sub}</p>}
        <h1 className="text-4xl font-black tracking-tight md:text-5xl">{title}</h1>
      </div>
      {children}
    </header>
  );
}
