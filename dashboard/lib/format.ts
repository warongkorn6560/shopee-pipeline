const TZ = "Asia/Bangkok";

export function thaiDateTime(iso: string | number | Date): string {
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: TZ, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

export function thaiDate(iso: string | number | Date): string {
  return new Intl.DateTimeFormat("th-TH", { timeZone: TZ, day: "numeric", month: "short", year: "numeric" })
    .format(new Date(iso));
}

export function relative(iso: string | number | Date, now = Date.now()): string {
  const diff = new Date(iso).getTime() - now;
  const rtf = new Intl.RelativeTimeFormat("th", { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60_000) return rtf.format(Math.round(diff / 1000), "second");
  if (abs < 3_600_000) return rtf.format(Math.round(diff / 60_000), "minute");
  if (abs < 86_400_000) return rtf.format(Math.round(diff / 3_600_000), "hour");
  return rtf.format(Math.round(diff / 86_400_000), "day");
}

/** Broadcast-style timecode: 1:07 or 0:42. */
export function timecode(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Next fire time of a simple daily "m h * * *" UTC cron. */
export function nextDailyRun(cron: string, now = new Date()): Date | null {
  const [m, h, dom, mon, dow] = cron.split(" ");
  if (dom !== "*" || mon !== "*" || dow !== "*") return null;
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), Number(h), Number(m)));
  if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
  return next;
}

export function bytes(n: number): string {
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function number(n: number): string {
  return new Intl.NumberFormat("th-TH").format(n);
}
