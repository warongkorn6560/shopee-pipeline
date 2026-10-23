import {
  ArrowUpRight, AudioLines, BookOpen, Clapperboard, Download, ImageIcon, Inbox, Map as MapIcon,
  PenLine, Send, type LucideIcon,
} from "lucide-react";
import { requireSession } from "@/lib/dal";
import { loadContext } from "@/lib/context";
import { getRecentRuns, getRunsFor, effective } from "@/lib/data";
import { FLOWS, VARIABLES, flowById, type FlowId, type StepKey } from "@/lib/flows";
import { bytes, nextDailyRun, number, relative, thaiDate, thaiDateTime, timecode } from "@/lib/format";
import * as gh from "@/lib/github";
import { attention, runLabel, runTone, stepStatuses } from "@/lib/status";
import { AutoRefresh, RunButton, ScheduleToggle } from "./controls";
import { Card, CardHeader, FlowTag, InlineError, Pill, Skeleton, StateIcon, Tally, cx, type Tone } from "./ui";

const STEP_ICON: Record<FlowId, Record<StepKey, LucideIcon>> = {
  shopee: { input: Inbox, script: PenLine, visual: ImageIcon, voice: AudioLines, render: Clapperboard, deliver: Send },
  story: { input: BookOpen, script: PenLine, visual: MapIcon, voice: AudioLines, render: Clapperboard, deliver: Send },
};

const RING: Record<Tone, string> = {
  ok: "border-ok/40 text-ok bg-ok-soft",
  warn: "border-warn/50 text-warn bg-warn-soft",
  bad: "border-bad/50 text-bad bg-bad-soft",
  idle: "border-line-strong text-ink-3 bg-surface-2",
  live: "border-live text-live bg-bad-soft",
};

const duration = (r: gh.Run) =>
  timecode(new Date(r.updated_at).getTime() - new Date(r.run_started_at || r.created_at).getTime());

// ---------------------------------------------------------------------------
export async function FlowPanel({ flowId }: { flowId: FlowId }) {
  await requireSession();
  const flow = flowById(flowId)!;
  const ctx = await loadContext();
  const primary = flow.workflows.find((w) => w.primary)!;
  const wf = ctx.workflows?.get(primary.file);
  const runsRes = ctx.github ? await getRunsFor(primary.file) : null;
  const latest = runsRes?.ok ? runsRes.value[0] : undefined;
  const steps = stepStatuses(flow, ctx);
  const enabled = wf?.state === "active";
  const accent = flow.id === "shopee" ? "bg-shopee" : "bg-story-mark";

  let extra: { failedStep?: string | null; artifact?: gh.Artifact } = {};
  if (latest?.status === "completed") {
    try {
      if (latest.conclusion === "failure") extra.failedStep = await gh.failedStep(latest.id);
      else if (latest.conclusion === "success") extra.artifact = (await gh.runArtifacts(latest.id))[0];
    } catch {
      extra = {};
    }
  }

  const mode = effective(ctx.vars, flow.publishVar);
  const modeLabel = VARIABLES.find((v) => v.name === flow.publishVar)?.options?.find((o) => o.value === mode)?.label ?? mode;
  const next = enabled ? nextDailyRun(primary.cron) : null;
  const isLive = latest ? latest.status !== "completed" : false;
  const stateTone: Tone = isLive ? "live" : !ctx.github ? "idle" : !wf ? "warn" : enabled ? "ok" : "idle";
  const stateLabel = isLive ? "ON AIR" : !ctx.github ? "ไม่ได้เชื่อม GitHub" : !wf ? "ยังไม่มี workflow" : enabled ? "รันตามเวลา" : "หยุดอยู่";
  const visualVar = flow.id === "shopee" ? "รูปสินค้าจริง" : effective(ctx.vars, "STORY_IMAGE_PROVIDER");

  return (
    <Card as="article" className="relative overflow-hidden">
      <AutoRefresh active={isLive} />
      <div className={cx("absolute inset-y-0 left-0 w-1", accent)} aria-hidden />
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 pl-6">
        <div className="min-w-0">
          <FlowTag flow={flow.id} />
          <h2 className="mt-2 font-display text-[22px] font-semibold leading-tight text-ink">{flow.name}</h2>
          <p className="mt-1 text-sm text-ink-2">{flow.tagline}</p>
        </div>
        <Pill tone={stateTone}>{stateTone !== "live" && <Tally tone={stateTone} className="size-1.5" />}{stateLabel}</Pill>
      </div>

      <ol className="mt-5 grid grid-cols-3 gap-y-4 px-6 sm:grid-cols-6" aria-label={`ขั้นตอน ${flow.name}`}>
        {steps.map((s, i) => {
          const Icon = STEP_ICON[flow.id][s.key];
          return (
            <li key={s.key} className="relative flex min-w-0 flex-col items-center text-center">
              {i > 0 && <span aria-hidden className="absolute top-5 right-1/2 hidden h-px w-full bg-line-strong sm:block" />}
              <span className={cx("relative z-10 grid size-10 place-items-center rounded-full border-2", RING[s.tone])}>
                <Icon className="size-[18px]" />
              </span>
              <span className="mt-2 font-display text-[13px] font-semibold text-ink">{s.label}</span>
              <span className="mt-0.5 line-clamp-2 px-1 text-[11px] leading-snug text-ink-3" title={`${s.tool} — ${s.note}`}>
                {s.note}
              </span>
            </li>
          );
        })}
      </ol>

      <dl className="mx-5 mt-5 grid grid-cols-1 divide-y divide-line rounded-xl border border-line bg-surface-2/60 text-sm sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <div className="px-4 py-3">
          <dt className="eyebrow">ตารางเวลา</dt>
          <dd className="mt-1 font-medium text-ink">{primary.scheduleLabel}</dd>
          <dd className="text-xs text-ink-3">{next ? `ถัดไป ${relative(next)}` : enabled === false ? "หยุดอยู่ · กดรันเองได้" : "—"}</dd>
        </div>
        <div className="px-4 py-3">
          <dt className="eyebrow">รันล่าสุด</dt>
          <dd className="mt-1 flex items-center gap-2 font-medium text-ink">
            <Tally tone={runTone(latest)} />
            {runLabel(latest)}
            {latest && <span className="font-mono text-xs font-normal text-ink-3">#{latest.run_number}</span>}
          </dd>
          <dd className="truncate text-xs text-ink-3">
            {latest ? `${relative(latest.created_at)} · ${duration(latest)}` : "—"}
            {extra.failedStep && <span className="text-bad"> · พังที่ “{extra.failedStep}”</span>}
          </dd>
        </div>
        <div className="px-4 py-3">
          <dt className="eyebrow">โหมด</dt>
          <dd className="mt-1 font-medium text-ink">{modeLabel}</dd>
          <dd className="text-xs text-ink-3">{flow.costNote.split(" (")[0]}</dd>
        </div>
      </dl>

      <div className="flex flex-wrap items-center gap-2 px-5 pt-4 pb-5">
        {ctx.github && wf ? (
          <>
            <RunButton
              file={primary.file}
              flowName={flow.short}
              allowTopic={primary.inputs?.topic}
              facts={[
                { label: "โหมดการโพสต์", value: modeLabel },
                { label: "แหล่งภาพ", value: visualVar },
                { label: "ค่าใช้จ่ายโดยประมาณ", value: flow.costNote.split(" (")[0] },
              ]}
              warning={
                mode === "auto" ? "โหมดโพสต์อัตโนมัติ — วิดีโอจะถูกโพสต์สาธารณะทันที" : undefined
              }
            />
            <ScheduleToggle file={primary.file} enabled={enabled} label={flow.short} />
          </>
        ) : (
          <a href="/settings#github" className="inline-flex items-center gap-2 rounded-xl border border-dashed border-line-strong px-3.5 py-2 text-sm text-ink-2 hover:bg-surface-2">
            เชื่อม GitHub เพื่อควบคุม flow นี้
          </a>
        )}
        <div className="ml-auto flex items-center gap-1">
          {extra.artifact && (
            <a
              href={`/api/artifacts/${extra.artifact.id}`}
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink"
              title="ไฟล์ .zip ที่มีวิดีโอ MP4 (เก็บ 7 วัน)"
            >
              <Download className="size-4" />
              วิดีโอล่าสุด <span className="text-ink-3">{bytes(extra.artifact.size_in_bytes)}</span>
            </a>
          )}
          {latest && (
            <a href={latest.html_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink">
              log <ArrowUpRight className="size-3.5" />
            </a>
          )}
        </div>
      </div>
    </Card>
  );
}

export function FlowPanelSkeleton({ flowId }: { flowId: FlowId }) {
  const flow = flowById(flowId)!;
  return (
    <Card as="article" className="relative overflow-hidden">
      <div className={cx("absolute inset-y-0 left-0 w-1", flow.id === "shopee" ? "bg-shopee" : "bg-story-mark")} />
      <div className="px-6 pt-5">
        <FlowTag flow={flow.id} />
        <h2 className="mt-2 font-display text-[22px] font-semibold text-ink">{flow.name}</h2>
        <p className="mt-1 text-sm text-ink-2">{flow.tagline}</p>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-4 px-6 sm:grid-cols-6">
        {flow.steps.map((s) => (
          <div key={s.key} className="flex flex-col items-center gap-2">
            <Skeleton className="size-10 rounded-full" />
            <span className="font-display text-[13px] font-semibold text-ink-3">{s.label}</span>
          </div>
        ))}
      </div>
      <Skeleton className="mx-5 mt-5 h-[76px]" />
      <div className="flex gap-2 px-5 pt-4 pb-5">
        <Skeleton className="h-9 w-28" />
        <Skeleton className="h-9 w-36" />
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
export async function AttentionList() {
  await requireSession();
  const ctx = await loadContext();
  const items = attention(ctx);
  if (ctx.errors.length) {
    return <div className="space-y-2">{ctx.errors.map((e) => <InlineError key={e} title="ดึงข้อมูลไม่สำเร็จ" detail={e} />)}</div>;
  }
  if (!items.length) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-ok/25 bg-ok-soft px-5 py-4 text-sm text-ok">
        <StateIcon tone="ok" />
        ทุกอย่างพร้อม — ไม่มีเรื่องที่ต้องจัดการ
      </div>
    );
  }
  return (
    <Card>
      <CardHeader eyebrow={`${items.length} เรื่อง`} title="ต้องจัดการ" />
      <ul className="mt-3 divide-y divide-line">
        {items.map((a) => (
          <li key={a.title} className="flex items-start gap-3 px-5 py-3">
            <StateIcon tone={a.tone} className="mt-0.5" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-ink">{a.title}</div>
              <div className="text-sm text-ink-2">{a.detail}</div>
            </div>
            {a.href && (
              <a
                href={a.href}
                {...(a.href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})}
                className="shrink-0 rounded-lg px-2.5 py-1 text-sm font-medium text-ink hover:bg-surface-2"
              >
                {a.cta ?? "ดู"} →
              </a>
            )}
          </li>
        ))}
      </ul>
      <div className="h-2" />
    </Card>
  );
}

// ---------------------------------------------------------------------------
const FILE_FLOW: Record<string, FlowId> = Object.fromEntries(
  FLOWS.flatMap((f) => f.workflows.map((w) => [w.file, f.id])),
);

export async function RecentRuns() {
  await requireSession();
  if (!gh.githubConfigured()) {
    return (
      <Card className="h-full">
        <CardHeader eyebrow="GitHub Actions" title="ประวัติการรัน" />
        <p className="px-5 pt-3 pb-5 text-sm text-ink-2">เชื่อม GitHub ที่หน้าตั้งค่าเพื่อดูประวัติการรัน</p>
      </Card>
    );
  }
  const res = await getRecentRuns();
  if (!res.ok) return <InlineError title="โหลดประวัติการรันไม่สำเร็จ" detail={res.error} />;
  const runs = res.value.filter((r) => FILE_FLOW[r.path.split("/").pop()!]);
  return (
    <Card className="h-full">
      <AutoRefresh active={runs.some((r) => r.status !== "completed")} />
      <CardHeader eyebrow="GitHub Actions" title="ประวัติการรัน" />
      {runs.length === 0 ? (
        <p className="px-5 pt-3 pb-5 text-sm text-ink-2">ยังไม่มีการรัน</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-y border-line text-left text-xs text-ink-3">
                <th className="py-2 pl-5 font-medium">สถานะ</th>
                <th className="py-2 font-medium">งาน</th>
                <th className="py-2 font-medium">เริ่มโดย</th>
                <th className="py-2 font-medium">เมื่อ</th>
                <th className="py-2 pr-5 text-right font-medium">ความยาว</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {runs.slice(0, 10).map((r) => {
                const file = r.path.split("/").pop()!;
                return (
                  <tr key={r.id} className="hover:bg-surface-2/60">
                    <td className="py-2.5 pl-5">
                      <span className="inline-flex items-center gap-2 whitespace-nowrap">
                        <Tally tone={runTone(r)} />
                        <span className={cx(runTone(r) === "live" && "font-display font-semibold text-live")}>{runLabel(r)}</span>
                      </span>
                    </td>
                    <td className="py-2.5">
                      <a href={r.html_url} target="_blank" rel="noreferrer" className="group inline-flex items-center gap-2">
                        <FlowTag flow={FILE_FLOW[file]} />
                        <span className="text-ink group-hover:underline">{r.name}</span>
                        <span className="font-mono text-xs text-ink-3">#{r.run_number}</span>
                      </a>
                    </td>
                    <td className="py-2.5 text-ink-2">{r.event === "schedule" ? "ตามเวลา" : r.event === "workflow_dispatch" ? "กดรันเอง" : r.event}</td>
                    <td className="py-2.5 whitespace-nowrap text-ink-2" title={thaiDateTime(r.created_at)}>{relative(r.created_at)}</td>
                    <td className="py-2.5 pr-5 text-right font-mono text-xs text-ink-2 tabular">{duration(r)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="h-3" />
    </Card>
  );
}

// ---------------------------------------------------------------------------
export async function HealthPanel() {
  await requireSession();
  const ctx = await loadContext();
  const e = ctx.eleven;
  const pct = e.ok ? Math.min(e.data!.used / e.data!.limit, 1) : 0;
  return (
    <Card className="h-full">
      <CardHeader eyebrow="สด" title="สถานะบริการ" />
      <div className="space-y-4 px-5 pt-4 pb-5">
        <div className="rounded-xl border border-line p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-ink">ElevenLabs · เสียงพากย์</span>
            {e.ok ? <Pill tone={pct > 0.9 ? "bad" : pct > 0.75 ? "warn" : "ok"}>{e.data!.tier}</Pill> : <Pill tone="idle">{e.configured ? "เช็คไม่ได้" : "ไม่ได้เชื่อม"}</Pill>}
          </div>
          {e.ok ? (
            <>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="font-display text-2xl font-semibold text-ink tabular">{number(e.data!.limit - e.data!.used)}</span>
                <span className="text-xs text-ink-3">/ {number(e.data!.limit)} ตัวอักษรคงเหลือ</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2" role="meter" aria-valuenow={Math.round(pct * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="ใช้โควตาไปแล้ว">
                <div className={cx("h-full rounded-full", pct > 0.9 ? "bg-bad" : pct > 0.75 ? "bg-warn" : "bg-ok")} style={{ width: `${Math.max(pct * 100, 1.5)}%` }} />
              </div>
              <div className="mt-2 flex justify-between text-xs text-ink-3">
                <span>≈ {number(Math.floor((e.data!.limit - e.data!.used) / 450))} คลิป</span>
                <span>รีเซ็ต {thaiDate(e.data!.resetAt)}</span>
              </div>
            </>
          ) : (
            <p className="mt-2 text-xs text-ink-3">เพิ่ม ELEVENLABS_API_KEY ใน Vercel เพื่อดูโควตา</p>
          )}
        </div>

        <ul className="divide-y divide-line rounded-xl border border-line text-sm">
          <HealthRow
            label="AI Gateway"
            tone={ctx.gateway.ok ? (ctx.gateway.data!.balance < 0.5 ? "warn" : "ok") : "idle"}
            value={ctx.gateway.ok ? `$${ctx.gateway.data!.balance.toFixed(2)} เครดิต` : ctx.gateway.configured ? "เช็คไม่ได้" : "ไม่ได้เชื่อม"}
          />
          <HealthRow
            label="Telegram"
            tone={ctx.telegram.ok ? "ok" : ctx.telegram.configured ? "bad" : "idle"}
            value={ctx.telegram.ok ? `@${ctx.telegram.data!.username}` : ctx.telegram.configured ? "token ใช้ไม่ได้" : "ไม่ได้เชื่อม"}
          />
          <HealthRow
            label="คลังข้อมูล"
            tone={ctx.readyProducts !== null ? "ok" : "idle"}
            value={ctx.readyProducts !== null ? `คิว ${ctx.readyProducts} · หัวข้อ ${ctx.readyStories ?? 0} · รอรีวิว ${ctx.pendingReviews ?? 0}` : "ไม่ได้เชื่อม"}
            href="/queue"
          />
          <HealthRow
            label="GitHub"
            tone={ctx.github ? (ctx.workflows ? "ok" : "bad") : "idle"}
            value={ctx.github ? (ctx.workflows ? `${ctx.workflows.size} workflows` : "token ใช้ไม่ได้") : "ไม่ได้เชื่อม"}
          />
        </ul>
      </div>
    </Card>
  );
}

function HealthRow({ label, tone, value, href }: { label: string; tone: Tone; value: string; href?: string }) {
  const body = (
    <>
      <span className="flex items-center gap-2.5 text-ink"><Tally tone={tone} />{label}</span>
      <span className="truncate text-right text-ink-2">{value}{href && <ArrowUpRight className="ml-1 inline size-3.5" />}</span>
    </>
  );
  return (
    <li>
      {href ? (
        <a href={href} {...(href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-surface-2/60">{body}</a>
      ) : (
        <div className="flex items-center justify-between gap-3 px-4 py-2.5">{body}</div>
      )}
    </li>
  );
}
