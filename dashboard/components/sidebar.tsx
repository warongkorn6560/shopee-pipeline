"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clapperboard, ExternalLink, LayoutDashboard, ListChecks, LogOut, Receipt, SlidersHorizontal } from "lucide-react";
import { logout } from "@/app/(app)/actions";
import { cx } from "./ui";

const NAV = [
  { href: "/", label: "ภาพรวม", icon: LayoutDashboard },
  { href: "/review", label: "รีวิววิดีโอ", short: "รีวิว", icon: Clapperboard },
  { href: "/queue", label: "คิวงาน", icon: ListChecks },
  { href: "/settings", label: "ตั้งค่า", icon: SlidersHorizontal },
  { href: "/services", label: "บริการ & ค่าใช้จ่าย", short: "บริการ", icon: Receipt },
] as const;

function useActive() {
  const path = usePathname();
  return (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
}

export function Sidebar({ repo }: { repo: string }) {
  const isActive = useActive();
  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r border-line bg-surface px-4 py-6 md:flex">
      <Link href="/" className="mb-8 flex items-center gap-3 px-2">
        <Mark />
        <div className="min-w-0">
          <div className="font-display text-[15px] font-semibold leading-none text-ink">Pipeline Control</div>
          <div className="mt-1 truncate text-[11px] text-ink-3">วิดีโออัตโนมัติ 2 flow</div>
        </div>
      </Link>
      <nav className="flex flex-col gap-1" aria-label="หลัก">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            aria-current={isActive(href) ? "page" : undefined}
            className={cx(
              "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
              isActive(href) ? "bg-ink text-surface" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto space-y-1 border-t border-line pt-4">
        <a
          href={`https://github.com/${repo}/actions`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink"
        >
          <ExternalLink className="size-4" />
          GitHub Actions
        </a>
        <form action={logout}>
          <button type="submit" className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink">
            <LogOut className="size-4" />
            ออกจากระบบ
          </button>
        </form>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const isActive = useActive();
  return (
    <>
      <div className="sticky top-[env(safe-area-inset-top,0px)] z-30 flex items-center justify-between border-b border-line bg-surface/90 px-4 py-3 backdrop-blur md:hidden">
        <Link href="/" className="flex items-center gap-2.5">
          <Mark small />
          <span className="font-display text-[15px] font-semibold text-ink">Pipeline Control</span>
        </Link>
        <form action={logout}>
          <button type="submit" aria-label="ออกจากระบบ" className="rounded-lg p-2 text-ink-2 hover:bg-surface-2">
            <LogOut className="size-4" />
          </button>
        </form>
      </div>
      <nav
        aria-label="หลัก"
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom,0px)] backdrop-blur md:hidden"
      >
        {NAV.map(({ href, label, icon: Icon, ...rest }) => (
          <Link
            key={href}
            href={href}
            aria-current={isActive(href) ? "page" : undefined}
            className={cx(
              "flex flex-col items-center gap-1 py-2.5 text-[11px]",
              isActive(href) ? "text-ink" : "text-ink-3",
            )}
          >
            <Icon className={cx("size-5", isActive(href) && "text-shopee")} />
            {"short" in rest ? rest.short : label}
          </Link>
        ))}
      </nav>
    </>
  );
}

function Mark({ small }: { small?: boolean }) {
  return (
    <svg viewBox="0 0 64 64" className={small ? "size-7" : "size-9"} aria-hidden>
      <rect width="64" height="64" rx="14" className="fill-ink" />
      <rect x="10" y="40" width="20" height="6" rx="3" fill="#e8452a" />
      <rect x="34" y="40" width="20" height="6" rx="3" fill="#f2b544" />
      <circle cx="32" cy="24" r="9" fill="#e5322d" />
    </svg>
  );
}
