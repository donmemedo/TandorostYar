"use client";
import { ArrowUpLeft, ArrowUpRight, Check, Flame, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { CountUp, Failed, Loading, Rings, Sheet, Success, TYPES, Bar, css, grad } from "@/components/ui";
import { post, useApi, type Dash, type Pact } from "@/lib/api";
import { parseCount } from "@/lib/digits";
import { errText, useT } from "@/lib/i18n";

export default function Today() {
  const { t, n, money, date, lang, pct } = useT();
  const { data, error, reload } = useApi<Dash>("/dashboard");
  const [sheet, setSheet] = useState<Pact | null>(null);
  if (error) return <Failed retry={reload} />;
  if (!data) return <Loading />;
  const { user, pacts, pool, week, today } = data;
  const total = pacts.reduce((s, p) => s + p.target_days, 0);
  const overall = total ? Math.round((100 * pacts.reduce((s, p) => s + Math.min(p.done_days, p.target_days), 0)) / total) : 0;
  const Arrow = lang === "fa" ? ArrowUpLeft : ArrowUpRight;

  return (
    <div className="space-y-5">
      <header className="rise flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-sm font-semibold text-muted">{date(today, { weekday: "long", day: "numeric", month: "long" })}</p>
          <h1 className="text-4xl font-black tracking-tight md:text-6xl">{t.hello(lang === "fa" ? user.name : user.name_en)}</h1>
        </div>
        <div className="glass flex items-center gap-2 rounded-full py-2 pe-4 ps-2 font-bold shadow-lg">
          <span className="grid h-9 w-9 place-items-center rounded-full" style={{ background: "linear-gradient(135deg,#ff9f0a,#ff2d55)" }}>
            <Flame size={20} className="flame text-white" fill="#fff" />
          </span>
          {t.streak(n(user.streak))}
        </div>
      </header>

      {pacts.length === 0 ? (
        <Link href={data.paused ? "/wallet" : "/pacts"} className="card rise grid place-items-center gap-3 p-12 text-center" style={css({ "--i": 1 })}>
          <span className="grid h-16 w-16 place-items-center rounded-full bg-fg text-bg"><Plus size={30} /></span>
          <p className="text-2xl font-black">{data.paused ? t.nav.pacts : t.noPacts}</p>
          <p className="max-w-md leading-7 text-muted">{data.paused ? t.pausedMsg : t.noPactsHint}</p>
        </Link>
      ) : (
        <section className="card rise grid items-center gap-8 p-6 md:grid-cols-[auto_1fr] md:p-8" style={css({ "--i": 1 })}>
          <div className="relative mx-auto w-[240px] max-w-full">
            <Rings label={`${t.thisWeek}: ${pct(overall)}`} items={pacts.map((p) => ({ value: p.done_days / p.target_days, c: TYPES[p.type].c }))} />
            <div className="absolute inset-0 grid place-items-center text-center">
              <div>
                <div className="text-3xl font-black tabular-nums">{pct(overall)}</div>
                <div className="text-[11px] font-semibold text-muted">{t.thisWeek}</div>
              </div>
            </div>
          </div>
          <div className="space-y-5">
            {pacts.map((p) => {
              const Icon = TYPES[p.type].icon;
              return (
                <div key={p.id} className="flex items-center gap-4">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-white shadow-md" style={{ background: grad(p.type) }}><Icon size={22} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-bold">{t.type[p.type]}</span>
                      <span className="text-sm font-semibold tabular-nums text-muted">{t.ofDays(n(p.done_days), n(p.target_days))}</span>
                    </div>
                    <p className="truncate text-xs text-muted">
                      {p.at_risk > 0 ? <>{t.atRisk}: <b className="text-bad">{money(p.at_risk)}</b></> : <b className="text-good">{t.done} ✓</b>}
                    </p>
                  </div>
                </div>
              );
            })}
            <div className="grid grid-cols-7 gap-1.5 border-t border-line pt-5">
              {week.map((d) => {
                const hits = pacts.filter((p) => p.days.includes(d));
                const isToday = d === today, future = d > today;
                return (
                  <div key={d} className={`flex flex-col items-center gap-1.5 rounded-2xl py-2 ${isToday ? "bg-fg text-bg" : ""} ${future ? "text-muted" : ""}`}>
                    <span className="text-[11px] font-bold opacity-70">{date(d, { weekday: "narrow" })}</span>
                    <span className="text-sm font-black tabular-nums">{date(d, { day: "numeric" })}</span>
                    <span className="flex h-1.5 gap-0.5">{hits.map((p) => <i key={p.id} className="h-1.5 w-1.5 rounded-full" style={{ background: TYPES[p.type].c[0] }} />)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-3">
        {pacts.map((p, i) => {
          const Icon = TYPES[p.type].icon, met = p.today >= p.goal;
          return (
            <article key={p.id} className="card rise flex flex-col gap-4 overflow-hidden p-5" style={css({ "--i": i + 2 })}>
              <div aria-hidden className="absolute -end-10 -top-10 -z-10 h-32 w-32 rounded-full opacity-25 blur-xl" style={{ background: grad(p.type) }} />
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-bold"><Icon size={18} style={{ color: TYPES[p.type].c[0] }} /> {t.today}</span>
                {met && <span className="flex items-center gap-1 rounded-full bg-good/15 px-2.5 py-1 text-xs font-bold text-good"><Check size={14} /> {t.done}</span>}
              </div>
              <div>
                <span className="text-3xl font-black tabular-nums">{n(p.today)}</span>
                <span className="text-sm font-semibold text-muted"> / {n(p.goal)} {t.unit[p.type]}</span>
              </div>
              <Bar value={p.today / p.goal} bg={grad(p.type)} />
              <button className="btn btn-ghost mt-auto w-full" onClick={() => setSheet(p)}><Plus size={18} /> {t.checkin[p.type]}</button>
            </article>
          );
        })}
      </section>

      <Link href="/community" className="card rise group block overflow-hidden p-6 md:p-8" style={css({ "--i": 5 })}>
        <div aria-hidden className="absolute inset-0 -z-10 opacity-[0.12]" style={{ background: "var(--brand)" }} />
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 font-bold text-muted"><Sparkles size={18} /> {t.pool}</p>
            <p className="brand-text mt-2 text-4xl font-black md:text-6xl"><CountUp value={pool.amount} format={money} /></p>
            <p className="mt-3 max-w-xl text-sm leading-7 text-muted">{t.poolHint}</p>
          </div>
          <span className="icon-btn shrink-0 transition-transform group-hover:scale-110"><Arrow size={20} /></span>
        </div>
      </Link>

      <CheckinSheet pact={sheet} onClose={() => setSheet(null)} onSaved={reload} />
    </div>
  );
}

function CheckinSheet({ pact, onClose, onSaved }: { pact: Pact | null; onClose: () => void; onSaved: () => void }) {
  const { t, n } = useT();
  const [value, setValue] = useState(0);
  const [state, setState] = useState<"idle" | "busy" | "ok" | "err">("idle");
  const [msg, setMsg] = useState("");
  const close = () => { onClose(); setValue(0); setState("idle"); setMsg(""); };
  const save = async () => {
    setState("busy");
    try {
      await post(`/pacts/${pact!.id}/checkin`, { value: pact!.type === "nutrition" ? 1 : value });
      setState("ok");
      onSaved();
      setTimeout(close, 1100);
    } catch (e) { setMsg(errText(t, e)); setState("err"); }
  };
  const ready = pact?.type === "nutrition" || value > 0;

  return (
    <Sheet open={!!pact} onClose={close} label={pact ? t.checkin[pact.type] : ""}>
      {pact && (state === "ok" ? <Success label={t.saved} /> : (
        <div className="space-y-5">
          <h2 className="text-2xl font-black">{t.checkin[pact.type]}</h2>
          {pact.type === "gym" && (
            <>
              <div className="grid grid-cols-4 gap-2">
                {[30, 45, 60, 90].map((m) => <button key={m} className="chip" aria-pressed={value === m} onClick={() => setValue(m)}>{n(m)}</button>)}
              </div>
              <p className="text-sm text-muted">{t.unit.gym} · {t.gymHint}</p>
            </>
          )}
          {pact.type === "steps" && (
            <>
              <input type="text" inputMode="numeric" autoComplete="off" placeholder={t.stepsPlaceholder} value={value ? n(value) : ""} autoFocus
                onChange={(e) => setValue(parseCount(e.target.value, 40000))}
                className="h-16 w-full rounded-2xl border border-line bg-soft px-5 text-2xl font-black tabular-nums outline-none focus:border-fg" />
              <div className="grid grid-cols-3 gap-2">
                {[1000, 2500, 5000].map((s) => <button key={s} className="chip" onClick={() => setValue((v) => Math.min(40000, v + s))}>+{n(s)}</button>)}
              </div>
            </>
          )}
          {pact.type === "nutrition" && (
            <p className="rounded-2xl bg-soft p-5 text-center text-lg font-black tabular-nums">
              {n(pact.today)} / {n(pact.goal)} {t.unit.nutrition}
            </p>
          )}
          {state === "err" && <p role="alert" className="text-sm font-bold text-bad">{msg}</p>}
          <div className="flex gap-2">
            <button className="btn btn-ghost" onClick={close}>{t.cancel}</button>
            <button className="btn btn-primary flex-1" disabled={!ready || state === "busy"} onClick={save}>{t.save}</button>
          </div>
        </div>
      ))}
    </Sheet>
  );
}
