"use server";

import { cookies } from "next/headers";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/dal";
import { VARIABLES, WORKFLOW_FILES } from "@/lib/flows";
import * as gh from "@/lib/github";
import * as sheets from "@/lib/sheets";
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

const STATUSES = {
  Inbox: ["Ready", "Hold", "New"],
  Stories: ["Ready", "Hold"],
} as const;

export async function setQueueStatus(tab: "Inbox" | "Stories", row: number, status: string): Promise<ActionResult> {
  await requireSession();
  if (!(tab in STATUSES) || !(STATUSES[tab] as readonly string[]).includes(status) || !(row >= 2)) {
    return { ok: false, message: "คำสั่งไม่ถูกต้อง" };
  }
  try {
    await sheets.setStatus(tab, row, status);
  } catch (e) {
    return fail(e, "อัปเดตชีตไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: status === "Ready" ? "ส่งเข้าคิวแล้ว" : status === "Hold" ? "พักไว้แล้ว" : "อัปเดตแล้ว" };
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
  const image = String(form.get("image") ?? "").trim();
  const notes = String(form.get("notes") ?? "").trim();
  if (!name || name.length > 200) return { ok: false, message: "กรอกชื่อสินค้า" };
  if (!isHttpUrl(url)) return { ok: false, message: "ลิงก์ affiliate ต้องเป็น URL" };
  if (image && !isHttpUrl(image)) return { ok: false, message: "ลิงก์รูปต้องเป็น URL" };
  if (price && !/^\d+(\.\d+)?$/.test(price)) return { ok: false, message: "ราคาเป็นตัวเลขเท่านั้น" };
  try {
    await sheets.addProduct({ name, price, url, image, notes: notes.slice(0, 300) });
  } catch (e) {
    return fail(e, "เพิ่มสินค้าไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "เพิ่มสินค้าเข้าคิวแล้ว (สถานะ Ready)" };
}

export async function addStory(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireSession();
  const topic = String(form.get("topic") ?? "").trim();
  const angle = String(form.get("angle") ?? "").trim();
  if (!topic || topic.length > 140) return { ok: false, message: "กรอกหัวข้อ (ไม่เกิน 140 ตัวอักษร)" };
  try {
    await sheets.addStory(topic, angle.slice(0, 300));
  } catch (e) {
    return fail(e, "เพิ่มหัวข้อไม่สำเร็จ");
  }
  refresh();
  return { ok: true, message: "เพิ่มหัวข้อเข้าคิวแล้ว (สถานะ Ready)" };
}

export async function logout(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}
