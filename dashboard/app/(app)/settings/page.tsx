import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import { ArrowUpRight, KeyRound, Link2, Plus } from "lucide-react";
import { RunButton, ScheduleToggle } from "@/components/controls";
import { Card, CardHeader, FlowTag, InlineError, PageHeader, Pill, Skeleton, StateIcon, Tally, btn, cx } from "@/components/ui";
import { ClaudeKeyForm, VoiceSample } from "@/components/ai-card";
import { ChannelEditor } from "@/components/channel-editor";
import { SettingsTabs } from "@/components/settings-tabs";
import { ConnectButtons, ConnectResult, MetaSecretForm, TiktokAppForm } from "@/components/social-card";
import { VarField } from "@/components/var-field";
import { channels } from "@/lib/channels";
import { requireSession } from "@/lib/dal";
import { effective, getSecrets, getVariables, getWorkflows, settle } from "@/lib/data";
import { FLOWS, SECRETS, THEME_SERIES, VARIABLES, type FlowId } from "@/lib/flows";
import { REPO, githubConfigured } from "@/lib/github";
import { hourText, hoursLabel, parseHours } from "@/lib/format";
import { META_APP_ID, connections, type Provider } from "@/lib/social";
import { storeConfigured } from "@/lib/store";

export const metadata: Metadata = { title: "ตั้งค่า" };

export default function SettingsPage() {
  const wait = (h: string) => <Skeleton className={cx(h, "rounded-2xl")} />;
  const tabs = [
    { id: "overview", label: "ภาพรวม", content: <Suspense fallback={wait("h-64")}><Connections /></Suspense> },
    {
      id: "channels", label: "เพจ & โซเชียล",
      content: (
        <>
          <Suspense><ConnectResult /></Suspense>
          <Suspense fallback={wait("h-72")}><Channels /></Suspense>
          <Suspense fallback={wait("h-64")}><Social /></Suspense>
        </>
      ),
    },
    ...FLOWS.map((f) => ({
      id: f.id === "shopee" ? "flow-a" : "flow-b", label: f.id === "shopee" ? "Flow A · Shopee" : "Flow B · คลิปเล่าเรื่อง",
      content: <Suspense fallback={wait("h-96")}><FlowSettings flowId={f.id} /></Suspense>,
    })),
    { id: "ai", label: "AI & เสียง", content: <Suspense fallback={wait("h-72")}><AiAndVoice /></Suspense> },
    {
      id: "system", label: "ตารางเวลา & กุญแจ",
      content: (
        <>
          <Suspense fallback={wait("h-64")}><Workflows /></Suspense>
          <Suspense fallback={wait("h-96")}><Secrets /></Suspense>
        </>
      ),
    },
  ];
  return (
    <div className="space-y-6">
      <PageHeader title="ตั้งค่า" subtitle="ค่าที่แก้ที่นี่มีผลตั้งแต่รันครั้งถัดไป" />
      <SettingsTabs tabs={tabs} />
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
    { label: "คลังข้อมูล (Vercel Blob)", env: "BLOB_READ_WRITE_TOKEN", ok: storeConfigured(), use: "คิวงาน · วิดีโอรีวิว" },
    { label: "Pipeline API", env: "PIPELINE_API_KEY", ok: (process.env.PIPELINE_API_KEY?.length ?? 0) >= 24, use: "ให้ GitHub Actions ส่งงานเข้าเว็บ" },
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
              href="https://github.com/settings/personal-access-tokens/new?name=Pipeline%20Control&description=Dashboard%20for%20shopee-pipeline&expires_in=366&actions=write&variables=write&secrets=write&contents=read"
              target="_blank"
              rel="noreferrer"
            >
              สร้าง Fine-grained token <ArrowUpRight className="inline size-3.5" />
            </a>
          </li>
          <li>Repository access → <b className="text-ink">Only select repositories</b> → เลือก <Code>{REPO.split("/")[1]}</Code></li>
          <li>Permissions: <Code>Actions: Read and write</Code> <Code>Variables: Read and write</Code> <Code>Secrets: Read and write</Code> <span className="text-ink-3">(สำหรับบันทึก Claude key)</span> <Code>Contents: Read-only</Code></li>
          <li>กด Generate แล้วคัดลอก token</li>
          <li>
            ใน Vercel → โปรเจกต์ <Code>pipeline-dashboard</Code> → Settings → Environment Variables → เพิ่ม <Code>GITHUB_TOKEN</Code> แล้ว Redeploy
          </li>
        </ol>
      </Card>
    </div>
  );
}

const VOICES = [
  { id: "jucSqawHKM1rUNf78oZQ", label: "Duang — ผู้ชาย เล่าเรื่องเสียงทุ้ม" },
  { id: "7XW5JhaNn90bnFojQ5DA", label: "Mali — ผู้หญิง ชัด เป็นธรรมชาติ" },
  { id: "yq05eeRaHPMGuWTVpqeP", label: "Tonce — ผู้ชาย เป็นกันเอง" },
];

async function AiAndVoice() {
  await requireSession();
  const gh = githubConfigured();
  const [secrets, vars] = gh ? await Promise.all([getSecrets(), getVariables()]) : [null, null];
  const hasKey = Boolean(secrets?.ok && secrets.value.has("ANTHROPIC_API_KEY"));
  const values = vars?.ok ? vars.value : null;
  const modelDef = VARIABLES.find((v) => v.name === "CLAUDE_MODEL")!;
  const budgetDef = VARIABLES.find((v) => v.name === "CLAUDE_MONTHLY_BUDGET")!;
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader
          eyebrow="สมองของทั้งสอง flow"
          title="Claude"
          action={hasKey ? <Pill tone="ok">ใช้ Claude อยู่</Pill> : <Pill tone="warn">ยังไม่ใส่ key · ใช้ AI สำรอง</Pill>}
        />
        <div className="space-y-4 px-5 pt-3 pb-1">
          <p className="text-sm text-ink-2">
            เมื่อใส่ key แล้ว Claude จะเขียนบท วางช็อตแผนที่ (ซูมไปไหน วาดเส้นอะไร ปักหมุดตรงไหน) และคิดหัวข้อใหม่
            โดยอ้างอิงข้อมูลจาก Wikipedia ทุกครั้ง
          </p>
          <ClaudeKeyForm hasKey={hasKey} disabled={!gh} />
        </div>
        <div className="divide-y divide-line">
          <VarField key={`CLAUDE_MODEL:${effective(values, "CLAUDE_MODEL")}`} def={modelDef}
            current={effective(values, "CLAUDE_MODEL")} isSet={Boolean(values?.CLAUDE_MODEL)} disabled={!gh} />
          <VarField key={`CLAUDE_MONTHLY_BUDGET:${effective(values, "CLAUDE_MONTHLY_BUDGET")}`} def={budgetDef}
            current={effective(values, "CLAUDE_MONTHLY_BUDGET")} isSet={Boolean(values?.CLAUDE_MONTHLY_BUDGET)} disabled={!gh} />
        </div>
      </Card>
      <Card>
        <CardHeader eyebrow="ElevenLabs · eleven_v4" title="เสียงพากย์ภาษาไทย" />
        <div className="space-y-3 px-5 pt-3 pb-5">
          <p className="text-sm text-ink-2">
            เปลี่ยนจากโมเดลเดิมที่ไม่รองรับภาษาไทย (ถอดเสียงกลับได้ถูกแค่ 65%) มาเป็น eleven_v4 กับเสียงคนไทยจริง (ถอดเสียงกลับได้ 100%)
            เลือกเสียงของแต่ละ flow ได้ในการ์ดด้านล่าง
          </p>
          {VOICES.map((v) => <VoiceSample key={v.id} id={v.id} label={v.label} />)}
        </div>
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
      {flowId === "story" && (
        <p className="mx-5 mt-3 rounded-xl bg-surface-2 px-3.5 py-2.5 text-xs text-ink-2">
          ค่าในหน้านี้เป็นค่ากลาง · แต่ละเพจตั้งธีม ชื่อซีรีส์ และโหมดโพสต์ของตัวเองได้ในแท็บ <a href="#channels" className="font-medium text-ink underline">เพจ &amp; โซเชียล</a>
        </p>
      )}
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
  const [res, vars] = await Promise.all([getWorkflows(), getVariables()]);
  if (!res.ok) return <InlineError title="โหลด workflow ไม่สำเร็จ" detail={res.error} />;
  const values = vars.ok ? vars.value : null;
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
                <div className="font-mono text-[11px] text-ink-3">{w.file} · {w.hoursVar ? hoursLabel(parseHours(effective(values, w.hoursVar))) : w.scheduleLabel} · {!wf ? "ยังไม่อยู่ใน repo" : on ? "เปิด" : wf.state === "disabled_inactivity" ? "ปิด (ไม่มีความเคลื่อนไหว 60 วัน)" : "ปิด"}</div>
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

const NEED_LABEL = { required: "จำเป็น", auto: "โหมดโพสต์อัตโนมัติ", recommended: "แนะนำ" } as const;

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

const SOCIAL: { id: Provider; name: string; flows: FlowId[]; note: string }[] = [
  { id: "instagram", name: "Instagram", flows: ["shopee", "story"], note: "บัญชี Professional · ระบบต่ออายุ token 60 วันให้เองทุกวัน" },
  { id: "tiktok", name: "TikTok", flows: ["shopee", "story"], note: "แอปที่ยังไม่ผ่าน audit ของ TikTok โพสต์ได้แบบส่วนตัว (เห็นคนเดียว) เท่านั้น" },
];

async function Social() {
  await requireSession();
  const store = storeConfigured();
  const data = store ? await settle(connections()) : null;
  const vars = githubConfigured() ? await getVariables() : null;
  const values = vars?.ok ? vars.value : null;
  const view = data?.ok ? data.value : null;
  const modes = FLOWS.map((f) => ({ flow: f, auto: effective(values, f.publishVar) === "auto" }));
  return (
    <Card>
      <CardHeader
        eyebrow="กดเชื่อมครั้งเดียว ระบบเก็บ token ลง GitHub Secrets ให้เอง"
        title="Instagram & TikTok"
        action={
          <span className="flex flex-wrap gap-1.5">
            {modes.map(({ flow, auto }) => (
              <Pill key={flow.id} tone={auto ? "ok" : "idle"}>{flow.short}: {auto ? "โพสต์อัตโนมัติ" : "ตรวจก่อน"}</Pill>
            ))}
          </span>
        }
      />
      {data && !data.ok && <div className="px-5 pt-3"><InlineError title="อ่านสถานะบัญชีไม่สำเร็จ" detail={data.error} /></div>}
      <ul className="mt-3 divide-y divide-line">
        {SOCIAL.map((s) => {
          const acc = data?.ok ? data.value.accounts[s.id] : null;
          const ready = Boolean(view && (s.id === "tiktok" ? view.tiktokApp : s.id === "instagram" ? view.igApp : view.metaApp));
          return (
            <li key={s.id} className="space-y-2.5 px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-ink">{s.name}</span>
                    {s.flows.map((f) => <FlowTag key={f} flow={f} />)}
                    {acc ? <Pill tone="ok">เชื่อมแล้ว · {acc.name}</Pill> : <Pill tone="idle">ยังไม่เชื่อม</Pill>}
                  </div>
                  <p className="text-xs text-ink-3">
                    {s.note}
                    {acc?.expiresAt && <> · token ใช้ได้ถึง {new Date(acc.expiresAt).toLocaleDateString("th-TH", { dateStyle: "medium" })}</>}
                  </p>
                </div>
                <ConnectButtons provider={s.id} connected={Boolean(acc)} ready={Boolean(ready)} />
              </div>
              {s.id === "tiktok" && !acc && <TiktokAppForm saved={Boolean(view?.tiktokApp)} />}
            </li>
          );
        })}
      </ul>
      <p className="px-5 pt-1 pb-5 text-xs leading-relaxed text-ink-3">
        เปิดโพสต์อัตโนมัติได้ที่ &ldquo;โหมดการโพสต์&rdquo; ในแท็บ Flow A / Flow B · ตอนโหมด auto ระบบโพสต์ไปทุกบัญชีที่เชื่อมไว้ และยังส่ง Telegram + หน้ารีวิวเหมือนเดิม
        {" "}· Shopee Video ไม่มี API ต้องอัปโหลดเองเสมอ
      </p>
    </Card>
  );
}

async function Channels() {
  await requireSession();
  if (!storeConfigured()) return <InlineError title="ยังไม่ได้เชื่อมคลังข้อมูล" detail="ต้องมี BLOB_READ_WRITE_TOKEN ก่อน" />;
  const [data, conn, vars] = await Promise.all([
    settle(channels()), settle(connections()), githubConfigured() ? getVariables() : Promise.resolve(null),
  ]);
  const varValues = vars?.ok ? vars.value : null;
  // An empty channel field falls back to the GitHub variable, then to the theme's default.
  const seriesFor = (theme: string) => varValues?.STORY_SERIES_NAME?.value || THEME_SERIES[theme] || "ค่าของธีม";
  const nicheDefault = (varValues?.STORY_NICHE?.value || "แนวของธีม").slice(0, 60);
  const defaultHours = parseHours(effective(vars?.ok ? vars.value : null, "STORY_POST_HOURS")).map(hourText).join(", ") || "พักอยู่";
  if (!data.ok) return <InlineError title="อ่านรายชื่อเพจไม่สำเร็จ" detail={data.error} />;
  const list = data.value.channels;
  const appReady = conn.ok && conn.value.metaApp;
  const themes = VARIABLES.find((v) => v.name === "STORY_THEME")!.options!;
  return (
    <Card>
      <div id="facebook" className="scroll-mt-24" />
      <CardHeader
        eyebrow={<span className="inline-flex items-center gap-2"><FlowTag flow="story" /> โพสต์ Reels · token เพจไม่หมดอายุ</span>}
        title={list.length ? `เพจ Facebook · ${list.length} เพจ` : "เพจ Facebook"}
        action={
          <a
            href={appReady ? "/api/connect/facebook" : undefined}
            aria-disabled={!appReady}
            className={cx(btn.base, list.length ? btn.secondary : btn.primary, !appReady && "pointer-events-none opacity-50")}
          >
            {list.length ? <><Plus className="size-4" /> เพิ่มเพจ / ต่ออายุ</> : <><Link2 className="size-4" /> เชื่อมเพจ Facebook</>}
          </a>
        }
      />
      {!list.length && (
        <ol className="list-decimal space-y-1.5 px-5 pt-3 pl-10 text-sm text-ink-2 marker:text-ink-3">
          <li className={cx(appReady && "text-ink-3 line-through")}>ใส่ App secret ด้านล่าง (ครั้งเดียว)</li>
          <li>กด <b className="text-ink">เชื่อมเพจ Facebook</b> → ล็อกอิน Facebook → ติ๊กเพจที่ต้องการ → อนุญาต</li>
          <li>กลับมาที่นี่ ตั้งว่าแต่ละเพจเล่าเรื่องอะไร — เพิ่มเพจใหม่ได้ตลอด แต่ละเพจมีธีมของตัวเอง</li>
        </ol>
      )}
      {!appReady && <div className="px-5 pt-3"><MetaSecretForm appId={META_APP_ID} saved={false} /></div>}
      {list.length > 0 && (
        <div className="mt-3 divide-y divide-line border-t border-line">
          {list.map((c) => (
            <ChannelEditor key={`${c.id}:${c.updatedAt}`} channel={c} themes={themes} primary={c.id === data.value.primaryId}
              seriesDefault={seriesFor(c.theme)} nicheDefault={nicheDefault} defaultHours={defaultHours} />
          ))}
        </div>
      )}
      <p className="border-t border-line px-5 py-3 text-xs leading-relaxed text-ink-3">
        เพจหลัก (เพจแรกที่เปิดใช้) รับหัวข้อที่ไม่ได้ระบุเพจ · หัวข้อในคิวเลือกเพจได้ตอนเพิ่ม · token ทุกเพจเข้ารหัสเก็บในคลังข้อมูลส่วนตัว
      </p>
    </Card>
  );
}
