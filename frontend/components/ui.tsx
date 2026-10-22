"use client";
import { Dumbbell, Footprints, Salad } from "lucide-react";
import { useEffect, useId, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";
import type { PactType } from "@/lib/api";
import { useT } from "@/lib/i18n";

export const TYPES: Record<PactType, { c: [string, string]; icon: typeof Dumbbell }> = {
  gym: { c: ["#ff2d55", "#ff8a5c"], icon: Dumbbell },
  steps: { c: ["#9be22d", "#30d158"], icon: Footprints },
  nutrition: { c: ["#32ade6", "#00d4c8"], icon: Salad },
};
export const grad = (t: PactType) => `linear-gradient(135deg, ${TYPES[t].c[0]}, ${TYPES[t].c[1]})`;
export const css = (o: Record<string, string | number>) => o as CSSProperties;
const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Damped spring (Apple's damping-ratio / response parameters). Starts from the CURRENT value and velocity, so it can be
 *  interrupted and re-targeted at any instant. Returns a cancel function. */
function spring(from: number, to: number, v0: number, damping: number, response: number, step: (x: number) => void, done: () => void) {
  const w = (2 * Math.PI) / response;
  let x = from, v = v0, last = performance.now(), raf = 0;
  const tick = (now: number) => {
    const h = Math.min(0.032, (now - last) / 1000) / 4;
    last = now;
    for (let i = 0; i < 4; i++) { v += (-w * w * (x - to) - 2 * damping * w * v) * h; x += v * h; }
    if (Math.abs(x - to) < 0.5 && Math.abs(v) < 8) { step(to); done(); return; }
    step(x);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}
const project = (v: number, rate = 0.998) => ((v / 1000) * rate) / (1 - rate); // where a flick would coast to (px)
const rubber = (over: number, dim = 400, k = 0.55) => (over * dim * k) / (dim + k * Math.abs(over)); // resistance past an edge

export function Rings({ items, size = 240, label }: { items: { value: number; c: [string, string] }[]; size?: number; label?: string }) {
  const id = useId().replace(/[^\w-]/g, "");
  const s = size * 0.09, h = size / 2;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="h-auto max-w-full" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {items.map((it, i) => {
        const r = h - s / 2 - i * s * 1.18, c = 2 * Math.PI * r;
        return (
          <g key={i} transform={`rotate(-90 ${h} ${h})`}>
            <defs>
              <linearGradient id={id + i} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={it.c[0]} /><stop offset="1" stopColor={it.c[1]} /></linearGradient>
            </defs>
            <circle cx={h} cy={h} r={r} fill="none" stroke={it.c[1]} strokeOpacity={0.16} strokeWidth={s} />
            <circle className="ring-arc" cx={h} cy={h} r={r} fill="none" stroke={`url(#${id}${i})`} strokeWidth={s} strokeLinecap="round"
              strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(it.value, 1))} style={css({ "--c": c, animationDelay: `${i * 140}ms` })} />
          </g>
        );
      })}
    </svg>
  );
}

/** Counts up by writing straight to the text node: no React render per frame. */
export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
  const el = useRef<HTMLSpanElement>(null);
  const from = useRef(0);
  const fmt = useRef(format);
  fmt.current = format;
  const first = useRef(format(0)).current;
  useEffect(() => {
    const node = el.current!, a = from.current;
    if (reduced() || a === value) { node.textContent = fmt.current(value); from.current = value; return; }
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / 900);
      node.textContent = fmt.current(Math.round(a + (value - a) * (1 - (1 - p) ** 4)));
      if (p < 1) raf = requestAnimationFrame(tick); else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); from.current = value; };
  }, [value]);
  return <span ref={el}>{first}</span>;
}

export function Bar({ value, bg }: { value: number; bg: string }) {
  return <div className="bar" aria-hidden><i style={{ width: `${Math.min(Math.max(value, 0), 1) * 100}%`, background: bg }} /></div>;
}

/** Bottom sheet on phones (drag the handle: 1:1 tracking, rubber-band upward, momentum-projected dismiss, spring back), centred modal on desktop. */
export function Sheet({ open, onClose, label, children }: { open: boolean; onClose: () => void; label: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null), body = useRef<HTMLDivElement>(null);
  const y = useRef(0), cancel = useRef<() => void>(() => {}), drag = useRef<{ off: number; pts: [number, number][] } | null>(null);
  const paint = (v: number) => {
    y.current = v;
    if (body.current) body.current.style.transform = v ? `translate3d(0,${v}px,0)` : "";
    ref.current?.style.setProperty("--dim", String(Math.max(0, 1 - v / (body.current?.offsetHeight || 1))));
  };
  useEffect(() => {
    const d = ref.current!;
    if (open && !d.open) { cancel.current(); paint(0); d.showModal(); }
    if (!open && d.open) d.close();
  }, [open]);

  const dismiss = (v0 = 0) => {
    if (reduced()) return onClose();
    cancel.current();
    cancel.current = spring(y.current, (body.current?.offsetHeight ?? 600) + 40, v0, 1, 0.35, paint, onClose);
  };
  const down = (e: PointerEvent) => {
    cancel.current(); // grabbing a moving sheet stops it where it is
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { off: e.clientY - y.current, pts: [[performance.now(), e.clientY]] };
  };
  const move = (e: PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const raw = e.clientY - d.off;
    paint(raw < 0 ? rubber(raw) : raw);
    d.pts.push([performance.now(), e.clientY]);
    if (d.pts.length > 6) d.pts.shift();
  };
  const up = () => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    const [t0, y0] = d.pts[0], [t1, y1] = d.pts[d.pts.length - 1];
    const v = t1 > t0 ? ((y1 - y0) / (t1 - t0)) * 1000 : 0; // release velocity, px/s
    if (y.current + project(v) > (body.current?.offsetHeight ?? 600) * 0.5) dismiss(v);
    else cancel.current = spring(y.current, 0, v, Math.abs(v) > 300 ? 0.8 : 1, 0.35, paint, () => paint(0)); // bounce only when a flick carried momentum
  };

  return (
    <dialog ref={ref} className="sheet" aria-label={label} onClose={onClose} onCancel={(e) => { e.preventDefault(); dismiss(); }}
      onClick={(e) => e.target === ref.current && dismiss()}>
      <div ref={body} className="sheet-body">
        <div className="sheet-grab" aria-hidden onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} />
        {open && children}
      </div>
    </dialog>
  );
}

export function ConfirmSheet({ open, title, body, confirm, danger, busy, onConfirm, onClose }:
  { open: boolean; title: string; body: string; confirm: string; danger?: boolean; busy?: boolean; onConfirm: () => void; onClose: () => void }) {
  const { t } = useT();
  return (
    <Sheet open={open} onClose={onClose} label={title}>
      <div className="space-y-4">
        <h2 className="text-2xl font-black">{title}</h2>
        <p className="leading-7 text-muted">{body}</p>
        <div className="flex gap-2">
          <button className="btn btn-ghost" onClick={onClose}>{t.cancel}</button>
          <button className={`btn flex-1 ${danger ? "btn-danger" : "btn-primary"}`} disabled={busy} onClick={onConfirm}>{confirm}</button>
        </div>
      </div>
    </Sheet>
  );
}

/** Press and hold to commit. Keyboard and assistive tech activate it with a normal click (detail 0), so nobody is locked out. */
export function HoldButton({ label, hint, onDone, ms = 1300 }: { label: string; hint: string; onDone: () => void; ms?: number }) {
  const btn = useRef<HTMLButtonElement>(null), raf = useRef(0), fired = useRef(false), hid = useId();
  const paint = (x: number) => { btn.current?.style.setProperty("--p", String(x)); if (btn.current) btn.current.dataset.on = x > 0.5 ? "1" : ""; };
  const fire = () => { if (fired.current) return; fired.current = true; navigator.vibrate?.([20, 40, 30]); onDone(); };
  const start = () => {
    cancelAnimationFrame(raf.current);
    const t0 = performance.now();
    const tick = (t: number) => {
      const x = Math.min(1, (t - t0) / ms);
      paint(x);
      if (x < 1) raf.current = requestAnimationFrame(tick); else fire();
    };
    raf.current = requestAnimationFrame(tick);
  };
  const stop = () => { cancelAnimationFrame(raf.current); if (!fired.current) paint(0); };
  useEffect(() => () => cancelAnimationFrame(raf.current), []);
  return (
    <>
      <button ref={btn} type="button" className="btn btn-primary hold h-14 w-full text-base" aria-describedby={hid} style={css({ "--p": 0 })}
        onPointerDown={start} onPointerUp={stop} onPointerLeave={stop} onPointerCancel={stop} onContextMenu={(e) => e.preventDefault()}
        onClick={(e) => { if (e.detail === 0) { paint(1); fire(); } }}>
        <span className="hold-fill" />
        <span className="hold-label relative">{label}</span>
      </button>
      <span id={hid} className="sr-only">{hint}</span>
    </>
  );
}

export function Success({ label }: { label: string }) {
  return (
    <div role="status" className="grid place-items-center gap-3 py-8 text-center">
      <div className="burst" aria-hidden>
        {Array.from({ length: 12 }, (_, k) => <i key={k} style={css({ "--k": k })} />)}
        <svg width="84" height="84" viewBox="0 0 84 84">
          <circle cx="42" cy="42" r="40" fill="var(--good)" />
          <path className="check-draw" d="M26 43l11 11 22-24" fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-2xl font-black">{label}</p>
    </div>
  );
}

export function Loading() {
  const { t } = useT();
  return (
    <div className="space-y-5" aria-busy role="status">
      <span className="sr-only">{t.loading}</span>
      <div className="skeleton h-16 w-2/3" />
      <div className="skeleton h-72" />
      <div className="grid gap-4 sm:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-44" />)}</div>
    </div>
  );
}

export function Failed({ retry, message }: { retry: () => void; message?: string }) {
  const { t } = useT();
  return (
    <div role="alert" className="card grid place-items-center gap-4 p-10 text-center">
      <p className="text-lg font-bold">{message ?? t.err.generic}</p>
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
    const id = setTimeout(() => setMsg(""), 2800);
    return () => clearTimeout(id);
  }, [msg]);
  return [msg, setMsg] as const;
}

export function PageTitle({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) {
  return (
    <header className="rise mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {sub && <p className="mb-1 text-sm font-semibold text-muted">{sub}</p>}
        <h1 className="text-4xl font-black md:text-5xl">{title}</h1>
      </div>
      {children}
    </header>
  );
}
