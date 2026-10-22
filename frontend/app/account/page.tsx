"use client";
import { Building2, Check, ChevronLeft, ChevronRight, LogOut, MonitorSmartphone, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ConfirmSheet, PageTitle, Toast, css, useToast } from "@/components/ui";
import { Toggles } from "@/components/Toggles";
import { del, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { errText, useT } from "@/lib/i18n";

export default function Account() {
  const { t, n, lang } = useT();
  const { me, logout, setName } = useAuth();
  const [name, setDraft] = useState<string>();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, toast] = useToast();
  if (!me) return null;
  const shown = name ?? (lang === "fa" ? me.name : me.name_en);
  const Chevron = lang === "fa" ? ChevronLeft : ChevronRight;
  const phone = me.phone ? `${me.phone.slice(0, 4)} ${me.phone.slice(4, 7)} ${me.phone.slice(7)}` : "";

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try { const r = await patch<{ name: string }>("/me", { name: shown }); setName(r.name); setDraft(undefined); toast(t.account.saved); }
    catch (er) { toast(errText(t, er)); }
    setBusy(false);
  };
  const logoutAll = async () => {
    try { await post("/auth/logout-all"); await logout(); }
    catch (er) { toast(errText(t, er)); }
  };
  const remove = async () => {
    setBusy(true);
    try { await del("/me"); await logout(); }
    catch (er) { setAsking(false); toast(errText(t, er)); setBusy(false); }
  };

  return (
    <>
      <Toast msg={msg} />
      <PageTitle title={t.nav.account} sub={t.account.sub} />
      <div className="mx-auto grid max-w-3xl gap-4">
        <form onSubmit={save} className="card rise space-y-4 p-6" style={css({ "--i": 1 })}>
          <label className="block">
            <span className="mb-1 block text-sm font-bold">{t.account.name}</span>
            <span className="mb-2 block text-xs text-muted">{t.account.nameHint}</span>
            <input className="field" value={shown} maxLength={30} onChange={(e) => setDraft(e.target.value)} autoComplete="nickname" />
          </label>
          <button className="btn btn-primary w-full" disabled={busy || name === undefined || !name.trim()}><Check size={18} aria-hidden /> {t.save}</button>
        </form>

        <dl className="card rise divide-y divide-line px-6" style={css({ "--i": 2 })}>
          <div className="flex items-center justify-between py-4"><dt className="font-semibold text-muted">{t.account.phone}</dt><dd className="font-black tabular-nums" dir="ltr">{phone}</dd></div>
          <div className="flex items-center justify-between py-4"><dt className="font-semibold text-muted">{t.balance}</dt><dd className="font-black tabular-nums">{n(me.balance)} {t.toman}</dd></div>
          <div className="flex items-center justify-between py-3"><dt className="font-semibold text-muted">{t.account.language} · {t.account.theme}</dt><dd><Toggles /></dd></div>
        </dl>

        <Link href="/business" className="card rise flex items-center gap-4 p-5" style={css({ "--i": 3 })}>
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-soft"><Building2 size={22} aria-hidden /></span>
          <span className="flex-1"><b className="block">{t.account.forTeams}</b><span className="text-sm text-muted">{t.account.forTeamsHint}</span></span>
          <Chevron size={20} className="text-muted" aria-hidden />
        </Link>

        <div className="rise grid gap-2 sm:grid-cols-3" style={css({ "--i": 4 })}>
          <button className="btn btn-ghost" onClick={() => void logout()}><LogOut size={18} aria-hidden /> {t.account.logout}</button>
          <button className="btn btn-ghost" onClick={() => void logoutAll()}><MonitorSmartphone size={18} aria-hidden /> {t.account.logoutAll}</button>
          <button className="btn btn-danger" onClick={() => setAsking(true)}><Trash2 size={18} aria-hidden /> {t.account.del}</button>
        </div>
      </div>
      <ConfirmSheet open={asking} title={t.account.delTitle} body={t.account.delBody} confirm={t.account.delConfirm} danger busy={busy} onConfirm={remove} onClose={() => setAsking(false)} />
    </>
  );
}
