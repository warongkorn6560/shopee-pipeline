import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, XCircle } from "lucide-react";

export type Tone = "ok" | "warn" | "bad" | "idle" | "live";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ children, className, as: Tag = "section" }: {
  children: ReactNode; className?: string; as?: "section" | "div" | "article";
}) {
  return (
    <Tag className={cx("rounded-2xl border border-line bg-surface shadow-card", className)}>{children}</Tag>
  );
}

export function CardHeader({ title, eyebrow, action, className }: {
  title: ReactNode; eyebrow?: ReactNode; action?: ReactNode; className?: string;
}) {
  return (
    <div className={cx("flex flex-wrap items-center justify-between gap-3 px-5 pt-5", className)}>
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h2 className="font-display text-[17px] font-semibold leading-tight text-ink">{title}</h2>
      </div>
      {action}
    </div>
  );
}

const TALLY: Record<Tone, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
  idle: "bg-ink-3/50",
  live: "bg-live tally-live",
};

export function Tally({ tone, className }: { tone: Tone; className?: string }) {
  return <span aria-hidden className={cx("inline-block size-2.5 shrink-0 rounded-full", TALLY[tone], className)} />;
}

const PILL: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  idle: "bg-surface-2 text-ink-2 ring-1 ring-inset ring-line",
  live: "bg-live text-white",
};

export function Pill({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cx(
      "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium",
      PILL[tone], className,
    )}>
      {tone === "live" && <span className="size-1.5 rounded-full bg-white tally-live" />}
      {children}
    </span>
  );
}

export function StateIcon({ tone, className }: { tone: Tone; className?: string }) {
  const cls = cx("size-4 shrink-0", className);
  if (tone === "ok") return <CheckCircle2 className={cx(cls, "text-ok")} aria-label="พร้อม" />;
  if (tone === "warn") return <AlertTriangle className={cx(cls, "text-warn")} aria-label="ต้องดู" />;
  if (tone === "bad") return <XCircle className={cx(cls, "text-bad")} aria-label="มีปัญหา" />;
  return <CircleDashed className={cx(cls, "text-ink-3")} aria-label="ไม่ทราบ" />;
}

export const btn = {
  base: "inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
  primary: "bg-ink text-surface hover:bg-ink/85",
  secondary: "border border-line-strong bg-surface text-ink hover:bg-surface-2",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
  danger: "bg-bad text-white hover:bg-bad/90",
};

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-[28px] font-semibold leading-none tracking-tight text-ink sm:text-[32px]">{title}</h1>
        {subtitle && <p className="mt-2 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("skeleton", className)} />;
}

export function InlineError({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad">
      <XCircle className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">
        <div className="font-medium">{title}</div>
        {detail && <div className="mt-0.5 break-words text-bad/80">{detail}</div>}
      </div>
    </div>
  );
}

export function FlowTag({ flow, className }: { flow: "shopee" | "story"; className?: string }) {
  return (
    <span className={cx(
      "inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 font-display text-[11px] font-semibold uppercase tracking-wide",
      flow === "shopee" ? "bg-shopee-soft text-shopee" : "bg-story-soft text-story",
      className,
    )}>
      <span className={cx("size-1.5 rounded-full", flow === "shopee" ? "bg-shopee" : "bg-story-mark")} />
      {flow === "shopee" ? "Flow A" : "Flow B"}
    </span>
  );
}
