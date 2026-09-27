"use client";
import { Plus, ShieldCheck, Trophy } from "lucide-react";
import { useState } from "react";
import { Bar, Failed, HoldButton, Loading, PageTitle, Sheet, Success, TYPES, css, grad } from "@/components/ui";
import { post, useApi, type Dash, type PactType } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function Pacts() {
  const { t, n, money, date } = useT();
  const { data, error, reload } = useApi<Dash>("/dashboard");
  const [open, setOpen] = useState(false);
  if (error) return <Failed retry={reload} />;
  if (!data) return <Loading />;

  return (
    <>
      <PageTitle title={t.myPacts} sub={t.tagline}>
        <button className="btn btn-primary" onClick={() => setOpen(true)} disabled={data.pacts.length >= 3}><Plus size={18} /> {t.newPact}</button>
      </PageTitle>
      <div className="grid gap-4 md:grid-cols-2">
        {data.pacts.map((p, i) => {
          const Icon = TYPES[p.type].icon;
          return (
            <article key={p.id} className="card rise overflow-hidden p-6" style={css({ "--i": i })}>
              <div aria-hidden className="absolute -end-16 -top-16 -z-10 h-48 w-48 rounded-full opacity-30 blur-3xl" style={{ background: grad(p.type) }} />
              <div className="flex items-start justify-between">
                <span className="grid h-14 w-14 place-items-center rounded-[20px] text-white shadow-lg" style={{ background: grad(p.type) }}><Icon size={28} /></span>
                <span className="rounded-full bg-good/15 px-3 py-1 text-xs font-bold text-good">{t.active}</span>
              </div>
              <h2 className="mt-4 text-2xl font-black">{t.type[p.type]}</h2>
              <p className="text-sm text-muted">{p.type === "steps" ? `${n(p.goal)} ${t.unit.steps}` : t.typeDesc[p.type]}</p>
              <dl className="my-5 grid grid-cols-3 gap-3 text-center">
                {[[n(p.target_days), t.perWeek], [money(p.stake), t.perMiss], [money(p.at_risk), t.atRisk]].map(([v, k]) => (
                  <div key={k} className="rounded-2xl bg-soft px-2 py-3">
                    <dt className="text-[11px] font-semibold text-muted">{k}</dt>
                    <dd className="mt-1 text-sm font-black tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
              <div className="mb-2 flex justify-between text-sm font-semibold">
                <span>{t.thisWeek}</span><span className="tabular-nums text-muted">{t.ofDays(n(p.done_days), n(p.target_days))}</span>
              </div>
              <Bar value={p.done_days / p.target_days} bg={grad(p.type)} />
              <div className="mt-4 flex gap-1.5">
                {data.week.map((d) => (
                  <span key={d} title={date(d, { weekday: "long" })} className="grid h-8 flex-1 place-items-center rounded-xl text-[11px] font-bold"
                    style={p.days.includes(d) ? { background: grad(p.type), color: "#fff" } : { background: "var(--soft)", color: "var(--muted)" }}>
                    {date(d, { weekday: "narrow" })}
                  </span>
                ))}
              </div>
            </article>
          );
        })}
      </div>
      <Wizard open={open} taken={data.pacts.map((p) => p.type)} onClose={() => setOpen(false)} onDone={reload} />
    </>
  );
}

function Wizard({ open, taken, onClose, onDone }: { open: boolean; taken: PactType[]; onClose: () => void; onDone: () => void }) {
  const { t, n, money } = useT();
  const [step, setStep] = useState(0);
  const [type, setType] = useState<PactType>();
  const [days, setDays] = useState(4);
  const [goal, setGoal] = useState(8000);
  const [stake, setStake] = useState(50000);
  const [err, setErr] = useState("");
  const close = () => { onClose(); setStep(0); setType(undefined); setErr(""); };
  const seal = async () => {
    try {
      await post("/pacts", { type, target_days: days, stake, daily_goal: type === "steps" ? goal : null });
      setStep(3);
      onDone();
      setTimeout(close, 1500);
    } catch (e) { setErr(t.err[(e as Error).message as keyof typeof t.err] ?? t.err.generic); }
  };

  return (
    <Sheet open={open} onClose={close}>
      <div className="mb-5 flex gap-1.5" aria-hidden>
        {[0, 1, 2].map((i) => <i key={i} className="h-1 flex-1 rounded-full transition-colors duration-500" style={{ background: i <= step ? "var(--fg)" : "var(--line)" }} />)}
      </div>

      {step === 0 && (
        <div className="space-y-3">
          <h2 className="mb-4 text-2xl font-black">{t.q1}</h2>
          {(Object.keys(TYPES) as PactType[]).map((k) => {
            const Icon = TYPES[k].icon;
            return (
              <button key={k} disabled={taken.includes(k)} aria-pressed={type === k} onClick={() => setType(k)}
                className="chip w-full justify-start! gap-4! p-4 text-start disabled:opacity-40">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-white" style={{ background: grad(k) }}><Icon size={24} /></span>
                <span><b className="block text-lg">{t.type[k]}</b><span className="text-sm font-medium text-muted">{taken.includes(k) ? t.err.exists : t.typeDesc[k]}</span></span>
              </button>
            );
          })}
          <button className="btn btn-primary mt-3 w-full" disabled={!type} onClick={() => setStep(1)}>{t.next}</button>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-6">
          <section>
            <h2 className="mb-3 text-xl font-black">{t.q2}</h2>
            <div className="grid grid-cols-7 gap-1.5">
              {[1, 2, 3, 4, 5, 6, 7].map((d) => <button key={d} className="chip px-0!" aria-pressed={days === d} onClick={() => setDays(d)}>{n(d)}</button>)}
            </div>
          </section>
          {type === "steps" && (
            <section>
              <h2 className="mb-3 text-xl font-black">{t.dailyGoal}</h2>
              <div className="grid grid-cols-4 gap-2">
                {[6000, 8000, 10000, 12000].map((g) => <button key={g} className="chip px-1!" aria-pressed={goal === g} onClick={() => setGoal(g)}>{n(g)}</button>)}
              </div>
            </section>
          )}
          <section>
            <h2 className="mb-3 text-xl font-black">{t.q3}</h2>
            <div className="grid grid-cols-2 gap-2">
              {[20000, 50000, 100000, 200000].map((s) => <button key={s} className="chip" aria-pressed={stake === s} onClick={() => setStake(s)}>{money(s)}</button>)}
            </div>
          </section>
          <div className="flex gap-2">
            <button className="btn btn-ghost" onClick={() => setStep(0)}>{t.back}</button>
            <button className="btn btn-primary flex-1" onClick={() => setStep(2)}>{t.next}</button>
          </div>
        </div>
      )}

      {step === 2 && type && (
        <div className="space-y-5">
          <h2 className="text-2xl font-black">{t.summary}</h2>
          <div className="relative overflow-hidden rounded-3xl p-6 text-white" style={{ background: grad(type) }}>
            <p className="text-sm font-bold opacity-80">{t.type[type]}</p>
            <p className="mt-1 text-3xl font-black">{n(days)} {t.perWeek}</p>
            <p className="mt-1 font-semibold opacity-90">{type === "steps" ? `${n(goal)} ${t.unit.steps}` : t.typeDesc[type]}</p>
          </div>
          <ul className="space-y-3 text-sm">
            <li className="flex items-center gap-3"><ShieldCheck className="shrink-0 text-bad" size={20} /> <span className="flex-1">{t.perMiss}</span> <b className="tabular-nums">{money(stake)}</b></li>
            <li className="flex items-center gap-3"><ShieldCheck className="shrink-0 text-bad" size={20} /> <span className="flex-1">{t.maxRisk}</span> <b className="tabular-nums">{money(stake * days)}</b></li>
            <li className="flex items-center gap-3"><Trophy className="shrink-0 text-good" size={20} /> <span className="flex-1">{t.win}</span></li>
          </ul>
          {err && <p className="text-sm font-bold text-bad">{err}</p>}
          <HoldButton label={t.hold} onDone={seal} />
          <button className="btn btn-ghost w-full" onClick={() => setStep(1)}>{t.back}</button>
        </div>
      )}

      {step === 3 && <Success label={t.sealed} />}
    </Sheet>
  );
}
