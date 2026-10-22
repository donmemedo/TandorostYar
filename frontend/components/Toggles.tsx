"use client";
import { Languages, Moon, Sun } from "lucide-react";
import type { MouseEvent } from "react";
import { useT } from "@/lib/i18n";

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

export function Toggles() {
  const { t, lang, setLang } = useT();
  return (
    <div className="flex items-center gap-2">
      <button className="icon-btn" onClick={toggleTheme} aria-label={t.theme} title={t.theme}>
        <Moon size={18} className="dark:hidden" />
        <Sun size={18} className="hidden dark:block" />
      </button>
      <button className="icon-btn !flex !h-11 !w-auto gap-1.5 px-3 text-sm font-bold" onClick={() => setLang(lang === "fa" ? "en" : "fa")} aria-label={t.langSwitch}>
        <Languages size={16} /> {t.langSwitch}
      </button>
    </div>
  );
}

