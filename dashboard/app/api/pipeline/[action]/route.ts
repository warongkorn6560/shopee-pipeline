import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { channelToken, channels, primaryChannelId } from "@/lib/channels";
import { fillImages, productImage } from "@/lib/shopee";
import {
  expireOldVideos, list, mutate, newId, now, presignedPlayback, presignedUpload,
  type Product, type Story, type Video, type VideoStatus,
} from "@/lib/store";

// Machine API for the GitHub Actions pipeline (Bearer PIPELINE_API_KEY).
// Excluded from the session proxy; every request is authorized here.

type Flow = "shopee" | "story";
const STALE_MS = 3 * 60 * 60 * 1000; // a run that died mid-way releases its item after 3h

function authorized(req: Request): boolean {
  const key = process.env.PIPELINE_API_KEY ?? "";
  const got = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (key.length < 24 || !got) return false;
  const h = (s: string) => createHash("sha256").update(s).digest();
  return timingSafeEqual(h(key), h(got));
}

const bad = (message: string, status = 400) => NextResponse.json({ error: message }, { status });
const isFlow = (f: unknown): f is Flow => f === "shopee" || f === "story";

function releaseStale<T extends { status: string; updatedAt: string; lastError?: string }>(items: T[]) {
  for (const it of items) {
    if (it.status === "Producing" && Date.now() - Date.parse(it.updatedAt) > STALE_MS) {
      it.status = "Failed" as T["status"];
      it.lastError = "รันค้างเกิน 3 ชั่วโมง ระบบปล่อยคิวคืน";
      it.updatedAt = now();
    }
  }
}

function parseCost(raw: unknown): Video["cost"] {
  if (!raw || typeof raw !== "object") return undefined;
  const c = raw as Record<string, unknown>;
  const n = (k: string) => Math.max(0, Number(c[k]) || 0);
  return { inputTokens: n("inputTokens"), outputTokens: n("outputTokens"), claudeUsd: n("claudeUsd"), ttsChars: n("ttsChars") };
}

const PRODUCT_PATCH = ["status", "lastError", "videoId", "image"] as const;
const STORY_PATCH = ["status", "title", "runUrl", "published", "lastError", "videoId"] as const;

export async function GET(req: Request, { params }: { params: Promise<{ action: string }> }) {
  if (!authorized(req)) return bad("unauthorized", 401);
  if ((await params).action !== "channels") return bad("unknown action", 404);
  return NextResponse.json(await channels());
}

export async function POST(req: Request, { params }: { params: Promise<{ action: string }> }) {
  if (!authorized(req)) return bad("unauthorized", 401);
  const { action } = await params;
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const origin = new URL(req.url).origin;

  switch (action) {
    case "claim": {
      if (!isFlow(body.flow)) return bad("flow must be shopee or story");
      if (body.flow === "shopee") {
        const item = await mutate("products", (items) => {
          releaseStale(items);
          const p = items.find((x) => x.status === "Ready");
          if (p) {
            p.status = "Producing";
            p.updatedAt = now();
          }
          return p ? { ...p } : null;
        });
        if (item && !item.image) {
          item.image = await productImage(item.url);
          if (item.image) {
            await mutate("products", (items) => {
              const p = items.find((x) => x.id === item.id);
              if (p) p.image = item.image;
            });
          }
        }
        return NextResponse.json({ item });
      }
      // Each channel claims its own topics; topics without a channel belong to the primary one.
      const primaryId = await primaryChannelId();
      const target = typeof body.channelId === "string" && body.channelId ? body.channelId : primaryId;
      const mine = (s: Story) => (s.channelId || primaryId) === target;
      const item = await mutate("stories", (items) => {
        releaseStale(items);
        const s = items.find((x) => x.status === "Ready" && mine(x));
        if (s) {
          s.status = "Producing";
          s.updatedAt = now();
        }
        return s ? { ...s } : null;
      });
      if (item) return NextResponse.json({ item });
      const previousTopics = (await list("stories")).filter(mine).map((s) => s.topic);
      return NextResponse.json({ item: null, previousTopics });
    }

    case "update": {
      if (!isFlow(body.flow) || typeof body.id !== "string") return bad("flow and id required");
      const patch = (body.patch ?? {}) as Record<string, unknown>;
      const keys = body.flow === "shopee" ? PRODUCT_PATCH : STORY_PATCH;
      const found = await mutate(body.flow === "shopee" ? "products" : "stories", (items) => {
        const it = (items as (Product | Story)[]).find((x) => x.id === body.id) as Record<string, unknown> | undefined;
        if (!it) return false;
        for (const k of keys) if (k in patch) it[k] = String(patch[k] ?? "").slice(0, 1000);
        it.updatedAt = now();
        return true;
      });
      return found ? NextResponse.json({ ok: true }) : bad("not found", 404);
    }

    case "stories": {
      // Start (or queue) a specific topic; reuses the existing entry for the same topic.
      const topic = String(body.topic ?? "").trim().slice(0, 140);
      if (!topic) return bad("topic required");
      const channelId = typeof body.channelId === "string" && body.channelId ? body.channelId : undefined;
      const status = body.status === "Producing" ? "Producing" : "Ready";
      const source = body.source === "auto" ? "auto" : "manual";
      const item = await mutate("stories", (items) => {
        const existing = items.find((s) => s.topic === topic && s.channelId === channelId);
        if (existing) {
          if (existing.status !== "Producing") {
            existing.status = status;
            existing.lastError = undefined;
            existing.updatedAt = now();
          }
          return { ...existing };
        }
        const story: Story = {
          id: newId(), topic, angle: String(body.angle ?? "").slice(0, 300), status,
          source, channelId, createdAt: now(), updatedAt: now(),
        };
        items.push(story);
        return story;
      });
      return NextResponse.json({ item });
    }

    case "channels":
      return NextResponse.json(await channels());

    case "channel-token": {
      // The page token for publishing; only ever returned to the pipeline key.
      if (typeof body.channelId !== "string") return bad("channelId required");
      const got = await channelToken(body.channelId);
      if (!got) return bad("channel not found", 404);
      return NextResponse.json({ channelId: got.channel.id, pageId: got.channel.pageId, name: got.channel.name, token: got.token });
    }

    case "video": {
      // Everything post-video.yml needs to publish one approved video.
      if (typeof body.id !== "string") return bad("id required");
      const v = (await list("videos")).find((x) => x.id === body.id);
      if (!v) return bad("video not found", 404);
      if (!v.pathname) return bad("video file has expired", 410);
      const primaryId = await primaryChannelId();
      const ch = v.channelId ? await channelToken(v.channelId) : null;
      return NextResponse.json({
        id: v.id, flow: v.flow, title: v.title, caption: v.caption,
        url: await presignedPlayback(v.pathname, 60),
        primary: !v.channelId || v.channelId === primaryId,
        published: v.published ?? {},
        ...(ch ? { channelId: ch.channel.id, channelName: ch.channel.name, pageId: ch.channel.pageId, token: ch.token } : {}),
      });
    }

    case "videos-list": {
      // Posted videos with their platform ids, for stats.yml and topic learning.
      const flow = isFlow(body.flow) ? body.flow : "story";
      const since = Date.now() - Math.min(Math.max(Number(body.days) || 60, 1), 365) * 86_400_000;
      const [videos, stories] = await Promise.all([list("videos"), list("stories")]);
      const topics = new Map(stories.map((s) => [s.id, s.topic]));
      const hasPost = (v: Video) => v.status === "posted" || Object.values(v.published ?? {}).some(
        (r) => r && typeof r === "object" && !("error" in r) && !("skipped" in r),
      );
      return NextResponse.json({
        videos: videos
          .filter((v) => v.flow === flow && Date.parse(v.createdAt) >= since && hasPost(v))
          .map((v) => ({
            id: v.id, title: v.title, refId: v.refId, topic: topics.get(v.refId) ?? "", channelId: v.channelId ?? "",
            published: v.published ?? {}, stats: v.stats ?? null, createdAt: v.createdAt,
          })),
      });
    }

    case "video-stats": {
      if (typeof body.id !== "string" || !body.stats || typeof body.stats !== "object") return bad("id and stats required");
      const stats = { ...(body.stats as Record<string, unknown>) } as unknown as Video["stats"];
      const found = await mutate("videos", (items) => {
        const v = items.find((x) => x.id === body.id);
        if (!v) return false;
        v.stats = { ...stats!, totalViews: Number(stats!.totalViews) || 0, engagement: Number(stats!.engagement) || 0, updatedAt: stats!.updatedAt || now() };
        return true;
      });
      return found ? NextResponse.json({ ok: true }) : bad("not found", 404);
    }

    case "video-posted": {
      if (typeof body.id !== "string") return bad("id required");
      const found = await mutate("videos", (items) => {
        const v = items.find((x) => x.id === body.id);
        if (!v) return false;
        // Merge, so a retry for one platform never erases another platform's success.
        v.published = { ...v.published, ...((body.published as Record<string, unknown>) ?? {}) };
        if (body.posted === true) v.status = "posted";
        return true;
      });
      return found ? NextResponse.json({ ok: true }) : bad("not found", 404);
    }

    case "upload-url": {
      if (!isFlow(body.flow)) return bad("flow required");
      const videoId = newId();
      const pathname = `videos/${body.flow}/${videoId}.mp4`;
      return NextResponse.json({
        videoId, pathname, uploadUrl: await presignedUpload(pathname),
        reviewUrl: `${origin}/review#v-${videoId}`,
      });
    }

    case "videos": {
      if (!isFlow(body.flow) || typeof body.videoId !== "string" || typeof body.pathname !== "string") {
        return bad("flow, videoId, pathname required");
      }
      const status: VideoStatus = body.status === "posted" ? "posted" : "review";
      const video: Video = {
        id: body.videoId, flow: body.flow, refId: String(body.refId ?? ""),
        title: String(body.title ?? "").slice(0, 200), pathname: body.pathname,
        size: Number(body.size ?? 0), caption: String(body.caption ?? "").slice(0, 4000),
        reviewText: String(body.reviewText ?? "").slice(0, 6000),
        link: body.link ? String(body.link) : undefined,
        sources: Array.isArray(body.sources) ? body.sources.map(String).slice(0, 10) : undefined,
        runUrl: body.runUrl ? String(body.runUrl) : undefined,
        published: (body.published as Record<string, unknown>) ?? undefined,
        cost: parseCost(body.cost),
        channelId: typeof body.channelId === "string" && body.channelId ? body.channelId : undefined,
        status, createdAt: now(),
      };
      await mutate("videos", (items) => {
        const i = items.findIndex((v) => v.id === video.id);
        if (i >= 0) items[i] = video;
        else items.unshift(video);
      });
      const expired = await expireOldVideos().catch(() => 0);
      return NextResponse.json({ ok: true, reviewUrl: `${origin}/review#v-${video.id}`, expired });
    }

    case "import": {
      const products = Array.isArray(body.products) ? (body.products as Partial<Product>[]) : [];
      const stories = Array.isArray(body.stories) ? (body.stories as Partial<Story>[]) : [];
      const added = { products: 0, stories: 0, images: 0 };
      if (products.length) {
        const fresh: Product[] = [];
        const existing = await list("products");
        const seen = new Set(existing.map((p) => p.url));
        for (const p of products) {
          if (!p.url || !p.name || seen.has(p.url)) continue;
          seen.add(p.url);
          fresh.push({
            id: newId(), name: p.name, price: p.price ?? "", commission: p.commission ?? "",
            sales: p.sales ?? "", url: p.url, image: p.image ?? "", notes: p.notes ?? "",
            status: (p.status as Product["status"]) ?? "New", source: p.source ?? "sheet",
            lastError: p.lastError, createdAt: p.createdAt ?? now(), updatedAt: now(),
          });
        }
        added.images = await fillImages(fresh);
        await mutate("products", (items) => void items.push(...fresh.filter((f) => !items.some((x) => x.url === f.url))));
        added.products = fresh.length;
      }
      if (stories.length) {
        const fresh = await mutate("stories", (items) => {
          const seen = new Set(items.map((s) => s.topic));
          const add: Story[] = [];
          for (const s of stories) {
            if (!s.topic || seen.has(s.topic)) continue;
            seen.add(s.topic);
            add.push({
              id: newId(), topic: s.topic, angle: s.angle ?? "", status: (s.status as Story["status"]) ?? "Ready",
              title: s.title, runUrl: s.runUrl, published: s.published, source: s.source ?? "sheet",
              createdAt: s.createdAt ?? now(), updatedAt: now(),
            });
          }
          items.push(...add);
          return add.length;
        });
        added.stories = fresh;
      }
      return NextResponse.json({ ok: true, added });
    }
  }
  return bad("unknown action", 404);
}
