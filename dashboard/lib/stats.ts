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

export type GrowthPoint = { t: number; facebook: number; instagram: number; youtube: number };

/**
 * Total views over time across clips: each clip contributes its latest snapshot
 * at or before every bucket (snapshots are cumulative counts).
 */
export function growth(videos: Video[], since: number, maxPoints = 120): GrowthPoint[] {
  const series = videos.map((v) => {
    const h = v.statsHistory?.length ? v.statsHistory
      : v.stats ? [{ t: v.stats.updatedAt, fb: v.stats.facebook?.plays ?? 0, ig: v.stats.instagram?.views ?? 0, yt: v.stats.youtube?.views ?? 0 }] : [];
    return h.map((p) => ({ ...p, ms: Date.parse(p.t) })).filter((p) => !Number.isNaN(p.ms));
  });
  const HOUR = 3_600_000;
  const stamps = [...new Set(series.flat().map((p) => Math.ceil(p.ms / HOUR) * HOUR))].filter((t) => t >= since).sort((a, b) => a - b);
  const step = Math.max(1, Math.ceil(stamps.length / maxPoints));
  const picked = stamps.filter((_, i) => i % step === 0 || i === stamps.length - 1);
  return picked.map((t) => {
    const out: GrowthPoint = { t, facebook: 0, instagram: 0, youtube: 0 };
    for (const s of series) {
      let last: (typeof s)[number] | undefined;
      for (const p of s) if (p.ms <= t) last = p; else break;
      if (last) {
        out.facebook += last.fb;
        out.instagram += last.ig;
        out.youtube += last.yt;
      }
    }
    return out;
  });
}
