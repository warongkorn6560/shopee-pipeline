"use server";

import { cookies } from "next/headers";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/dal";
import { VARIABLES, WORKFLOW_FILES } from "@/lib/flows";
import * as gh from "@/lib/github";
import { fillImages, parseAffiliateCsv, productImage } from "@/lib/shopee";
import * as channels from "@/lib/channels";
import * as posting from "@/lib/post-video";
import * as social from "@/lib/social";
import * as store from "@/lib/store";
import { SESSION_COOKIE } from "@/lib/session";

export interface ActionResult {
  ok: boolean;
  message: string;
}

function fail(e: unknown, prefix: string): ActionResult {
  const msg = e instanceof Error ? e.message : String(e);
  if (e instanceof gh.GitHubError && (e.status === 401 || e.status === 403)) {
    return { ok: false, message: `${prefix}: GitHub token ไม่มีสิทธิ์พอ (${e.status}) — ตรวจสิทธิ์ Actions/Variables` };
  }
  return { ok: false, message: `${prefix}: ${msg}` };
}

export async function runWorkflow(file: string, topic?: string): Promise<ActionResult> {
  await requireSession();
  if (!WORKFLOW_FILES.includes(file)) return { ok: false, message: "ไม่รู้จัก workflow นี้" };
  const cleanTopic = topic?.trim().slice(0, 140);
  try {
    await gh.dispatch(file, file === "story-video.yml" && cleanTopic ? { topic: cleanTopic } : undefined);
  } catch (e) {
    return fail(e, "สั่งรันไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "ส่งคำสั่งรันแล้ว — GitHub จะเริ่มภายในไม่กี่วินาที" };
}

/** Pull fresh view counts now (stats.yml, ~1 min). */
export async function refreshStats(): Promise<ActionResult> {
  await requireSession();
  try {
    const running = (await gh.listRunsFor("stats.yml", 3)).some((r) => r.status !== "completed");
    if (running) return { ok: true, message: "กำลังดึงยอดวิวอยู่แล้ว — รอสักครู่" };
    await gh.dispatch("stats.yml");
  } catch (e) {
    return fail(e, "สั่งดึงยอดวิวไม่สำเร็จ");
  }
  return { ok: true, message: "กำลังดึงยอดวิวล่าสุด — ประมาณ 1 นาที หน้านี้จะอัปเดตเอง" };
}

/** Burst: make `count` story videos back to back (story-video.yml runs them one at a time). */
export async function runStoryBurst(count: number, preview: boolean, style = ""): Promise<ActionResult> {
  await requireSession();
  const n = Math.round(Number(count));
  if (!Number.isFinite(n) || n < 1 || n > 60) return { ok: false, message: "จำนวนคลิปต้องอยู่ระหว่าง 1–60" };
  try {
    const pick = ["classic", "reaction"].includes(style) ? style : "";
    await gh.dispatch("story-video.yml", { count: String(n), preview: String(preview), ...(pick ? { style: pick } : {}) });
  } catch (e) {
    return fail(e, "สั่งรัวคลิปไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: `สั่งรัว ${n} คลิปแล้ว${preview ? " (ตัวอย่าง · เข้าหน้ารีวิว ไม่โพสต์)" : ""} — ใช้เวลาราว ${Math.ceil((n * 17) / 60)} ชม.` };
}

export async function setWorkflowEnabled(file: string, enabled: boolean): Promise<ActionResult> {
  await requireSession();
  if (!WORKFLOW_FILES.includes(file)) return { ok: false, message: "ไม่รู้จัก workflow นี้" };
  try {
    await gh.setWorkflowEnabled(file, enabled);
  } catch (e) {
    return fail(e, enabled ? "เปิดไม่สำเร็จ" : "ปิดไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: enabled ? "เปิดการรันตามเวลาแล้ว" : "หยุดการรันตามเวลาแล้ว" };
}

export async function saveVariable(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const name = String(form.get("name") ?? "");
  const value = String(form.get("value") ?? "").trim();
  const def = VARIABLES.find((v) => v.name === name);
  if (!def) return { ok: false, message: "ไม่รู้จักค่านี้" };
  if (def.options && def.kind !== "select" && !def.options.some((o) => o.value === value)) {
    return { ok: false, message: "ค่าที่เลือกไม่ถูกต้อง" };
  }
  if (!value || value.length > 300) return { ok: false, message: "กรอกค่า (ไม่เกิน 300 ตัวอักษร)" };
  try {
    await gh.setVariable(name, value);
  } catch (e) {
    return fail(e, "บันทึกไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: `บันทึก ${def.label} แล้ว — มีผลตั้งแต่รันครั้งถัดไป` };
}

export async function resetVariable(name: string): Promise<ActionResult> {
  await requireSession();
  if (!VARIABLES.some((v) => v.name === name)) return { ok: false, message: "ไม่รู้จักค่านี้" };
  try {
    await gh.deleteVariable(name);
  } catch (e) {
    return fail(e, "รีเซ็ตไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "กลับไปใช้ค่าเริ่มต้นแล้ว" };
}

const PRODUCT_STATUSES = ["Ready", "Hold", "New"] as const;
const STORY_STATUSES = ["Ready", "Hold"] as const;

export async function setQueueStatus(tab: "products" | "stories", id: string, status: string): Promise<ActionResult> {
  await requireSession();
  const allowed: readonly string[] = tab === "products" ? PRODUCT_STATUSES : tab === "stories" ? STORY_STATUSES : [];
  if (!allowed.includes(status)) return { ok: false, message: "คำสั่งไม่ถูกต้อง" };
  try {
    const found = await store.mutate(tab, (items) => {
      const it = (items as { id: string; status: string; updatedAt: string; lastError?: string }[]).find((x) => x.id === id);
      if (!it) return false;
      it.status = status;
      it.updatedAt = store.now();
      if (status === "Ready") it.lastError = undefined;
      return true;
    });
    if (!found) return { ok: false, message: "ไม่พบรายการนี้แล้ว" };
  } catch (e) {
    return fail(e, "อัปเดตไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: status === "Ready" ? "ส่งเข้าคิวแล้ว" : status === "Hold" ? "พักไว้แล้ว" : "อัปเดตแล้ว" };
}

export async function deleteQueueItem(tab: "products" | "stories", id: string): Promise<ActionResult> {
  await requireSession();
  if (tab !== "products" && tab !== "stories") return { ok: false, message: "คำสั่งไม่ถูกต้อง" };
  try {
    await store.mutate(tab, (items) => {
      const i = items.findIndex((x) => x.id === id);
      if (i >= 0) items.splice(i, 1);
    });
  } catch (e) {
    return fail(e, "ลบไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "ลบแล้ว" };
}

function isHttpUrl(s: string) {
  try {
    const u = new URL(s);
    return u.protocol === "https:" || u.protocol === "http:";
  } catch {
    return false;
  }
}

export async function addProduct(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const name = String(form.get("name") ?? "").trim();
  const price = String(form.get("price") ?? "").trim();
  const url = String(form.get("url") ?? "").trim();
  let image = String(form.get("image") ?? "").trim();
  const notes = String(form.get("notes") ?? "").trim();
  if (!name || name.length > 200) return { ok: false, message: "กรอกชื่อสินค้า" };
  if (!isHttpUrl(url)) return { ok: false, message: "ลิงก์ affiliate ต้องเป็น URL" };
  if (image && !isHttpUrl(image)) return { ok: false, message: "ลิงก์รูปต้องเป็น URL" };
  if (price && !/^\d+(\.\d+)?$/.test(price)) return { ok: false, message: "ราคาเป็นตัวเลขเท่านั้น" };
  if (!image) image = await productImage(url);
  try {
    const dup = await store.mutate("products", (items) => {
      if (items.some((p) => p.url === url)) return true;
      items.push({
        id: store.newId(), name, price, commission: "", sales: "", url, image, notes: notes.slice(0, 300),
        status: "Ready", source: "manual", createdAt: store.now(), updatedAt: store.now(),
      });
      return false;
    });
    if (dup) return { ok: false, message: "มีสินค้าลิงก์นี้อยู่ในคิวแล้ว" };
  } catch (e) {
    return fail(e, "เพิ่มสินค้าไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: image ? "เพิ่มเข้าคิวแล้ว (ดึงรูปสินค้าให้อัตโนมัติ)" : "เพิ่มเข้าคิวแล้ว — ไม่พบรูป จะใช้การ์ดตัวอักษรแทน" };
}

export async function importProductsCsv(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const file = form.get("file");
  const ready = form.get("ready") === "on";
  if (!(file instanceof File) || file.size === 0) return { ok: false, message: "เลือกไฟล์ CSV ก่อน" };
  if (file.size > 2_000_000) return { ok: false, message: "ไฟล์ใหญ่เกิน 2 MB" };
  const parsed = parseAffiliateCsv(await file.text());
  if (!parsed.length) return { ok: false, message: "อ่านไฟล์ไม่ได้ — ใช้ไฟล์ Batch Product Links จาก Shopee Affiliate" };
  try {
    const existing = new Set((await store.list("products")).map((p) => p.url));
    const fresh: store.Product[] = parsed.filter((p) => !existing.has(p.url)).map((p) => ({
      id: store.newId(), ...p, image: "", status: ready ? "Ready" : "New", source: "csv",
      createdAt: store.now(), updatedAt: store.now(),
    }));
    const images = await fillImages(fresh);
    await store.mutate("products", (items) => void items.push(...fresh.filter((f) => !items.some((x) => x.url === f.url))));
    refresh();
    const skipped = parsed.length - fresh.length;
    return {
      ok: true,
      message: `นำเข้า ${fresh.length} รายการ (มีรูป ${images})${skipped ? ` · ข้ามที่มีอยู่แล้ว ${skipped}` : ""}${ready ? " · เข้าคิวผลิตทันที" : " · สถานะ ใหม่ รอคุณกดเข้าคิว"}`,
    };
  } catch (e) {
    return fail(e, "นำเข้าไม่สำเร็จ");
  }
}

export async function addStory(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const topic = String(form.get("topic") ?? "").trim();
  const angle = String(form.get("angle") ?? "").trim();
  const channelId = String(form.get("channelId") ?? "") || undefined;
  if (!topic || topic.length > 140) return { ok: false, message: "กรอกหัวข้อ (ไม่เกิน 140 ตัวอักษร)" };
  try {
    await store.mutate("stories", (items) => {
      items.push({
        id: store.newId(), topic, angle: angle.slice(0, 300), status: "Ready", source: "manual", channelId,
        createdAt: store.now(), updatedAt: store.now(),
      });
    });
  } catch (e) {
    return fail(e, "เพิ่มหัวข้อไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "เพิ่มหัวข้อเข้าคิวแล้ว" };
}

export async function reviewVideo(
  id: string, decision: "approved" | "rejected" | "posted" | "review", opts: { note?: string; requeue?: boolean } = {},
): Promise<ActionResult> {
  await requireSession();
  if (!["approved", "rejected", "posted", "review"].includes(decision)) return { ok: false, message: "คำสั่งไม่ถูกต้อง" };
  try {
    const video = await store.mutate("videos", (items) => {
      const v = items.find((x) => x.id === id);
      if (!v) return null;
      v.status = decision;
      v.reviewedAt = store.now();
      if (opts.note !== undefined) v.note = opts.note.slice(0, 500);
      return { ...v };
    });
    if (!video) return { ok: false, message: "ไม่พบวิดีโอนี้แล้ว" };
    if (opts.requeue && video.refId) {
      await store.mutate(video.flow === "shopee" ? "products" : "stories", (items) => {
        const it = (items as { id: string; status: string; updatedAt: string }[]).find((x) => x.id === video.refId);
        if (it) {
          it.status = "Ready";
          it.updatedAt = store.now();
        }
      });
    }
    // Approving a story video posts it (post-video.yml publishes to its page).
    if (decision === "approved" && video.flow === "story") {
      const r = await posting.requestPost(id);
      refresh();
      return r.ok ? { ok: true, message: "ผ่านแล้ว · กำลังโพสต์… (ประมาณ 2–5 นาที)" } : { ok: false, message: `ผ่านแล้ว แต่สั่งโพสต์ไม่สำเร็จ — ${r.message}` };
    }
  } catch (e) {
    return fail(e, "บันทึกผลรีวิวไม่สำเร็จ");
  }
  refresh();
  const label = { approved: "ผ่านแล้ว", rejected: "ไม่ผ่าน", posted: "บันทึกว่าโพสต์แล้ว", review: "ย้ายกลับไปรอตรวจ" }[decision];
  return { ok: true, message: opts.requeue ? `${label} · ส่งกลับเข้าคิวให้ทำใหม่` : label };
}

export async function repostVideo(id: string): Promise<ActionResult> {
  await requireSession();
  const r = await posting.requestPost(id);
  refresh();
  return r;
}

export async function saveClaudeKey(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const key = String(form.get("key") ?? "").trim();
  if (!/^sk-ant-[A-Za-z0-9_-]{20,}$/.test(key)) {
    return { ok: false, message: "รูปแบบ key ไม่ถูกต้อง — Claude API key ขึ้นต้นด้วย sk-ant-" };
  }
  try {
    const { default: Anthropic } = await import("@anthropic-ai/sdk");
    await new Anthropic({ apiKey: key, maxRetries: 1 }).models.list({ limit: 1 });
  } catch (e) {
    const status = (e as { status?: number }).status;
    return {
      ok: false,
      message: status === 401 ? "Anthropic ปฏิเสธ key นี้ (401) — ตรวจว่าคัดลอกครบ" : `ตรวจ key ไม่ผ่าน: ${status ?? "เชื่อมต่อไม่ได้"}`,
    };
  }
  try {
    await gh.setSecret("ANTHROPIC_API_KEY", key);
  } catch (e) {
    if (e instanceof gh.GitHubError && (e.status === 403 || e.status === 404)) {
      return { ok: false, message: "GitHub token ยังไม่มีสิทธิ์เขียน secret — แก้ token: Secrets → Read and write แล้วลองใหม่" };
    }
    return fail(e, "บันทึก key ไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "บันทึก Claude key แล้ว — รอบถัดไปทั้งสอง flow จะใช้ Claude เขียนบท" };
}

export async function removeClaudeKey(): Promise<ActionResult> {
  await requireSession();
  try {
    await gh.deleteSecret("ANTHROPIC_API_KEY");
  } catch (e) {
    return fail(e, "ลบ key ไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "ลบ Claude key แล้ว — กลับไปใช้ AI สำรอง" };
}

export async function logout(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}

// ---------------------------------------------------------------------------
// Social accounts
// ---------------------------------------------------------------------------
const SOCIAL_LABEL = { facebook: "เพจ Facebook", instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube" } as const;

export async function disconnectSocial(provider: social.Provider): Promise<ActionResult> {
  await requireSession();
  if (!social.PROVIDERS.includes(provider)) return { ok: false, message: "ไม่รู้จักบริการนี้" };
  try {
    await social.disconnect(provider);
  } catch (e) {
    return fail(e, "ยกเลิกการเชื่อมไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: `ยกเลิกการเชื่อม ${SOCIAL_LABEL[provider]} แล้ว` };
}

export async function pickFacebookPages(ids: string[]): Promise<ActionResult> {
  await requireSession();
  let names: string[];
  try {
    names = await social.pickPages(ids.map(String));
  } catch (e) {
    return fail(e, "บันทึกเพจไม่สำเร็จ");
  }
  redirect(`/settings?connected=facebook&name=${encodeURIComponent(names.join(", "))}#channels`);
}

// ---------------------------------------------------------------------------
// Channels (one per Facebook page)
// ---------------------------------------------------------------------------
const THEMES = VARIABLES.find((v) => v.name === "STORY_THEME")!.options!.map((o) => o.value);

export async function saveChannel(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const id = String(form.get("id") ?? "");
  const theme = String(form.get("theme") ?? "");
  const publishMode = form.get("publishMode") === "auto" ? "auto" : "review";
  if (!THEMES.includes(theme)) return { ok: false, message: "ธีมไม่ถูกต้อง" };
  let name: string;
  try {
    name = await channels.updateChannel(id, {
      theme, publishMode, enabled: form.get("enabled") === "on",
      postHours: [...new Set(form.getAll("postHour").map(String).filter(Boolean).map(Number))]
        .filter((h) => Number.isInteger(h) && h >= 0 && h <= 23).sort((a, b) => a - b).slice(0, 3),
      seriesName: String(form.get("seriesName") ?? "").trim().slice(0, 60),
      niche: String(form.get("niche") ?? "").trim().slice(0, 300),
    });
  } catch (e) {
    return fail(e, "บันทึกไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: `บันทึกการตั้งค่าเพจ ${name} แล้ว` };
}

export async function removeChannel(id: string): Promise<ActionResult> {
  await requireSession();
  let name: string;
  try {
    name = await channels.removeChannel(id);
  } catch (e) {
    return fail(e, "นำเพจออกไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: `นำเพจ ${name} ออกแล้ว` };
}

export async function saveMetaSecret(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const secret = String(form.get("appSecret") ?? "").trim();
  if (!/^[a-f0-9]{32}$/i.test(secret)) {
    return { ok: false, message: "App secret ต้องเป็นตัวอักษร 32 ตัว — คัดลอกจาก Meta for Developers → ShopeePipeline → App settings → Basic" };
  }
  try {
    await social.saveMetaSecret(secret);
  } catch (e) {
    return fail(e, "บันทึกไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "บันทึก App secret แล้ว — กดเชื่อมเพจ Facebook ได้เลย" };
}

export async function saveGoogleApp(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const id = String(form.get("clientId") ?? "").trim();
  const secret = String(form.get("clientSecret") ?? "").trim();
  if (!/^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$/.test(id) || secret.length < 20) {
    return { ok: false, message: "Client ID / secret ไม่ถูกรูปแบบ — คัดลอกจาก Google Cloud → APIs & Services → Credentials" };
  }
  try {
    await social.saveGoogleApp(id, secret);
  } catch (e) {
    return fail(e, "บันทึกไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "บันทึก Google OAuth แล้ว — กดเชื่อม YouTube ได้เลย" };
}

export async function saveTiktokApp(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const key = String(form.get("clientKey") ?? "").trim();
  const secret = String(form.get("clientSecret") ?? "").trim();
  if (!/^[A-Za-z0-9]{8,64}$/.test(key) || secret.length < 16) {
    return { ok: false, message: "Client key / secret ไม่ถูกรูปแบบ — คัดลอกจาก developers.tiktok.com → แอปของคุณ" };
  }
  try {
    await social.saveTiktokApp(key, secret);
  } catch (e) {
    return fail(e, "บันทึกไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "บันทึกแอป TikTok แล้ว — กดเชื่อม TikTok ได้เลย" };
}
