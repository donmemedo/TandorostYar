"use client";
import { ArrowLeft, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toLatin } from "@/lib/digits";
import { errText, useT } from "@/lib/i18n";
import { Toggles } from "./Toggles";

/** Phone number, then a 6-digit code: one flow for both sign-in and sign-up. */
export default function Login() {
  const { t, lang, n } = useT();
  const { refresh } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<string>();
  const [left, setLeft] = useState(0);
  const input = useRef<HTMLInputElement>(null), errId = useId();
  const Back = lang === "fa" ? ArrowRight : ArrowLeft;

  useEffect(() => { input.current?.focus(); }, [step]);
  useEffect(() => {
    if (left <= 0) return;
    const id = setTimeout(() => setLeft((l) => l - 1), 1000);
    return () => clearTimeout(id);
  }, [left]);

  const send = async () => {
    setBusy(true); setErr("");
    try {
      const r = await post<{ ttl: number; code?: string }>("/auth/otp", { phone });
      setDemo(r.code); setCode(""); setLeft(60); setStep("code");
    } catch (e) { setErr(errText(t, e)); }
    setBusy(false);
  };
  const verify = async (c: string) => {
    setBusy(true); setErr("");
    try {
      const r = await post<{ new: boolean }>("/auth/verify", { phone, code: c });
      await refresh();
      if (r.new) router.replace("/account"); // first visit: land where the handle can be changed
    }
    catch (e) { setErr(errText(t, e)); setCode(""); setBusy(false); input.current?.focus(); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); if (step === "phone") void send(); else if (code.length === 6) void verify(code); };
  const phoneOk = toLatin(phone).replace(/\D/g, "").length >= 10;

  return (
    <div className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="fixed end-4 top-4 z-10"><Toggles /></div>
      <div className="w-full max-w-md">
        <div className="rise mb-8 text-center">
          <span className="mark mx-auto mb-5 block !h-16 !w-16" aria-hidden />
          <p className="brand-text text-lg font-black">{t.brand}</p>
        </div>

        <form key={step} onSubmit={submit} className="card rise space-y-5 p-6 md:p-8" style={{ "--i": 1 } as React.CSSProperties} noValidate>
          {step === "phone" ? (
            <>
              <div>
                <h1 className="text-3xl font-black">{t.login.title}</h1>
                <p className="mt-2 leading-7 text-muted">{t.login.sub}</p>
              </div>
              <label className="block">
                <span className="mb-2 block text-sm font-bold">{t.login.phone}</span>
                <input ref={input} className="field text-start" dir="ltr" type="tel" inputMode="tel" autoComplete="tel" name="phone" placeholder="09123456789"
                  value={phone} onChange={(e) => setPhone(toLatin(e.target.value))} aria-invalid={!!err} aria-describedby={err ? errId : undefined} maxLength={20} />
              </label>
            </>
          ) : (
            <>
              <button type="button" className="flex items-center gap-1.5 text-sm font-bold text-muted" onClick={() => { setStep("phone"); setErr(""); }}>
                <Back size={16} /> {t.login.edit}
              </button>
              <div>
                <h1 className="text-3xl font-black">{t.login.codeTitle}</h1>
                <p className="mt-2 leading-7 text-muted">{t.login.codeSub("\u2066" + toLatin(phone).trim() + "\u2069")}</p>
              </div>
              <label className="block">
                <span className="sr-only">{t.login.code}</span>
                <input ref={input} className="field text-center text-3xl tabular-nums" dir="ltr" inputMode="numeric" autoComplete="one-time-code" name="code" placeholder="••••••"
                  value={code} readOnly={busy} aria-invalid={!!err} aria-describedby={err ? errId : undefined}
                  onChange={(e) => { const v = toLatin(e.target.value).replace(/\D/g, "").slice(0, 6); setCode(v); if (v.length === 6) void verify(v); }} />
              </label>
              {demo && (
                <button type="button" className="chip w-full" onClick={() => { setCode(demo); void verify(demo); }}>
                  <Sparkles size={16} /> {t.login.demoCode}: <b className="tabular-nums" dir="ltr">{demo}</b>
                </button>
              )}
            </>
          )}

          {err && <p id={errId} role="alert" className="text-sm font-bold text-bad">{err}</p>}

          {step === "phone" ? (
            <button className="btn btn-primary h-14 w-full text-base" type="submit" disabled={!phoneOk || busy}>
              {busy ? <Loader2 className="animate-spin" size={20} /> : t.login.send}
            </button>
          ) : (
            <div className="space-y-2">
              <button className="btn btn-primary h-14 w-full text-base" type="submit" disabled={code.length < 6 || busy}>
                {busy ? <Loader2 className="animate-spin" size={20} /> : t.login.verify}
              </button>
              <button type="button" className="btn btn-ghost w-full" disabled={left > 0 || busy} onClick={() => void send()}>
                {left > 0 ? t.login.resendIn(n(left)) : t.login.resend}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
