import type { Video } from "./store";

// Which platforms an approved story video goes to, and which still need a
// (re)try. The primary channel also posts to Instagram and TikTok.

export const PLATFORMS = ["facebook", "instagram", "tiktok"] as const;

export function targets(v: Video, primaryId: string): string[] {
  return !v.channelId || v.channelId === primaryId ? [...PLATFORMS] : ["facebook"];
}

const succeeded = (r: unknown) =>
  Boolean(r && typeof r === "object" && !("error" in r) && !("skipped" in r));

/** Platforms not yet posted successfully; [] once everything worked. */
export function pending(v: Video, primaryId: string): string[] {
  return targets(v, primaryId).filter((p) => !succeeded(v.published?.[p]));
}

/** Plain-Thai reason for errors that need the user, not a retry. */
export function explainError(platform: string, error: string): string | null {
  if (platform === "tiktok" && /unaudited_client_can_only_post_to_private_accounts/.test(error)) {
    return "TikTok: ต้องตั้งบัญชีเป็นส่วนตัว หรือรอ TikTok อนุมัติแอป";
  }
  return null;
}
