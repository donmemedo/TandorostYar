"use client";
import { Activity, Building2, Handshake, Languages, Moon, Sun, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, type MouseEvent, type ReactNode } from "react";
import { useT } from "@/lib/i18n";

const NAV = [
  { href: "/", key: "today", icon: Activity },
  { href: "/pacts", key: "pacts", icon: Handshake },
  { href: "/wallet", key: "wallet", icon: Wallet },
  { href: "/community", key: "community", icon: Users },
  { href: "/business", key: "business", icon: Building2 },
] as const;

function toggleTheme(e: MouseEvent) {
  const root = document.documentElement;
  const next = root.dataset.theme === "dark" ? "light" : "dark";
  const apply = () => {
    root.dataset.theme = next;
    try { localStorage.theme = next; } catch {}
  };
  if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return apply();
  const { clientX: x, clientY: y } = e;
  const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  root.classList.add("vt-theme");
  const vt = document.startViewTransition(apply);
  vt.ready.then(() => root.animate(
    { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
    { duration: 700, easing: "cubic-bezier(.2,.8,.2,1)", pseudoElement: "::view-transition-new(root)" },
  ));
  vt.finished.finally(() => root.classList.remove("vt-theme"));
}

function Toggles() {
  const { t, lang, setLang } = useT();
  return (
    <div className="flex items-center gap-2">
      <button className="icon-btn" onClick={toggleTheme} aria-label={t.theme} title={t.theme}>
        <Moon size={18} className="dark:hidden" />
        <Sun size={18} className="hidden dark:block" />
      </button>
      <button className="icon-btn w-auto! flex! gap-1.5 px-3 text-sm font-bold" onClick={() => setLang(lang === "fa" ? "en" : "fa")} aria-label={t.langSwitch}>
        <Languages size={16} /> {t.langSwitch}
      </button>
    </div>
  );
}

function Logo() {
  const { t } = useT();
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="mark" />
      <span className="text-xl font-black tracking-tight">{t.brand}</span>
    </Link>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const { t } = useT();
  const path = usePathname();
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  // Spotlight that follows the pointer on cards
  useEffect(() => {
    const f = (e: PointerEvent) => {
      const el = (e.target as Element).closest?.(".card") as HTMLElement | null;
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--x", `${e.clientX - r.left}px`);
      el.style.setProperty("--y", `${e.clientY - r.top}px`);
    };
    addEventListener("pointermove", f, { passive: true });
    return () => removeEventListener("pointermove", f);
  }, []);

  return (
    <>
      <div className="aurora" aria-hidden><i /><i /><i /></div>

      <aside className="fixed inset-y-0 start-0 z-20 hidden w-64 p-4 md:block">
        <div className="glass flex h-full flex-col gap-1 rounded-[28px] p-4">
          <div className="mb-1 px-2 py-2"><Logo /></div>
          <p className="mb-5 px-2 text-xs font-semibold text-muted">{t.tagline}</p>
          {NAV.map(({ href, key, icon: Icon }) => (
            <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
              className={`flex items-center gap-3 rounded-2xl px-3 py-3 font-semibold transition-all duration-300 ${isActive(href) ? "bg-fg text-bg shadow-lg" : "text-muted hover:bg-soft hover:text-fg"}`}>
              <Icon size={20} strokeWidth={2.2} /> {t.nav[key]}
            </Link>
          ))}
          <div className="mt-auto px-1"><Toggles /></div>
        </div>
      </aside>

      <header className="glass sticky top-0 z-20 flex items-center justify-between border-x-0 border-t-0 px-4 pb-2.5 pt-[calc(10px+env(safe-area-inset-top))] md:hidden">
        <Logo />
        <Toggles />
      </header>

      <main className="md:ps-64">
        <div className="mx-auto max-w-5xl px-4 pb-32 pt-6 md:px-10 md:pb-12 md:pt-12">{children}</div>
      </main>

      <nav className="glass fixed inset-x-3 bottom-[calc(10px+env(safe-area-inset-bottom))] z-30 flex justify-between rounded-[30px] p-1.5 shadow-2xl md:hidden">
        {NAV.map(({ href, key, icon: Icon }) => (
          <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-0.5 rounded-3xl py-2 text-[10px] font-bold transition-all duration-300 ${isActive(href) ? "bg-fg text-bg" : "text-muted"}`}>
            <Icon size={21} strokeWidth={2.2} /> {t.nav[key]}
          </Link>
        ))}
      </nav>
    </>
  );
}
