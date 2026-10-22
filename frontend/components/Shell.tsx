"use client";
import { Activity, Handshake, UserRound, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import Login from "./Login";
import { Toggles } from "./Toggles";
import { Failed, Loading } from "./ui";

const PUBLIC = ["/business"]; // aggregate-only page, readable without signing in

const NAV = [
  { href: "/", key: "today", icon: Activity },
  { href: "/pacts", key: "pacts", icon: Handshake },
  { href: "/wallet", key: "wallet", icon: Wallet },
  { href: "/community", key: "community", icon: Users },
  { href: "/account", key: "account", icon: UserRound },
] as const;

function Logo() {
  const { t } = useT();
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="mark" />
      <span className="text-xl font-black tracking-tight">{t.brand}</span>
    </Link>
  );
}

function Gate({ children }: { children: ReactNode }) {
  const { status, refresh } = useAuth();
  const { t } = useT();
  if (status === "loading") return <Loading />;
  if (status === "error") return <Failed retry={refresh} message={t.err.network} />;
  return <>{children}</>;
}

export default function Shell({ children }: { children: ReactNode }) {
  const { t } = useT();
  const { status } = useAuth();
  const path = usePathname();
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  const isPublic = PUBLIC.some((p) => path.startsWith(p));

  // Spotlight that follows a mouse over cards: fine pointers only, one write per frame, never on touch.
  useEffect(() => {
    if (!matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    let raf = 0, last: PointerEvent | null = null;
    const paint = () => {
      raf = 0;
      const el = (last?.target as Element | null)?.closest?.(".card") as HTMLElement | null;
      if (!el || !last) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--x", `${last.clientX - r.left}px`);
      el.style.setProperty("--y", `${last.clientY - r.top}px`);
    };
    const f = (e: PointerEvent) => { last = e; raf ||= requestAnimationFrame(paint); };
    addEventListener("pointermove", f, { passive: true });
    return () => { removeEventListener("pointermove", f); cancelAnimationFrame(raf); };
  }, []);

  if (status === "out" && !isPublic) return <><div className="aurora" aria-hidden /><main id="main"><Login /></main></>;

  return (
    <>
      <a href="#main" className="skip">{t.skip}</a>
      <div className="aurora" aria-hidden />

      <aside className="fixed inset-y-0 start-0 z-20 hidden w-64 p-4 md:block">
        <div className="glass flex h-full flex-col gap-1 rounded-[28px] p-4">
          <div className="mb-1 px-2 py-2"><Logo /></div>
          <p className="mb-5 px-2 text-xs font-semibold text-muted">{t.tagline}</p>
          <nav aria-label={t.brand} className="flex flex-col gap-1">
            {NAV.map(({ href, key, icon: Icon }) => (
              <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
                className={`flex min-h-12 items-center gap-3 rounded-2xl px-3 py-3 font-semibold transition-all duration-300 ${isActive(href) ? "bg-fg text-bg shadow-lg" : "text-muted hover:bg-soft hover:text-fg"}`}>
                <Icon size={20} strokeWidth={2.2} /> {t.nav[key]}
              </Link>
            ))}
          </nav>
          <div className="mt-auto px-1"><Toggles /></div>
        </div>
      </aside>

      <header className="glass sticky top-0 z-20 flex items-center justify-between border-x-0 border-t-0 px-4 pb-2.5 pt-[calc(10px+env(safe-area-inset-top))] md:hidden">
        <Logo />
        <Toggles />
      </header>

      <main id="main" className="md:ps-64">
        <div className="mx-auto max-w-5xl px-4 pb-32 pt-6 md:px-10 md:pb-12 md:pt-12">{isPublic ? children : <Gate>{children}</Gate>}</div>
      </main>

      <nav aria-label={t.brand} className="glass fixed inset-x-3 bottom-[calc(10px+env(safe-area-inset-bottom))] z-30 flex justify-between rounded-[30px] p-1.5 shadow-2xl md:hidden">
        {NAV.map(({ href, key, icon: Icon }) => (
          <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
            className={`flex min-h-12 flex-1 flex-col items-center justify-center gap-0.5 rounded-3xl py-2 text-[11px] font-bold transition-all duration-300 ${isActive(href) ? "bg-fg text-bg" : "text-muted"}`}>
            <Icon size={21} strokeWidth={2.2} /> {t.nav[key]}
          </Link>
        ))}
      </nav>
    </>
  );
}
