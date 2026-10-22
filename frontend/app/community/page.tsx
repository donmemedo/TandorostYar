"use client";
import { Crown, Lock, Sparkles } from "lucide-react";
import { useState } from "react";
import { Bar, ConfirmSheet, CountUp, Failed, Loading, PageTitle, Sheet, Toast, css, useToast } from "@/components/ui";
import { post, useApi, type Pool } from "@/lib/api";
import { errText, useT } from "@/lib/i18n";

type Row = { id: number; name: string; name_en: string; done: number; target: number; me: boolean };
type Community = { pool: Pool; leaderboard: Row[]; last: { week: string } | null; week: string; demo: boolean };
type Result = { mine: number; pool: number; fee: number; charity: number };
const MEDAL = ["#ffd60a", "#c7c7cc", "#ff9f0a"];

export default function CommunityPage() {
  const { t, n, money, lang, pct } = useT();
  const { data, error, reload } = useApi<Community>("/community");
  const [result, setResult] = useState<Result>();
  const [confirm, setConfirm] = useState(false);
  const [msg, toast] = useToast();
  if (error) return <Failed retry={reload} />;
  if (!data) return <Loading />;
  const { pool, leaderboard } = data;
  const closed = data.last?.week === data.week;
  const feePct = pct(Math.round(pool.fee_rate * 100));

  const settle = async () => {
    setConfirm(false);
    try { setResult(await post<Result>("/settle")); reload(); }
    catch (e) { toast(errText(t, e)); }
  };

  return (
    <>
      <Toast msg={msg} />
      <PageTitle title={t.nav.community} sub={t.pool}>
        {data.demo && <button className="btn btn-ghost" onClick={() => setConfirm(true)} disabled={closed}>{closed ? <Lock size={16} aria-hidden /> : <Sparkles size={16} aria-hidden />} {t.settle} · {t.demo}</button>}
      </PageTitle>

      <section className="card rise overflow-hidden p-6 md:p-10">
        <div aria-hidden className="absolute -top-24 start-1/4 -z-10 h-72 w-72 rounded-full opacity-30 blur-3xl" style={{ background: "var(--brand)" }} />
        <p className="font-bold text-muted">{t.atStake}</p>
        <p className="brand-text mt-2 text-5xl font-black tracking-tight md:text-7xl"><CountUp value={pool.amount} format={money} /></p>
        <div className="mt-6 flex flex-wrap gap-3">
          <span className="rounded-full bg-soft px-4 py-2 text-sm font-bold">{n(pool.participants)} {t.members}</span>
          <span className="rounded-full bg-soft px-4 py-2 text-sm font-bold">{n(pool.on_track)} / {n(pool.pacts)} {t.onTrack}</span>
        </div>
        <h2 className="mb-3 mt-8 font-bold">{t.split}</h2>
        <div className="flex h-4 overflow-hidden rounded-full">
          <i className="h-full" style={{ width: `${100 - pool.fee_rate * 100}%`, background: "linear-gradient(90deg,#30d158,#9be22d)" }} />
          <i className="h-full flex-1 bg-muted/50" />
        </div>
        <div className="mt-3 flex flex-wrap justify-between gap-2 text-sm">
          <span className="font-bold text-good">{t.winners} · {pct(100 - Math.round(pool.fee_rate * 100))}</span>
          <span className="font-bold text-muted">{t.fee} · {feePct}</span>
        </div>
        <p className="mt-3 text-xs leading-6 text-muted">{t.feeNote(feePct)} {t.charityNote}</p>
      </section>

      <section className="mt-5">
        <h2 className="rise mb-3 text-xl font-black" style={css({ "--i": 1 })}>{t.board}</h2>
        <ol className="space-y-2.5">
          {leaderboard.map((r, i) => (
            <li key={r.id} className={`card rise flex items-center gap-4 p-4 ${r.me ? "ring-2 ring-accent" : ""}`} style={css({ "--i": i + 2 })}>
              <span className="grid w-7 place-items-center text-lg font-black tabular-nums text-muted">
                {i < 3 ? <Crown size={22} fill={MEDAL[i]} stroke={MEDAL[i]} aria-label={n(i + 1)} /> : n(i + 1)}
              </span>
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-lg font-black text-white"
                style={{ background: `linear-gradient(135deg, hsl(${r.id * 47} 90% 60%), hsl(${r.id * 47 + 50} 90% 50%))` }}>
                {(lang === "fa" ? r.name : r.name_en)[0]}
              </span>
              <div className="min-w-0 flex-1">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <b className="truncate">{lang === "fa" ? r.name : r.name_en} {r.me && <span className="ms-1 rounded-full bg-accent px-2 py-0.5 text-[10px] text-white">{t.you}</span>}</b>
                  <span className="text-sm font-bold tabular-nums text-muted">{n(r.done)} / {n(r.target)}</span>
                </div>
                <Bar value={r.done / r.target} bg="var(--brand)" />
              </div>
            </li>
          ))}
        </ol>
      </section>

      <ConfirmSheet open={confirm} title={t.settleTitle} body={t.settleBody} confirm={t.confirm} onConfirm={settle} onClose={() => setConfirm(false)} />
      <Sheet open={!!result} onClose={() => setResult(undefined)} label={t.result}>
        {result && (
          <div className="space-y-5 text-center">
            <h2 className="text-2xl font-black">{t.result}</h2>
            <p className="text-sm font-bold text-muted">{t.yourShare}</p>
            <p className={`text-5xl font-black tabular-nums ${result.mine >= 0 ? "text-good" : "text-bad"}`}>
              <span dir="ltr">{result.mine >= 0 ? "+" : "−"}{n(Math.abs(result.mine))}</span> <span className="text-xl">{t.toman}</span>
            </p>
            <div className="grid grid-cols-3 gap-2 text-sm">
              {[[t.pool, result.pool], [t.fee, result.fee], [t.charity, result.charity]].map(([k, v]) => (
                <div key={k} className="rounded-2xl bg-soft p-3"><p className="text-xs text-muted">{k}</p><b className="tabular-nums">{n(v as number)}</b></div>
              ))}
            </div>
            <button className="btn btn-primary w-full" onClick={() => setResult(undefined)}>{t.close}</button>
          </div>
        )}
      </Sheet>
    </>
  );
}
