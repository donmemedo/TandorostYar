"use client";
import { Check } from "lucide-react";
import { Bar, CountUp, Failed, Loading, TYPES, css, grad } from "@/components/ui";
import { useApi, type PactType } from "@/lib/api";
import { useT } from "@/lib/i18n";

type Biz = { members: number; pacts: number; completion: Partial<Record<PactType, number>>; daily: { day: string; n: number }[] };

export default function Business() {
  const { t, n, date, pct } = useT();
  const { data, error, reload } = useApi<Biz>("/business");
  if (error) return <Failed retry={reload} />;
  if (!data) return <Loading />;
  const rates = Object.values(data.completion);
  const avg = rates.length ? rates.reduce((a, b) => a + b, 0) / rates.length : 0;
  const max = Math.max(1, ...data.daily.map((d) => d.n));

  return (
    <div className="space-y-5">
      <header className="rise py-4 md:py-8">
        <h1 className="max-w-3xl text-4xl font-black leading-tight tracking-tight md:text-6xl">
          <span className="brand-text">{t.bizTitle}</span>
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-8 text-muted">{t.bizSub}</p>
        <a href="#pricing" className="btn btn-primary mt-6">{t.bizCta}</a>
      </header>

      <section className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {[[t.activeMembers, data.members, n], [t.activePacts, data.pacts, n], [t.completion, Math.round(avg * 100), pct]].map(([k, v, f], i) => (
          <div key={k as string} className={`card rise p-5 md:p-6 ${i === 2 ? "col-span-2 md:col-span-1" : ""}`} style={css({ "--i": i + 1 })}>
            <p className="text-sm font-semibold text-muted">{k as string}</p>
            <p className="mt-2 text-4xl font-black"><CountUp value={v as number} format={f as (x: number) => string} /></p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="card rise p-6" style={css({ "--i": 4 })}>
          <h2 className="mb-5 font-black">{t.byType}</h2>
          <div className="space-y-5">
            {(Object.keys(TYPES) as PactType[]).filter((k) => k in data.completion).map((k) => (
              <div key={k}>
                <div className="mb-2 flex justify-between text-sm font-bold"><span>{t.type[k]}</span><span className="tabular-nums">{pct(Math.round(data.completion[k]! * 100))}</span></div>
                <Bar value={data.completion[k]!} bg={grad(k)} />
              </div>
            ))}
          </div>
        </div>
        <div className="card rise p-6" style={css({ "--i": 5 })}>
          <h2 className="mb-5 font-black">{t.activity}</h2>
          <div className="flex h-40 items-end gap-1.5" dir="ltr">
            {data.daily.map((d, i) => (
              <div key={d.day} className="group flex h-full flex-1 flex-col justify-end gap-1.5" title={`${date(d.day, { day: "numeric", month: "short" })}: ${n(d.n)}`}>
                <i className="block w-full origin-bottom rounded-md transition-opacity group-hover:opacity-80"
                  style={{ height: `${(d.n / max) * 100}%`, minHeight: 4, background: "linear-gradient(180deg,#32ade6,#5e5ce6)", animation: `grow-y 1s ${i * 40}ms cubic-bezier(.2,.8,.2,1) both` }} />
                <span className="text-center text-[10px] font-bold text-muted">{date(d.day, { weekday: "narrow" })}</span>
              </div>
            ))}
          </div>
          <style>{`@keyframes grow-y{from{transform:scaleY(0)}}`}</style>
        </div>
      </section>

      <section id="pricing" className="scroll-mt-24 pt-6">
        <h2 className="rise mb-5 text-3xl font-black">{t.pricing}</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {t.plans.map((p, i) => {
            const hot = i === 1;
            return (
              <article key={p.name} className={`card rise flex flex-col p-6 ${hot ? "md:-translate-y-3" : ""}`}
                style={css({ "--i": i + 6, ...(hot ? { border: "2px solid transparent", background: "linear-gradient(var(--bg),var(--bg)) padding-box, var(--brand) border-box" } : {}) })}>
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-black">{p.name}</h3>
                  {hot && <span className="rounded-full px-3 py-1 text-xs font-bold text-white" style={{ background: "var(--brand)" }}>{t.popular}</span>}
                </div>
                <p className="mt-4"><span className="text-4xl font-black">{p.price}</span> <span className="text-sm font-semibold text-muted">{t.toman} {"per" in p ? p.per : ""} {t.perMonth}</span></p>
                <ul className="mt-6 space-y-3 text-sm">
                  {p.f.map((f) => <li key={f} className="flex items-start gap-2"><Check size={18} className="shrink-0 text-good" /> {f}</li>)}
                </ul>
              </article>
            );
          })}
        </div>
        <p className="mt-5 text-sm text-muted">{t.feeNote(pct(12))}</p>
      </section>
    </div>
  );
}
