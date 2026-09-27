"use client";
import { ArrowDownLeft, ArrowUpRight, Dumbbell, GlassWater, HeartHandshake, Plus, Salad, Star } from "lucide-react";
import { useState } from "react";
import { CountUp, Failed, Loading, PageTitle, Toast, css, useToast } from "@/components/ui";
import { post, useApi } from "@/lib/api";
import { useT } from "@/lib/i18n";

type Wallet = { balance: number; points: number; txns: { id: number; amount: number; kind: string; day: string }[]; rewards: { id: string; cost: number }[] };
const REWARD_ICON = { gym20: Dumbbell, coach: Salad, bottle: GlassWater, charity: HeartHandshake } as Record<string, typeof Dumbbell>;

export default function WalletPage() {
  const { t, n, money, date } = useT();
  const { data, error, reload, setData } = useApi<Wallet>("/wallet");
  const [msg, toast] = useToast();
  const [busy, setBusy] = useState(false);
  if (error) return <Failed retry={reload} />;
  if (!data) return <Loading />;

  const act = async (path: string, ok?: string) => {
    setBusy(true);
    try { setData(await post<Wallet>(path)); if (ok) toast(ok); }
    catch (e) { toast(t.err[(e as Error).message as keyof typeof t.err] ?? t.err.generic); }
    setBusy(false);
  };

  return (
    <>
      <Toast msg={msg} />
      <PageTitle title={t.nav.wallet} />
      <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-5">
          <section className="rise relative aspect-[1.6] max-h-72 w-full overflow-hidden rounded-[32px] p-6 text-white shadow-2xl md:p-8"
            style={{ background: "radial-gradient(120% 120% at 0% 0%, #ff2d55 0%, transparent 50%), radial-gradient(120% 120% at 100% 100%, #0a84ff 0%, transparent 55%), radial-gradient(80% 80% at 80% 10%, #30d158 0%, transparent 50%), #111" }}>
            <div aria-hidden className="absolute inset-0 bg-[linear-gradient(115deg,transparent_40%,rgb(255_255_255/0.18)_50%,transparent_60%)] bg-[length:250%_100%] animate-[shimmer_5s_linear_infinite]" />
            <div className="relative flex h-full flex-col">
              <div className="flex items-center justify-between">
                <span className="text-lg font-black">{t.brand}</span>
                <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-bold backdrop-blur">{t.demo}</span>
              </div>
              <p className="mt-auto text-sm font-semibold opacity-80">{t.balance}</p>
              <p className="text-4xl font-black md:text-5xl"><CountUp value={data.balance} format={money} /></p>
              <p className="mt-2 flex items-center gap-1.5 text-sm font-bold opacity-90"><Star size={15} fill="#ffd60a" stroke="#ffd60a" /> {n(data.points)} {t.points}</p>
            </div>
          </section>
          <button className="btn btn-primary w-full" disabled={busy} onClick={() => act("/wallet/topup")}><Plus size={18} /> {t.topup} · {money(500000)}</button>

          <section className="card rise p-5" style={css({ "--i": 2 })}>
            <h2 className="mb-3 text-xl font-black">{t.txns}</h2>
            <ul className="divide-y divide-line">
              {data.txns.map((x) => {
                const pos = x.amount > 0, Icon = pos ? ArrowDownLeft : ArrowUpRight;
                return (
                  <li key={x.id} className="flex items-center gap-3 py-3">
                    <span className={`grid h-10 w-10 place-items-center rounded-full ${pos ? "bg-good/15 text-good" : "bg-bad/15 text-bad"}`}><Icon size={18} /></span>
                    <div className="flex-1">
                      <p className="font-bold">{t.txn[x.kind]}</p>
                      <p className="text-xs text-muted">{date(x.day, { day: "numeric", month: "long" })}</p>
                    </div>
                    <b className={`tabular-nums ${pos ? "text-good" : "text-bad"}`}><span dir="ltr">{pos ? "+" : "−"}{n(Math.abs(x.amount))}</span></b>
                  </li>
                );
              })}
            </ul>
          </section>
        </div>

        <section className="rise" style={css({ "--i": 1 })}>
          <h2 className="mb-3 text-xl font-black">{t.rewards}</h2>
          <div className="grid grid-cols-2 gap-3">
            {data.rewards.map((r) => {
              const Icon = REWARD_ICON[r.id];
              return (
                <article key={r.id} className="card flex flex-col gap-3 p-5">
                  <span className="grid h-12 w-12 place-items-center rounded-2xl bg-soft"><Icon size={24} /></span>
                  <p className="font-bold leading-6">{t.reward[r.id]}</p>
                  <p className="flex items-center gap-1 text-sm font-bold text-muted"><Star size={14} /> {n(r.cost)}</p>
                  <button className="btn btn-ghost mt-auto h-10 w-full text-sm" disabled={busy || data.points < r.cost}
                    onClick={() => act(`/rewards/${r.id}/redeem`, t.redeemed)}>{t.redeem}</button>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </>
  );
}
