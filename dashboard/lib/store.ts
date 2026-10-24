import "server-only";
import { BlobPreconditionFailedError, get, issueSignedToken, presignUrl, put, del } from "@vercel/blob";

// The dashboard's own data lives as JSON documents in the private Blob
// store "pipeline-data", next to the rendered videos:
//   data/products.json  data/stories.json  data/videos.json  data/channels.json   videos/<id>.mp4
// Writes are optimistic: read with an ETag, write with ifMatch, retry on conflict.

export type ProductStatus = "New" | "Ready" | "Producing" | "Posted" | "Failed" | "Hold";
export type StoryStatus = "Ready" | "Producing" | "Done" | "Posted" | "Failed" | "Hold";
export type VideoStatus = "review" | "approved" | "rejected" | "posted";

export interface Product {
  id: string;
  name: string;
  price: string;
  commission: string;
  sales: string;
  url: string;
  image: string;
  notes: string;
  status: ProductStatus;
  source: "sheet" | "csv" | "manual";
  lastError?: string;
  videoId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Story {
  id: string;
  topic: string;
  angle: string;
  status: StoryStatus;
  title?: string;
  runUrl?: string;
  published?: string;
  lastError?: string;
  videoId?: string;
  channelId?: string; // unset = the primary channel
  source: "sheet" | "manual" | "auto";
  createdAt: string;
  updatedAt: string;
}

export interface Video {
  id: string;
  flow: "shopee" | "story";
  refId: string;
  title: string;
  pathname: string | null; // null once the file has expired
  size: number;
  caption: string;
  reviewText: string;
  link?: string;
  sources?: string[];
  status: VideoStatus;
  note?: string;
  runUrl?: string;
  published?: Record<string, unknown>;
  cost?: VideoCost;
  stats?: VideoStats;
  style?: string; // editing style the pipeline picked (STORY_STYLE_MIX), e.g. "classic" / "reaction"
  channelId?: string; // story videos: the page it was made for (unset = primary)
  postRequestedAt?: string; // approve → post-video.yml dispatched
  createdAt: string;
  reviewedAt?: string;
}

/** Views and reactions per platform, refreshed by stats.yml every 6h. */
export interface VideoStats {
  facebook?: { plays?: number; likes?: number; comments?: number; shares?: number };
  instagram?: { views?: number; reach?: number; likes?: number; comments?: number; shares?: number; saved?: number };
  youtube?: { views?: number; likes?: number; comments?: number };
  totalViews: number;
  engagement: number;
  updatedAt: string;
}

/** What one video cost to make, as reported by the pipeline. */
export interface VideoCost {
  inputTokens: number;
  outputTokens: number;
  claudeUsd: number;
  ttsChars: number;
}

/** A page the story flow publishes to, with its own content settings. */
export interface Channel {
  id: string;
  platform: "facebook";
  pageId: string;
  name: string;
  theme: string; // STORY_THEME value
  seriesName: string; // "" = the theme's default
  niche: string; // "" = the theme's default
  publishMode: "review" | "auto";
  postHours?: number[]; // Bangkok hours, 1–3; empty = STORY_POST_HOURS
  enabled: boolean;
  tokenEnc: string; // page token, AES-GCM sealed (lib/channels.ts)
  connectedAt: string;
  updatedAt: string;
}

type Collections = { products: Product; stories: Story; videos: Video; channels: Channel };
type Name = keyof Collections;

const path = (name: Name) => `data/${name}.json`;
export const VIDEO_RETENTION_DAYS = 30;

export function storeConfigured(): boolean {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN);
}

async function read<N extends Name>(name: N): Promise<{ items: Collections[N][]; etag: string | null }> {
  const res = await get(path(name), { access: "private", useCache: false });
  if (!res || res.statusCode !== 200) return { items: [], etag: null };
  const doc = JSON.parse(await new Response(res.stream).text()) as { items?: Collections[N][] };
  // Compressed responses carry a weak ETag (W/"…"); conditional writes need the strong form.
  return { items: doc.items ?? [], etag: res.blob.etag.replace(/^W\//, "") };
}

export async function list<N extends Name>(name: N): Promise<Collections[N][]> {
  return (await read(name)).items;
}

/** Apply `fn` to the collection and save it, retrying if someone else wrote first. */
export async function mutate<N extends Name, R>(
  name: N,
  fn: (items: Collections[N][]) => R,
): Promise<R> {
  for (let attempt = 0; attempt < 6; attempt++) {
    const { items, etag } = await read(name);
    const result = fn(items);
    try {
      await put(path(name), JSON.stringify({ items }), {
        access: "private",
        contentType: "application/json",
        cacheControlMaxAge: 60,
        ...(etag ? { allowOverwrite: true, ifMatch: etag } : { allowOverwrite: false }),
      });
      return result;
    } catch (e) {
      const conflict = e instanceof BlobPreconditionFailedError || /precondition|etag mismatch|already exists/i.test(String(e));
      if (!conflict || attempt === 5) throw e;
      await new Promise((r) => setTimeout(r, 120 + Math.random() * 300));
    }
  }
  throw new Error("unreachable");
}

export function newId(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 10);
}

export const now = () => new Date().toISOString();

// ---------------------------------------------------------------------------
// Video files
// ---------------------------------------------------------------------------
export async function presignedUpload(pathname: string): Promise<string> {
  const token = await issueSignedToken({
    pathname,
    operations: ["put"],
    validUntil: Date.now() + 30 * 60_000,
    allowedContentTypes: ["video/mp4", "application/json"],
    maximumSizeInBytes: 200 * 1024 * 1024,
  });
  const { presignedUrl } = await presignUrl(token, {
    operation: "put", pathname, access: "private", allowOverwrite: true, addRandomSuffix: false,
  });
  return presignedUrl;
}

export async function presignedPlayback(pathname: string, minutes = 120): Promise<string> {
  const token = await issueSignedToken({
    pathname, operations: ["get"], validUntil: Date.now() + minutes * 60_000,
  });
  return (await presignUrl(token, { operation: "get", pathname, access: "private" })).presignedUrl;
}

/** Delete video files older than the retention window; keeps their records. */
export async function expireOldVideos(): Promise<number> {
  const cutoff = Date.now() - VIDEO_RETENTION_DAYS * 86_400_000;
  const stale = (await list("videos")).filter((v) => v.pathname && Date.parse(v.createdAt) < cutoff);
  if (!stale.length) return 0;
  await del(stale.map((v) => v.pathname!));
  await mutate("videos", (items) => {
    for (const v of items) if (stale.some((s) => s.id === v.id)) v.pathname = null;
  });
  return stale.length;
}
