"use client";

import { useEffect, useState, type ReactNode } from "react";
import { cx } from "./ui";

export type Tab = { id: string; label: string; badge?: ReactNode; content: ReactNode };

// Old deep links (#social, #github) land on the tab that now holds them.
const ALIASES: Record<string, string> = { social: "channels", github: "overview" };

/** Tabs kept in the URL hash, so /settings#channels links straight to a tab. */
export function SettingsTabs({ tabs }: { tabs: Tab[] }) {
  const [active, setActive] = useState(tabs[0].id);
  useEffect(() => {
    const sync = () => {
      const h = decodeURIComponent(location.hash.slice(1));
      const id = ALIASES[h] ?? h;
      if (tabs.some((t) => t.id === id)) setActive(id);
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [tabs]);

  const choose = (id: string) => {
    setActive(id);
    history.replaceState(null, "", `${location.pathname}${location.search}#${id}`);
  };

  return (
    <div className="space-y-5">
      <div role="tablist" aria-label="หมวดการตั้งค่า" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={active === t.id}
            onClick={() => choose(t.id)}
            className={cx(
              "flex shrink-0 items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-colors",
              active === t.id ? "bg-ink text-surface" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
            )}
          >
            {t.label}
            {t.badge}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div key={t.id} role="tabpanel" hidden={active !== t.id} className="space-y-5">
          {t.content}
        </div>
      ))}
    </div>
  );
}
