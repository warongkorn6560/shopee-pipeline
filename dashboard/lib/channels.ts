import "server-only";
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import * as gh from "./github";
import { readDoc, writeDoc, type PendingPage } from "./social";
import { list, mutate, now, type Channel } from "./store";

// Publishing channels: every Facebook page the story flow posts to, each with
// its own theme, series label and publish mode, so new pages can be added over
// time. Page tokens are sealed with AES-GCM before they go into the Blob doc.
// The first enabled page stays mirrored in FACEBOOK_PAGE_ID / FACEBOOK_PAGE_TOKEN
// for pipeline runs that don't pass a channel.

export type PublicChannel = Omit<Channel, "tokenEnc" | "instagram"> & {
  postHours: number[];
  instagram?: { id: string; username: string; expiresAt: string };
};

function key(): Buffer {
  const secret = process.env.CHANNEL_KEY || process.env.SESSION_SECRET;
  if (!secret) throw new Error("ยังไม่ได้ตั้ง CHANNEL_KEY / SESSION_SECRET");
  return createHash("sha256").update(`channels:${secret}`).digest();
}

function seal(text: string): string {
  const iv = randomBytes(12);
  const c = createCipheriv("aes-256-gcm", key(), iv);
  const enc = Buffer.concat([c.update(text, "utf8"), c.final()]);
  return [iv, c.getAuthTag(), enc].map((b) => b.toString("base64url")).join(".");
}

function unseal(sealed: string): string {
  const [iv, tag, enc] = sealed.split(".").map((x) => Buffer.from(x, "base64url"));
  const d = createDecipheriv("aes-256-gcm", key(), iv);
  d.setAuthTag(tag);
  return Buffer.concat([d.update(enc), d.final()]).toString("utf8");
}

function publicView(c: Channel): PublicChannel {
  const { tokenEnc, instagram, ...rest } = c;
  void tokenEnc;
  return {
    ...rest, postHours: rest.postHours ?? [],
    ...(instagram ? { instagram: { id: instagram.id, username: instagram.username, expiresAt: instagram.expiresAt } } : {}),
  };
}
// The primary channel is always a Facebook page: it is mirrored into the legacy page secrets.
const pickPrimary = (items: Channel[]) => items.find((c) => c.enabled && c.platform === "facebook") ?? null;

export async function channels(): Promise<{ channels: PublicChannel[]; primaryId: string }> {
  const items = await list("channels");
  return { channels: items.map(publicView), primaryId: pickPrimary(items)?.id ?? "" };
}

/** Where each channel's clips go: primary id plus, per other channel, its own platforms. */
export async function routing(): Promise<{ primaryId: string; own: Record<string, string[]> }> {
  const items = await list("channels");
  const own: Record<string, string[]> = {};
  for (const c of items) own[c.id] = [...(c.platform === "facebook" ? ["facebook"] : []), ...(c.instagram ? ["instagram"] : [])];
  return { primaryId: pickPrimary(items)?.id ?? "", own };
}

export async function primaryChannelId(): Promise<string> {
  return pickPrimary(await list("channels"))?.id ?? "";
}

export type ChannelTokens = { channel: PublicChannel; token: string; instagram?: { userId: string; token: string } };

export async function channelToken(id: string): Promise<ChannelTokens | null> {
  const c = (await list("channels")).find((x) => x.id === id);
  if (!c) return null;
  return {
    channel: publicView(c),
    token: c.tokenEnc ? unseal(c.tokenEnc) : "",
    ...(c.instagram ? { instagram: { userId: c.instagram.id, token: unseal(c.instagram.tokenEnc) } } : {}),
  };
}

export type IgAccount = { id: string; username: string; token: string; expiresAt: string };

/** Give a channel its own IG account; target "new" creates an IG-only channel. Returns the channel id. */
export async function attachInstagram(target: string, acct: IgAccount): Promise<string> {
  const ig = { id: acct.id, username: acct.username, tokenEnc: seal(acct.token), expiresAt: acct.expiresAt, connectedAt: now() };
  const id = await mutate("channels", (items) => {
    // One IG account belongs to one channel.
    for (const c of items) if (c.instagram?.id === acct.id && c.id !== target) delete c.instagram;
    if (target === "new") {
      const existing = items.find((c) => c.platform === "instagram" && c.pageId === acct.id);
      if (existing) {
        Object.assign(existing, { name: `@${acct.username}`, instagram: ig, updatedAt: now() });
        return existing.id;
      }
      items.push({
        id: `ig-${acct.id}`, platform: "instagram", pageId: acct.id, name: `@${acct.username}`,
        theme: "wildlife", seriesName: "", niche: "", publishMode: "review", postHours: [], enabled: true,
        tokenEnc: "", instagram: ig, connectedAt: now(), updatedAt: now(),
      });
      return `ig-${acct.id}`;
    }
    const c = items.find((x) => x.id === target);
    if (!c) return null;
    Object.assign(c, { instagram: ig, updatedAt: now() });
    return c.id;
  });
  if (!id) throw new Error("ไม่พบช่องที่จะผูก Instagram");
  return id;
}

export async function detachInstagram(id: string): Promise<void> {
  await mutate("channels", (items) => {
    const c = items.find((x) => x.id === id);
    if (c) delete c.instagram;
  });
}

/** Daily: refresh channel IG tokens with under 45 days left. */
export async function refreshChannelInstagram(
  refresh: (token: string) => Promise<{ access_token: string; expires_in: number }>,
): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  const due = (await list("channels")).filter((c) => c.instagram && !(Date.parse(c.instagram.expiresAt) - Date.now() > 45 * 86_400_000));
  for (const c of due) {
    try {
      const r = await refresh(unseal(c.instagram!.tokenEnc));
      await mutate("channels", (items) => {
        const x = items.find((y) => y.id === c.id);
        if (x?.instagram) Object.assign(x.instagram, { tokenEnc: seal(r.access_token), expiresAt: new Date(Date.now() + r.expires_in * 1000).toISOString() });
      });
      out[`instagram:${c.id}`] = "refreshed";
    } catch (e) {
      out[`instagram:${c.id}`] = String(e);
    }
  }
  return out;
}

/** Add pages (or refresh the token of pages already connected, keeping their settings). */
export async function addFacebookPages(pages: PendingPage[]): Promise<void> {
  await mutate("channels", (items) => {
    for (const p of pages) {
      const existing = items.find((c) => c.platform === "facebook" && c.pageId === p.id);
      if (existing) {
        Object.assign(existing, { name: p.name, tokenEnc: seal(p.token), updatedAt: now() });
        continue;
      }
      items.push({
        id: `fb-${p.id}`, platform: "facebook", pageId: p.id, name: p.name,
        theme: "wildlife", seriesName: "", niche: "", publishMode: "review", postHours: [], enabled: true,
        tokenEnc: seal(p.token), connectedAt: now(), updatedAt: now(),
      });
    }
  });
  await syncPrimary();
}

export type ChannelPatch = Partial<Pick<Channel, "theme" | "seriesName" | "niche" | "publishMode" | "postHours" | "enabled">>;

export async function updateChannel(id: string, patch: ChannelPatch): Promise<string> {
  const before = await primaryChannelId();
  const name = await mutate("channels", (items) => {
    const c = items.find((x) => x.id === id);
    if (!c) return null;
    Object.assign(c, patch, { updatedAt: now() });
    return c.name;
  });
  if (!name) throw new Error("ไม่พบเพจนี้");
  if ((await primaryChannelId()) !== before) await syncPrimary();
  return name;
}

export async function removeChannel(id: string): Promise<string> {
  const name = await mutate("channels", (items) => {
    const i = items.findIndex((x) => x.id === id);
    return i < 0 ? null : items.splice(i, 1)[0].name;
  });
  if (!name) throw new Error("ไม่พบเพจนี้");
  await syncPrimary();
  return name;
}

export async function removeAllFacebook(): Promise<void> {
  await mutate("channels", (items) => void items.splice(0, items.length, ...items.filter((c) => c.platform !== "facebook")));
  await syncPrimary();
}

/** Mirror the primary page into the legacy GitHub secrets and the social doc. */
async function syncPrimary(): Promise<void> {
  const primary = pickPrimary(await list("channels"));
  const doc = await readDoc();
  if (primary) {
    await gh.setSecret("FACEBOOK_PAGE_ID", primary.pageId);
    await gh.setSecret("FACEBOOK_PAGE_TOKEN", unseal(primary.tokenEnc));
    doc.accounts.facebook = { id: primary.pageId, name: primary.name, connectedAt: primary.connectedAt };
  } else {
    await gh.deleteSecret("FACEBOOK_PAGE_ID");
    await gh.deleteSecret("FACEBOOK_PAGE_TOKEN");
    delete doc.accounts.facebook;
  }
  delete doc.pending;
  await writeDoc(doc);
}
