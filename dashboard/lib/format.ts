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

const validHour = (h: number) => Number.isInteger(h) && h >= 0 && h <= 23;

/** "9,13,19" → [9, 13, 19] (Bangkok hours). */
export function parseHours(v: string): number[] {
  const hs = v.split(",").map((s) => s.trim()).filter(Boolean).map(Number).filter(validHour);
  return [...new Set(hs)].sort((a, b) => a - b);
}

export const hourText = (h: number) => `${String(h).padStart(2, "0")}:00`;

export function hoursLabel(hours: number[]): string {
  return hours.length ? `ทุกวัน ${hours.map(hourText).join(", ")} น.` : "—";
}

/** Next start of one of these Bangkok (UTC+7) hours. */
export function nextAtHours(hours: number[], now = new Date()): Date | null {
  const BKK = 7 * 3_600_000;
  const local = new Date(now.getTime() + BKK);
  for (let day = 0; day < 2; day++) {
    for (const h of hours) {
      const t = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate() + day, h) - BKK;
      if (t > now.getTime()) return new Date(t);
    }
  }
  return null;
}

export function bytes(n: number): string {
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function number(n: number): string {
  return new Intl.NumberFormat("th-TH").format(n);
}
