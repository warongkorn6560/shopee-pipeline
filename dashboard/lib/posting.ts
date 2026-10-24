import type { Video } from "./store";

// Which platforms an approved story video goes to, and which still need a
// (re)try. The primary channel also posts to Instagram and TikTok.

export const PLATFORMS = ["facebook", "instagram", "tiktok", "youtube"] as const;

/** YouTube only counts once a channel is connected (otherwise the pipeline skips it). */
export function targets(v: Video, primaryId: string, youtube = false): string[] {
  if (v.channelId && v.channelId !== primaryId) return ["facebook"];
  return PLATFORMS.filter((p) => p !== "youtube" || youtube);
}

const succeeded = (r: unknown) =>
  Boolean(r && typeof r === "object" && !("error" in r) && !("skipped" in r));

/** Platforms not yet posted successfully; [] once everything worked. */
export function pending(v: Video, primaryId: string, youtube = false): string[] {
  return targets(v, primaryId, youtube).filter((p) => !succeeded(v.published?.[p]));
}

/** Plain-Thai reason for errors that need the user, not a retry. */
export function explainError(platform: string, error: string): string | null {
  if (platform === "tiktok" && /unaudited_client_can_only_post_to_private_accounts/.test(error)) {
    return "TikTok: ต้องตั้งบัญชีเป็นส่วนตัว หรือรอ TikTok อนุมัติแอป";
  }
  if (platform === "youtube" && /quota/i.test(error)) return "YouTube: โควตาวันนี้เต็ม (≈6 คลิป/วัน) — กดโพสต์อีกครั้งพรุ่งนี้";
  return null;
}
