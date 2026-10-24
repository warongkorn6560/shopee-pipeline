import "server-only";
import { primaryChannelId } from "./channels";
import { readDoc } from "./social";
import { POST_VIDEO_WORKFLOW } from "./flows";
import * as gh from "./github";
import { PLATFORMS, pending } from "./posting";
import * as store from "./store";

// Dispatches post-video.yml for one approved story video. Used by the review
// page and by the Telegram buttons.

export type PostResult = { ok: boolean; message: string };

export async function requestPost(id: string): Promise<PostResult> {
  if (!gh.githubConfigured()) return { ok: false, message: "ยังไม่ได้เชื่อม GitHub" };
  try {
    // Retry only what hasn't posted yet, so Facebook/Instagram never get a duplicate.
    const v = (await store.list("videos")).find((x) => x.id === id);
    if (!v) return { ok: false, message: "ไม่พบวิดีโอนี้แล้ว" };
    const [primaryId, social] = await Promise.all([primaryChannelId(), readDoc()]);
    const todo = pending(v, primaryId, Boolean(social.accounts.youtube));
    if (!todo.length) return { ok: false, message: "โพสต์ครบทุกช่องทางแล้ว" };
    const first = !Object.keys(v.published ?? {}).some((k) => (PLATFORMS as readonly string[]).includes(k));
    if (first && v.postRequestedAt && Date.now() - Date.parse(v.postRequestedAt) < 15 * 60_000) {
      return { ok: false, message: "กำลังโพสต์อยู่ — รอผลสักครู่ก่อนกดอีกครั้ง" };
    }
    await gh.dispatch(POST_VIDEO_WORKFLOW, first ? { video_id: id } : { video_id: id, only: todo.join(",") });
    await store.mutate("videos", (items) => {
      const x = items.find((it) => it.id === id);
      if (x) x.postRequestedAt = store.now();
    });
  } catch (e) {
    return { ok: false, message: `สั่งโพสต์ไม่สำเร็จ: ${e instanceof Error ? e.message.slice(0, 200) : String(e)}` };
  }
  return { ok: true, message: "กำลังโพสต์… (ประมาณ 2–5 นาที)" };
}

/** Approve (or reject) a video still waiting for review; approving a story video posts it. */
export async function decide(id: string, decision: "approved" | "rejected"): Promise<PostResult> {
  const video = await store.mutate("videos", (items) => {
    const v = items.find((x) => x.id === id);
    if (!v) return null;
    if (v.status === "review") {
      v.status = decision;
      v.reviewedAt = store.now();
    }
    return { ...v };
  });
  if (!video) return { ok: false, message: "ไม่พบวิดีโอนี้แล้ว (อาจหมดอายุ)" };
  if (video.status !== decision) return { ok: false, message: `คลิปนี้ถูกตัดสินไปแล้ว (${video.status})` };
  if (decision === "rejected") return { ok: true, message: "ไม่ผ่าน" };
  if (video.flow !== "story") return { ok: true, message: "ผ่านแล้ว · โพสต์เองตามปกติ" };
  const r = await requestPost(id);
  return r.ok ? { ok: true, message: "ผ่านแล้ว · กำลังโพสต์…" } : { ok: false, message: `ผ่านแล้ว แต่สั่งโพสต์ไม่สำเร็จ — ${r.message}` };
}
