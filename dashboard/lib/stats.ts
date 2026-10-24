import type { Video, VideoStats } from "./store";

// Per-platform views and reactions, flattened for the stats page and review cards.

export const STAT_PLATFORMS = ["facebook", "instagram", "youtube"] as const;
export type StatPlatform = (typeof STAT_PLATFORMS)[number];
export const PLATFORM_LABEL: Record<StatPlatform, string> = { facebook: "Facebook", instagram: "Instagram", youtube: "YouTube" };

type Bucket = { views: number; reactions: number };

export function perPlatform(s: VideoStats | undefined): Record<StatPlatform, Bucket> {
  const fb = s?.facebook ?? {}, ig = s?.instagram ?? {}, yt = s?.youtube ?? {};
  const n = (x: number | undefined) => Number(x) || 0;
  return {
    facebook: { views: n(fb.plays), reactions: n(fb.likes) + n(fb.comments) + n(fb.shares) },
    instagram: { views: n(ig.views), reactions: n(ig.likes) + n(ig.comments) + n(ig.shares) + n(ig.saved) },
    youtube: { views: n(yt.views), reactions: n(yt.likes) + n(yt.comments) },
  };
}

export function summary(v: Video) {
  const p = perPlatform(v.stats);
  const views = v.stats?.totalViews || STAT_PLATFORMS.reduce((t, k) => t + p[k].views, 0);
  const reactions = STAT_PLATFORMS.reduce((t, k) => t + p[k].reactions, 0);
  return { p, views, reactions, rate: views ? reactions / views : 0 };
}

/** Start of the "last N days" window; 0 for all time. */
export function cutoff(days: string): number {
  return days === "all" ? 0 : Date.now() - Number(days) * 86_400_000;
}
