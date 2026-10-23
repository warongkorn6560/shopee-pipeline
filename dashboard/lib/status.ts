import "server-only";
import type { Tone } from "@/components/ui";
import { FLOWS, type FlowDef, type FlowStep } from "./flows";
import type { ElevenQuota, Probe } from "./health";
import type { Run, Workflow } from "./github";
import { number } from "./format";

export interface StatusContext {
  github: boolean;
  workflows: Map<string, Workflow> | null;
  vars: Record<string, { value: string }> | null;
  secrets: Set<string> | null;
  eleven: Probe<ElevenQuota>;
  gateway: Probe<{ balance: number; used: number }>;
  telegram: Probe<{ username: string }>;
  readyProducts: number | null;
  readyStories: number | null;
  pendingReviews: number | null;
  latest: Record<string, Run | undefined>; // primary workflow file → latest run
}

export interface StepStatus extends FlowStep {
  tone: Tone;
  note: string;
}

const value = (ctx: StatusContext, name: string, fallback: string) => ctx.vars?.[name]?.value || fallback;
const has = (ctx: StatusContext, name: string) => ctx.secrets?.has(name) ?? null;

export function stepStatuses(flow: FlowDef, ctx: StatusContext): StepStatus[] {
  return flow.steps.map((step) => ({ ...step, ...stepTone(flow, step, ctx) }));
}

function stepTone(flow: FlowDef, step: FlowStep, ctx: StatusContext): { tone: Tone; note: string } {
  switch (step.key) {
    case "input": {
      const ready = flow.id === "shopee" ? ctx.readyProducts : ctx.readyStories;
      if (ready === null) return { tone: "idle", note: "ยังไม่ได้เชื่อมคลังข้อมูล" };
      if (ready > 0) return { tone: "ok", note: `พร้อม ${ready} รายการ` };
      if (flow.id === "story" && value(ctx, "STORY_AUTO_TOPIC", "on") === "on") {
        return { tone: "ok", note: "คิวว่าง · AI คิดหัวข้อให้" };
      }
      return { tone: "warn", note: "คิวว่าง — เพิ่มที่หน้าคิวงาน" };
    }
    case "script": {
      if (ctx.gateway.ok) return { tone: "ok", note: `เครดิตเหลือ $${ctx.gateway.data!.balance.toFixed(2)}` };
      if (ctx.gateway.configured) return { tone: "warn", note: "เช็คเครดิตไม่ได้" };
      const s = has(ctx, "AI_GATEWAY_API_KEY");
      return s === false ? { tone: "bad", note: "ไม่มี AI_GATEWAY_API_KEY" } : { tone: "ok", note: "ตั้ง key แล้ว" };
    }
    case "visual": {
      if (flow.id === "shopee") {
        return { tone: "ok", note: "รูปสินค้าจริง · ฟรี" };
      }
      const p = value(ctx, "STORY_IMAGE_PROVIDER", "auto");
      if (p === "gateway") return { tone: "warn", note: "ภาพ AI ต้องเติมเครดิต" };
      return { tone: "ok", note: p === "cards" ? "การ์ดกราฟิก" : "Wikimedia · ฟรี" };
    }
    case "voice": {
      const e = ctx.eleven;
      if (e.ok) {
        const pct = e.data!.used / e.data!.limit;
        const left = e.data!.limit - e.data!.used;
        return { tone: pct > 0.9 ? "bad" : pct > 0.75 ? "warn" : "ok", note: `เหลือ ${number(left)} ตัวอักษร` };
      }
      if (e.configured) return { tone: "warn", note: "เช็คโควตาไม่ได้" };
      return has(ctx, "ELEVENLABS_API_KEY") === false
        ? { tone: "bad", note: "ไม่มี ELEVENLABS_API_KEY" }
        : { tone: "ok", note: "ตั้ง key แล้ว" };
    }
    case "render":
      return { tone: "ok", note: "รันบน GitHub runner" };
    case "deliver": {
      const auto = value(ctx, flow.publishVar, "review") === "auto";
      if (auto) {
        const need = flow.id === "story" ? ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN"] : ["TIKTOK_REFRESH_TOKEN"];
        const missing = need.filter((n) => has(ctx, n) === false);
        if (missing.length) return { tone: "warn", note: `auto แต่ยังไม่เชื่อม ${flow.id === "story" ? "Facebook" : "TikTok"}` };
        return { tone: "ok", note: "โพสต์อัตโนมัติ" };
      }
      return { tone: "ok", note: "ตรวจในเว็บ + Telegram" };
    }
  }
}

export interface Attention {
  tone: Tone;
  title: string;
  detail: string;
  href?: string;
  cta?: string;
}

export function attention(ctx: StatusContext): Attention[] {
  const out: Attention[] = [];
  if (!ctx.github) {
    out.push({
      tone: "bad", title: "ยังไม่ได้เชื่อม GitHub",
      detail: "ต้องมี GITHUB_TOKEN เพื่อสั่งรัน เปิด/ปิดตารางเวลา และแก้ค่าตั้งค่า",
      href: "/settings#github", cta: "วิธีเชื่อม",
    });
  }
  for (const flow of FLOWS) {
    const primary = flow.workflows.find((w) => w.primary)!;
    const wf = ctx.workflows?.get(primary.file);
    if (ctx.workflows && !wf) {
      out.push({ tone: "warn", title: `${flow.short}: ยังไม่พบ workflow ใน repo`, detail: `${primary.file} ยังไม่ถูก push ขึ้น GitHub` });
    } else if (wf && wf.state !== "active") {
      out.push({
        tone: "warn", title: `${flow.short} ${flow.name}: หยุดรันตามเวลาอยู่`,
        detail: `กด “เปิดรันตามเวลา” ที่การ์ด ${flow.short} เมื่อพร้อมให้รันเองทุกวัน`,
      });
    }
    const run = ctx.latest[primary.file];
    if (run?.conclusion === "failure") {
      out.push({
        tone: "bad", title: `${flow.short}: รันล่าสุดล้มเหลว`,
        detail: `#${run.run_number} — เปิดดู log เพื่อหาสาเหตุ`, href: run.html_url, cta: "ดู log",
      });
    }
    if ((ctx.vars?.[flow.publishVar]?.value) === "auto") {
      const need = flow.id === "story" ? "FACEBOOK_PAGE_TOKEN" : "TIKTOK_REFRESH_TOKEN";
      if (ctx.secrets && !ctx.secrets.has(need)) {
        out.push({
          tone: "warn", title: `${flow.short} ตั้งเป็นโพสต์อัตโนมัติ แต่ยังไม่เชื่อมบัญชี`,
          detail: "วิดีโอยังถูกส่งเข้า Telegram ตามปกติ แต่จะไม่ถูกโพสต์", href: "/settings#social", cta: "เชื่อมบัญชี",
        });
      }
    }
  }
  if (ctx.pendingReviews) {
    out.push({
      tone: "warn", title: `มีวิดีโอรอตรวจ ${ctx.pendingReviews} คลิป`,
      detail: "ดู กดผ่าน/ไม่ผ่าน และคัดลอกแคปชันไปโพสต์ได้ที่หน้ารีวิว", href: "/review", cta: "ไปรีวิว",
    });
  }
  if (ctx.readyProducts === 0) {
    out.push({
      tone: "warn", title: "Flow A: ไม่มีสินค้าสถานะ Ready",
      detail: "รันวันนี้จะข้ามไป ส่งสินค้าเข้าคิวหรือเพิ่มสินค้าใหม่ได้ที่หน้าคิวงาน", href: "/queue", cta: "ไปที่คิว",
    });
  }
  if (ctx.eleven.ok && ctx.eleven.data!.used / ctx.eleven.data!.limit > 0.75) {
    out.push({ tone: "warn", title: "โควตาเสียง ElevenLabs ใกล้หมด", detail: "เกิน 75% ของเดือนนี้แล้ว" });
  }
  return out;
}

export function runTone(run?: Run): Tone {
  if (!run) return "idle";
  if (run.status !== "completed") return "live";
  if (run.conclusion === "success") return "ok";
  if (run.conclusion === "failure" || run.conclusion === "timed_out") return "bad";
  return "idle";
}

export function runLabel(run?: Run): string {
  if (!run) return "ยังไม่เคยรัน";
  if (run.status === "queued" || run.status === "pending" || run.status === "waiting") return "รอคิว";
  if (run.status !== "completed") return "ON AIR";
  return {
    success: "สำเร็จ", failure: "ล้มเหลว", cancelled: "ยกเลิก", skipped: "ข้าม",
    timed_out: "หมดเวลา", neutral: "จบ",
  }[run.conclusion ?? "neutral"] ?? "จบ";
}
