import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import { ArrowUpRight, KeyRound } from "lucide-react";
import { RunButton, ScheduleToggle } from "@/components/controls";
import { Card, CardHeader, FlowTag, InlineError, PageHeader, Pill, Skeleton, StateIcon, Tally, cx } from "@/components/ui";
import { VarField } from "@/components/var-field";
import { requireSession } from "@/lib/dal";
import { effective, getSecrets, getVariables, getWorkflows } from "@/lib/data";
import { FLOWS, SECRETS, VARIABLES, type FlowId } from "@/lib/flows";
import { REPO, githubConfigured } from "@/lib/github";
import { sheetsConfigured } from "@/lib/sheets";

export const metadata: Metadata = { title: "ตั้งค่า" };

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="ตั้งค่า" subtitle="ค่าที่แก้ที่นี่จะถูกเก็บเป็น GitHub Actions Variables และมีผลตั้งแต่รันครั้งถัดไป" />
      <Suspense fallback={<Skeleton className="h-40 rounded-2xl" />}>
        <Connections />
      </Suspense>
      <div className="grid gap-5 xl:grid-cols-2">
        {FLOWS.map((f) => (
          <Suspense key={f.id} fallback={<Skeleton className="h-96 rounded-2xl" />}>
            <FlowSettings flowId={f.id} />
          </Suspense>
        ))}
      </div>
      <Suspense fallback={<Skeleton className="h-64 rounded-2xl" />}>
        <Workflows />
      </Suspense>
      <Suspense fallback={<Skeleton className="h-96 rounded-2xl" />}>
        <Secrets />
      </Suspense>
      <Social />
    </div>
  );
}

function Code({ children }: { children: ReactNode }) {
  return <code className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[12px] text-ink">{children}</code>;
}

async function Connections() {
  await requireSession();
  const rows = [
    { label: "GitHub", env: "GITHUB_TOKEN", ok: githubConfigured(), use: "สั่งรัน · ตั้งค่า · ประวัติ" },
    { label: "Google Sheet", env: "GOOGLE_SHEET_ID + GOOGLE_SERVICE_ACCOUNT_JSON", ok: sheetsConfigured(), use: "คิวสินค้าและหัวข้อ" },
    { label: "ElevenLabs", env: "ELEVENLABS_API_KEY", ok: Boolean(process.env.ELEVENLABS_API_KEY), use: "โควตาเสียง" },
    { label: "AI Gateway", env: "AI_GATEWAY_API_KEY", ok: Boolean(process.env.AI_GATEWAY_API_KEY), use: "เครดิต AI" },
    { label: "Telegram", env: "TELEGRAM_BOT_TOKEN", ok: Boolean(process.env.TELEGRAM_BOT_TOKEN), use: "สถานะบอท" },
  ];
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <Card>
        <CardHeader eyebrow="Vercel Environment" title="การเชื่อมต่อของ dashboard" />
        <ul className="mt-3 divide-y divide-line">
          {rows.map((r) => (
            <li key={r.label} className="flex items-center gap-3 px-5 py-2.5">
              <StateIcon tone={r.ok ? "ok" : "idle"} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink">{r.label}</div>
                <div className="truncate font-mono text-[11px] text-ink-3">{r.env}</div>
              </div>
              <span className="text-right text-xs text-ink-3">{r.use}</span>
            </li>
          ))}
        </ul>
        <div className="h-3" />
      </Card>
      <Card className={cx(!githubConfigured() && "ring-2 ring-shopee/40")}>
        <div id="github" className="scroll-mt-24" />
        <CardHeader
          eyebrow={githubConfigured() ? "เชื่อมแล้ว" : "ขั้นตอนเดียวที่ต้องทำเอง"}
          title="เชื่อม GitHub ให้ dashboard สั่งงานได้"
          action={githubConfigured() ? <Pill tone="ok">พร้อม</Pill> : <Pill tone="warn">ยังไม่เชื่อม</Pill>}
        />
        <ol className="list-decimal space-y-2 px-5 pt-3 pb-5 pl-10 text-sm text-ink-2 marker:text-ink-3">
          <li>
            เปิดหน้า{" "}
            <a
              className="font-medium text-ink underline decoration-line-strong underline-offset-2 hover:decoration-ink"
              href="https://github.com/settings/personal-access-tokens/new?name=Pipeline%20Control&description=Dashboard%20for%20shopee-pipeline&expires_in=366&actions=write&variables=write&secrets=read&contents=read"
              target="_blank"
              rel="noreferrer"
            >
              สร้าง Fine-grained token <ArrowUpRight className="inline size-3.5" />
            </a>
          </li>
          <li>Repository access → <b className="text-ink">Only select repositories</b> → เลือก <Code>{REPO.split("/")[1]}</Code></li>
          <li>Permissions: <Code>Actions: Read and write</Code> <Code>Variables: Read and write</Code> <Code>Secrets: Read-only</Code> <Code>Contents: Read-only</Code></li>
          <li>กด Generate แล้วคัดลอก token</li>
          <li>
            ใน Vercel → โปรเจกต์ <Code>pipeline-dashboard</Code> → Settings → Environment Variables → เพิ่ม <Code>GITHUB_TOKEN</Code> แล้ว Redeploy
          </li>
        </ol>
      </Card>
    </div>
  );
}

async function FlowSettings({ flowId }: { flowId: FlowId }) {
  await requireSession();
  const flow = FLOWS.find((f) => f.id === flowId)!;
  const defs = VARIABLES.filter((v) => v.scope === flowId);
  const gh = githubConfigured();
  const vars = gh ? await getVariables() : null;
  if (vars && !vars.ok) return <InlineError title="โหลดค่าตั้งค่าไม่สำเร็จ" detail={vars.error} />;
  const values = vars?.ok ? vars.value : null;
  return (
    <Card>
      <CardHeader eyebrow={<FlowTag flow={flowId} />} title={flow.name} />
      {!gh && <p className="mx-5 mt-3 rounded-xl bg-surface-2 px-3.5 py-2.5 text-xs text-ink-2">แสดงค่าเริ่มต้น — เชื่อม GitHub เพื่อแก้ไข</p>}
      <div className="mt-2 divide-y divide-line">
        {defs.map((d) => (
          <VarField key={`${d.name}:${effective(values, d.name)}`} def={d} current={effective(values, d.name)} isSet={Boolean(values?.[d.name])} disabled={!gh} />
        ))}
      </div>
    </Card>
  );
}

async function Workflows() {
  await requireSession();
  if (!githubConfigured()) return null;
  const res = await getWorkflows();
  if (!res.ok) return <InlineError title="โหลด workflow ไม่สำเร็จ" detail={res.error} />;
  return (
    <Card>
      <CardHeader eyebrow="GitHub Actions" title="ตารางเวลา" />
      <ul className="mt-3 divide-y divide-line">
        {FLOWS.flatMap((f) => f.workflows.map((w) => ({ f, w }))).map(({ f, w }) => {
          const wf = res.value.get(w.file);
          const on = wf?.state === "active";
          return (
            <li key={w.file} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <Tally tone={!wf ? "warn" : on ? "ok" : "idle"} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                  <FlowTag flow={f.id} /> {w.role}
                </div>
                <div className="font-mono text-[11px] text-ink-3">{w.file} · {w.scheduleLabel} · {!wf ? "ยังไม่อยู่ใน repo" : on ? "เปิด" : wf.state === "disabled_inactivity" ? "ปิด (ไม่มีความเคลื่อนไหว 60 วัน)" : "ปิด"}</div>
              </div>
              {wf && (
                <div className="flex gap-2">
                  <RunButton compact file={w.file} flowName={w.role} allowTopic={w.inputs?.topic} facts={[{ label: "workflow", value: w.file }]} />
                  <ScheduleToggle file={w.file} enabled={on} label={w.role} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <div className="h-2" />
    </Card>
  );
}

const NEED_LABEL = { required: "จำเป็น", auto: "โหมดโพสต์อัตโนมัติ", fal: "โหมด fal" } as const;

async function Secrets() {
  await requireSession();
  if (!githubConfigured()) return null;
  const [res, vars] = await Promise.all([getSecrets(), getVariables()]);
  if (!res.ok) return <InlineError title="โหลดรายชื่อ secrets ไม่สำเร็จ" detail={res.error} />;
  const values = vars.ok ? vars.value : null;
  const autoOn = (f: FlowId) => effective(values, f === "shopee" ? "PUBLISH_MODE" : "STORY_PUBLISH_MODE") === "auto";
  return (
    <Card>
      <CardHeader
        eyebrow="GitHub Secrets · ดูได้แค่ชื่อ ไม่เห็นค่า"
        title="กุญแจที่ pipeline ใช้"
        action={
          <a href={`https://github.com/${REPO}/settings/secrets/actions`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
            <KeyRound className="size-4" /> จัดการใน GitHub <ArrowUpRight className="size-3.5" />
          </a>
        }
      />
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-y border-line text-left text-xs text-ink-3">
              <th className="py-2 pl-5 font-medium">ชื่อ</th>
              <th className="py-2 font-medium">ใช้ทำ</th>
              <th className="py-2 font-medium">ใช้เมื่อ</th>
              <th className="py-2 pr-5 text-right font-medium">สถานะ</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {SECRETS.map((s) => {
              const present = res.value.has(s.name);
              const needed = s.need === "required" || (s.need === "auto" && s.flows.some(autoOn));
              return (
                <tr key={s.name}>
                  <td className="py-2.5 pl-5 font-mono text-xs text-ink">{s.name}</td>
                  <td className="py-2.5 text-ink-2">{s.purpose}</td>
                  <td className="py-2.5 text-ink-2">
                    <span className="inline-flex flex-wrap items-center gap-1.5">
                      {NEED_LABEL[s.need]}
                      {s.flows.map((f) => <FlowTag key={f} flow={f} />)}
                    </span>
                  </td>
                  <td className="py-2.5 pr-5 text-right">
                    {present ? <Pill tone="ok">มีแล้ว</Pill> : <Pill tone={needed ? "bad" : "idle"}>{needed ? "ขาด" : "ยังไม่ตั้ง"}</Pill>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="h-3" />
    </Card>
  );
}

function Social() {
  const items = [
    {
      name: "เพจ Facebook (Flow B)", cmd: "python -m pipeline.facebook auth",
      steps: "ใน Meta app เพิ่ม Facebook Login for Business และใส่ redirect https://warongkorn6560.github.io/shopee-pipeline/ จากนั้นรันคำสั่ง เลือกเพจ ระบบจะบันทึก FACEBOOK_PAGE_ID/TOKEN ลง GitHub ให้เอง (token เพจไม่หมดอายุ)",
    },
    {
      name: "Instagram", cmd: "python -m pipeline.instagram auth",
      steps: "token หมดอายุทุก 60 วัน (ตัวปัจจุบันหมดไปแล้วเมื่อ 19 ส.ค. 2026) รันคำสั่งเพื่อขอใหม่ แล้วตั้ง INSTAGRAM_ACCESS_TOKEN",
    },
    {
      name: "TikTok", cmd: "python -m pipeline.tiktok auth",
      steps: "ได้ TIKTOK_REFRESH_TOKEN สำหรับอัปโหลด · การโพสต์แบบสาธารณะต้องผ่าน app audit ของ TikTok (2–6 สัปดาห์)",
    },
  ];
  return (
    <Card>
      <div id="social" className="scroll-mt-24" />
      <CardHeader eyebrow="จำเป็นเฉพาะโหมดโพสต์อัตโนมัติ" title="เชื่อมบัญชีโซเชียล" />
      <ul className="mt-3 divide-y divide-line">
        {items.map((i) => (
          <li key={i.name} className="space-y-1.5 px-5 py-3.5">
            <div className="text-sm font-medium text-ink">{i.name}</div>
            <p className="text-sm text-ink-2">{i.steps}</p>
            <Code>{i.cmd}</Code>
          </li>
        ))}
      </ul>
      <p className="px-5 pt-1 pb-5 text-xs text-ink-3">รันคำสั่งในโฟลเดอร์ shopee-pipeline บนเครื่องของคุณ · Shopee Video ไม่มี API ต้องอัปโหลดเองเสมอ (~30 วินาที)</p>
    </Card>
  );
}
