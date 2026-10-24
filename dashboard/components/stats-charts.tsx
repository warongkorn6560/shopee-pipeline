"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cx } from "./ui";

// Hand-built SVG charts for the stats page: stacked area (growth over time) and
// stacked horizontal bars (top clips). Series colours come from --viz-1..3.

const SERIES = [
  { key: "facebook", label: "Facebook", color: "var(--viz-1)" },
  { key: "instagram", label: "Instagram", color: "var(--viz-2)" },
  { key: "youtube", label: "YouTube", color: "var(--viz-3)" },
] as const;
type Key = (typeof SERIES)[number]["key"];
type Values = Record<Key, number>;

const fmt = (n: number) => new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
const full = (n: number) => new Intl.NumberFormat("th-TH").format(n);

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function niceMax(v: number) {
  if (v <= 0) return 10;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v)!;
}

export function Legend({ present }: { present?: Key[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {SERIES.filter((s) => !present || present.includes(s.key)).map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  const left = Math.min(Math.max(x + 14, 0), width - 190);
  return (
    <div className="pointer-events-none absolute z-10 w-[180px] rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-card"
      style={{ left, top: Math.max(0, y - 10) }}>
      {children}
    </div>
  );
}

function Rows({ v }: { v: Values }) {
  const total = SERIES.reduce((t, s) => t + v[s.key], 0);
  return (
    <>
      {SERIES.map((s) => (
        <div key={s.key} className="flex items-center justify-between gap-2 py-0.5">
          <span className="flex items-center gap-1.5 text-ink-2"><span className="size-2 rounded-sm" style={{ background: s.color }} />{s.label}</span>
          <span className="tabular text-ink">{full(v[s.key])}</span>
        </div>
      ))}
      <div className="mt-1 flex justify-between border-t border-line pt-1 font-medium text-ink"><span>รวม</span><span className="tabular">{full(total)}</span></div>
    </>
  );
}

/** Cumulative views over time, stacked by platform, with a crosshair tooltip. */
export function GrowthChart({ points }: { points: ({ t: number } & Values)[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const H = 240, pad = { l: 44, r: 12, t: 12, b: 26 };
  if (points.length < 2) {
    return <p className="py-12 text-center text-sm text-ink-3">ต้องมีข้อมูลอย่างน้อย 2 รอบก่อนจะเห็นกราฟการเติบโต — ระบบดึงยอดวิวทุกชั่วโมง</p>;
  }
  const iw = width - pad.l - pad.r, ih = H - pad.t - pad.b;
  const t0 = points[0].t, t1 = points[points.length - 1].t;
  const x = (t: number) => pad.l + ((t - t0) / Math.max(1, t1 - t0)) * iw;
  const max = niceMax(Math.max(...points.map((p) => p.facebook + p.instagram + p.youtube)));
  const y = (v: number) => pad.t + ih - (v / max) * ih;
  // Stack bottom-up: facebook, instagram, youtube.
  const bands = SERIES.map((s, i) => {
    const lower = (p: Values) => SERIES.slice(0, i).reduce((t, q) => t + p[q.key], 0);
    const top = points.map((p) => `${x(p.t)},${y(lower(p) + p[s.key])}`);
    const bottom = [...points].reverse().map((p) => `${x(p.t)},${y(lower(p))}`);
    const line = points.map((p, j) => `${j ? "L" : "M"}${x(p.t)},${y(lower(p) + p[s.key])}`).join(" ");
    return { ...s, area: `M${top.join(" L")} L${bottom.join(" L")} Z`, line };
  });
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const span = t1 - t0;
  const label = (t: number) => new Date(t).toLocaleString("th-TH", span > 2 * 86_400_000
    ? { day: "numeric", month: "short", timeZone: "Asia/Bangkok" }
    : { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Bangkok" });
  const xticks = [0, 0.33, 0.66, 1].map((f) => t0 + f * span);
  const hp = hover === null ? null : points[hover];

  return (
    <div ref={ref} className="relative w-full min-w-0 overflow-hidden">
      <svg className="block" width={width} height={H} role="img" aria-label="ยอดวิวสะสมตามเวลา แยกตามแพลตฟอร์ม"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const mx = e.clientX - r.left;
          let best = 0;
          points.forEach((p, i) => { if (Math.abs(x(p.t) - mx) < Math.abs(x(points[best].t) - mx)) best = i; });
          setHover(best);
        }}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={width - pad.r} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeDasharray={v ? "2 4" : undefined} />
            <text x={pad.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="fill-ink-3 text-[10px] tabular">{fmt(v)}</text>
          </g>
        ))}
        {xticks.map((t, i) => (
          <text key={i} x={x(t)} y={H - 8} textAnchor={i === 0 ? "start" : i === xticks.length - 1 ? "end" : "middle"} className="fill-ink-3 text-[10px]">{label(t)}</text>
        ))}
        {bands.map((b) => (
          <g key={b.key}>
            <path d={b.area} fill={b.color} fillOpacity={0.22} />
            <path d={b.line} fill="none" stroke={b.color} strokeWidth={2} strokeLinejoin="round" />
          </g>
        ))}
        {hp && (
          <g>
            <line x1={x(hp.t)} x2={x(hp.t)} y1={pad.t} y2={pad.t + ih} stroke="var(--ink-3)" strokeDasharray="3 3" />
            {bands.map((b, i) => {
              const v = SERIES.slice(0, i + 1).reduce((t, q) => t + hp[q.key], 0);
              return <circle key={b.key} cx={x(hp.t)} cy={y(v)} r={4} fill={b.color} stroke="var(--surface)" strokeWidth={2} />;
            })}
          </g>
        )}
      </svg>
      {hp && (
        <Tooltip x={x(hp.t)} y={pad.t} width={width}>
          <div className="mb-1 font-medium text-ink">{new Date(hp.t).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" })}</div>
          <Rows v={hp} />
        </Tooltip>
      )}
    </div>
  );
}

/** Top clips by total views, each bar stacked by platform. */
export function TopClipsChart({ clips }: { clips: ({ id: string; title: string } & Values)[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  if (!clips.length) return <p className="py-12 text-center text-sm text-ink-3">ยังไม่มีสถิติในช่วงนี้</p>;
  const rowH = 34, labelW = Math.min(240, Math.round(width * 0.38)), valueW = 52;
  const iw = width - labelW - valueW - 8;
  const max = Math.max(...clips.map((c) => c.facebook + c.instagram + c.youtube), 1);
  return (
    <div ref={ref} className="relative w-full min-w-0 overflow-hidden">
      <svg className="block" width={width} height={clips.length * rowH} role="img" aria-label="คลิปที่มียอดวิวสูงสุด">
        {clips.map((c, i) => {
          const total = c.facebook + c.instagram + c.youtube;
          let acc = 0;
          return (
            <g key={c.id} transform={`translate(0 ${i * rowH})`}
              onMouseMove={(e) => {
                const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                setHover({ i, x: e.clientX - r.left, y: i * rowH });
              }}
              onMouseLeave={() => setHover(null)}>
              <rect x={0} y={0} width={width} height={rowH} fill="transparent" />
              <text x={0} y={rowH / 2} dy="0.32em" className="fill-ink-2 text-[12px]">
                {c.title.length > 26 && labelW < 240 ? c.title.slice(0, 24) + "…" : c.title.length > 34 ? c.title.slice(0, 32) + "…" : c.title}
              </text>
              {SERIES.map((s) => {
                const w = (c[s.key] / max) * iw;
                const x0 = labelW + acc;
                acc += w;
                return w > 0 ? <rect key={s.key} x={x0} y={8} width={Math.max(w - 2, 1)} height={rowH - 16} rx={3} fill={s.color} /> : null;
              })}
              <text x={labelW + (total / max) * iw + 6} y={rowH / 2} dy="0.32em" className="fill-ink text-[12px] font-medium tabular">{fmt(total)}</text>
            </g>
          );
        })}
      </svg>
      {hover && (
        <Tooltip x={hover.x} y={hover.y} width={width}>
          <div className="mb-1 line-clamp-2 font-medium text-ink">{clips[hover.i].title}</div>
          <Rows v={clips[hover.i]} />
        </Tooltip>
      )}
    </div>
  );
}

export function ChartCard({ title, eyebrow, children, legend, className }: {
  title: string; eyebrow?: string; children: ReactNode; legend?: ReactNode; className?: string;
}) {
  return (
    <section className={cx("min-w-0 rounded-2xl border border-line bg-surface p-5 shadow-card", className)}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
          <h2 className="font-display text-[17px] font-semibold text-ink">{title}</h2>
        </div>
        {legend}
      </div>
      {children}
    </section>
  );
}
