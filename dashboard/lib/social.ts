import "server-only";
import { get, put } from "@vercel/blob";
import * as channels from "./channels";
import * as gh from "./github";

// One-click social connections. The OAuth dance runs here; the tokens the
// pipeline needs are written to GitHub Actions secrets (FACEBOOK_PAGE_*,
// INSTAGRAM_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN). Secrets are write-only, so the
// tokens that must be refreshed later (Instagram, TikTok) are also kept in the
// private Blob doc data/social.json, together with what to show in the UI.
// Facebook pages are channels (lib/channels.ts): one sign-in can add many pages.

export type Provider = "facebook" | "instagram" | "tiktok";
export const PROVIDERS: Provider[] = ["facebook", "instagram", "tiktok"];

const GRAPH = "https://graph.facebook.com/v22.0";
const IG_GRAPH = "https://graph.instagram.com";

export interface Account {
  id: string;
  name: string;
  connectedAt: string;
  token?: string; // instagram long-lived token / tiktok refresh token
  expiresAt?: string;
}

export interface PendingPage {
  id: string;
  name: string;
  token: string;
}

interface SocialDoc {
  accounts: Partial<Record<Provider, Account>>;
  apps?: { tiktok?: { clientKey: string; clientSecret: string }; meta?: { appSecret: string } };
  pending?: { pages: PendingPage[]; until: number };
}

const DOC = "data/social.json";

export async function readDoc(): Promise<SocialDoc> {
  const res = await get(DOC, { access: "private", useCache: false });
  if (!res || res.statusCode !== 200) return { accounts: {} };
  const doc = JSON.parse(await new Response(res.stream).text()) as SocialDoc;
  return { ...doc, accounts: doc.accounts ?? {} };
}

export async function writeDoc(doc: SocialDoc): Promise<void> {
  await put(DOC, JSON.stringify(doc), {
    access: "private", contentType: "application/json", allowOverwrite: true, cacheControlMaxAge: 60,
  });
}

/** Public view for the UI: never includes tokens or app secrets. */
export async function connections() {
  const doc = await readDoc();
  const view = Object.fromEntries(
    PROVIDERS.map((p) => {
      const a = doc.accounts[p];
      return [p, a ? { id: a.id, name: a.name, connectedAt: a.connectedAt, expiresAt: a.expiresAt } : null];
    }),
  ) as Record<Provider, { id: string; name: string; connectedAt: string; expiresAt?: string } | null>;
  return { accounts: view, tiktokApp: Boolean(tiktokApp(doc)), metaApp: Boolean(metaApp(doc)), igApp: Boolean(igApp()), hasPending: Boolean(doc.pending && doc.pending.until > Date.now()) };
}

// ---------------------------------------------------------------------------
// App credentials
// ---------------------------------------------------------------------------
export const META_APP_ID = process.env.META_APP_ID || "27095692366789442";

function metaApp(doc?: SocialDoc) {
  const id = META_APP_ID, secret = process.env.META_APP_SECRET || doc?.apps?.meta?.appSecret;
  return id && secret ? { id, secret } : null;
}

// "Instagram API with Instagram Login" has its own app ID/secret inside the Meta app.
function igApp() {
  const id = process.env.INSTAGRAM_APP_ID || process.env.META_APP_ID;
  const secret = process.env.INSTAGRAM_APP_SECRET || process.env.META_APP_SECRET;
  return id && secret ? { id, secret } : null;
}

function tiktokApp(doc?: SocialDoc) {
  const key = process.env.TIKTOK_CLIENT_KEY || doc?.apps?.tiktok?.clientKey;
  const secret = process.env.TIKTOK_CLIENT_SECRET || doc?.apps?.tiktok?.clientSecret;
  return key && secret ? { key, secret } : null;
}

export function appReady(p: Provider, doc?: SocialDoc): boolean {
  return Boolean(p === "tiktok" ? tiktokApp(doc) : p === "instagram" ? igApp() : metaApp(doc));
}

export const redirectUri = (origin: string, p: Provider) => `${origin}/api/connect/${p}/callback`;

export async function authUrl(p: Provider, origin: string, state: string): Promise<string> {
  const redirect_uri = redirectUri(origin, p);
  if (p === "facebook") {
    const app = metaApp(await readDoc())!;
    return `https://www.facebook.com/v22.0/dialog/oauth?${new URLSearchParams({
      client_id: app.id, redirect_uri, state, response_type: "code",
      // Facebook Login for Business: the configuration carries the page permissions
      // (pages_show_list, pages_read_engagement, pages_manage_posts).
      config_id: process.env.FB_LOGIN_CONFIG_ID || "2039499073210511",
    })}`;
  }
  if (p === "instagram") {
    const app = igApp()!;
    return `https://www.instagram.com/oauth/authorize?${new URLSearchParams({
      client_id: app.id, redirect_uri, state, response_type: "code",
      scope: "instagram_business_basic,instagram_business_content_publish",
    })}`;
  }
  const app = tiktokApp(await readDoc())!;
  return `https://www.tiktok.com/v2/auth/authorize/?${new URLSearchParams({
    client_key: app.key, redirect_uri, state, response_type: "code", scope: "user.info.basic,video.publish", disable_auto_auth: "1",
  })}`;
}

async function json<T>(res: Response, what: string): Promise<T> {
  const data = (await res.json().catch(() => ({}))) as T & { error?: unknown; error_message?: string };
  if (!res.ok || (data as { error?: unknown }).error) {
    const err = data as { error?: { message?: string } | string; error_message?: string; error_description?: string };
    const msg = typeof err.error === "object" ? err.error?.message : err.error_description || err.error_message || err.error;
    throw new Error(`${what}: ${msg || res.status}`);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Callbacks: code → tokens → GitHub secrets
// ---------------------------------------------------------------------------
export type CallbackResult = { done: true; name: string } | { done: false; pick: true };

export async function completeConnect(p: Provider, code: string, origin: string): Promise<CallbackResult> {
  const redirect_uri = redirectUri(origin, p);
  const doc = await readDoc();
  const now = new Date().toISOString();

  if (p === "facebook") {
    const app = metaApp(doc)!;
    const short = await json<{ access_token: string }>(await fetch(`${GRAPH}/oauth/access_token?${new URLSearchParams({
      client_id: app.id, client_secret: app.secret, redirect_uri, code,
    })}`), "แลก code ไม่สำเร็จ");
    const long = await json<{ access_token: string }>(await fetch(`${GRAPH}/oauth/access_token?${new URLSearchParams({
      grant_type: "fb_exchange_token", client_id: app.id, client_secret: app.secret, fb_exchange_token: short.access_token,
    })}`), "ขอ token ระยะยาวไม่สำเร็จ");
    // Page tokens fetched with a long-lived user token do not expire.
    const pages = await json<{ data: PendingPage[] }>(await fetch(`${GRAPH}/me/accounts?${new URLSearchParams({
      access_token: long.access_token, fields: "id,name,access_token", limit: "100",
    })}`), "อ่านรายชื่อเพจไม่สำเร็จ");
    const list = pages.data.map((x) => ({ id: x.id, name: x.name, token: (x as unknown as { access_token: string }).access_token }));
    if (!list.length) {
      // Facebook Login for Business can leave /me/accounts empty; the pages the user picked are
      // listed as target_ids on the granted scopes instead.
      const dbg = await json<{ data: { granular_scopes?: { scope: string; target_ids?: string[] }[] } }>(
        await fetch(`${GRAPH}/debug_token?${new URLSearchParams({
          input_token: long.access_token, access_token: `${app.id}|${app.secret}`,
        })}`), "ตรวจสิทธิ์ token ไม่สำเร็จ");
      const ids = new Set((dbg.data.granular_scopes ?? []).filter((g) => g.scope.startsWith("pages_"))
        .flatMap((g) => g.target_ids ?? []));
      for (const id of ids) {
        const page = await json<{ id: string; name: string; access_token?: string }>(await fetch(`${GRAPH}/${id}?${new URLSearchParams({
          fields: "id,name,access_token", access_token: long.access_token,
        })}`), "อ่านข้อมูลเพจไม่สำเร็จ");
        if (page.access_token) list.push({ id: page.id, name: page.name, token: page.access_token });
      }
    }
    if (!list.length) throw new Error("ไม่พบเพจ — ตอนอนุญาตต้องเลือกเพจอย่างน้อยหนึ่งเพจ");
    if (list.length === 1) {
      await channels.addFacebookPages(list);
      return { done: true, name: list[0].name };
    }
    await writeDoc({ ...doc, pending: { pages: list, until: Date.now() + 15 * 60_000 } });
    return { done: false, pick: true };
  }

  if (p === "instagram") {
    const app = igApp()!;
    const short = await json<{ access_token: string; user_id: number }>(await fetch("https://api.instagram.com/oauth/access_token", {
      method: "POST",
      body: new URLSearchParams({ client_id: app.id, client_secret: app.secret, grant_type: "authorization_code", redirect_uri, code }),
    }), "แลก code ไม่สำเร็จ");
    const long = await json<{ access_token: string; expires_in: number }>(await fetch(`${IG_GRAPH}/access_token?${new URLSearchParams({
      grant_type: "ig_exchange_token", client_secret: app.secret, access_token: short.access_token,
    })}`), "ขอ token ระยะยาวไม่สำเร็จ");
    const me = await json<{ id: string; username: string }>(await fetch(`${IG_GRAPH}/me?${new URLSearchParams({
      fields: "id,username", access_token: long.access_token,
    })}`), "อ่านบัญชี Instagram ไม่สำเร็จ");
    await gh.setSecret("INSTAGRAM_ACCESS_TOKEN", long.access_token);
    doc.accounts.instagram = {
      id: me.id, name: `@${me.username}`, connectedAt: now, token: long.access_token,
      expiresAt: new Date(Date.now() + long.expires_in * 1000).toISOString(),
    };
    await writeDoc(doc);
    return { done: true, name: `@${me.username}` };
  }

  const app = tiktokApp(doc)!;
  const tok = await json<{ access_token: string; refresh_token: string; refresh_expires_in: number; open_id: string }>(
    await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_key: app.key, client_secret: app.secret, code, grant_type: "authorization_code", redirect_uri }),
    }), "แลก code ไม่สำเร็จ");
  const info = await fetch("https://open.tiktokapis.com/v2/user/info/?fields=display_name", {
    headers: { Authorization: `Bearer ${tok.access_token}` },
  }).then((r) => r.json()).catch(() => null) as { data?: { user?: { display_name?: string } } } | null;
  const name = info?.data?.user?.display_name || "TikTok";
  await gh.setSecret("TIKTOK_REFRESH_TOKEN", tok.refresh_token);
  if (!process.env.TIKTOK_CLIENT_KEY && doc.apps?.tiktok) {
    // The pipeline needs the same app keys the token was issued to.
    await gh.setSecret("TIKTOK_CLIENT_KEY", doc.apps.tiktok.clientKey);
    await gh.setSecret("TIKTOK_CLIENT_SECRET", doc.apps.tiktok.clientSecret);
  }
  doc.accounts.tiktok = {
    id: tok.open_id, name, connectedAt: now, token: tok.refresh_token,
    expiresAt: new Date(Date.now() + tok.refresh_expires_in * 1000).toISOString(),
  };
  await writeDoc(doc);
  return { done: true, name };
}

export async function pendingPages(): Promise<{ id: string; name: string }[]> {
  const doc = await readDoc();
  if (!doc.pending || doc.pending.until < Date.now()) return [];
  return doc.pending.pages.map(({ id, name }) => ({ id, name }));
}

/** Connect the ticked pages from the last Facebook sign-in; each becomes a channel. */
export async function pickPages(ids: string[]): Promise<string[]> {
  const doc = await readDoc();
  const pages = doc.pending && doc.pending.until > Date.now() ? doc.pending.pages.filter((x) => ids.includes(x.id)) : [];
  if (!pages.length) throw new Error(doc.pending ? "เลือกอย่างน้อยหนึ่งเพจ" : "หมดเวลาเลือกเพจแล้ว — กดเชื่อมใหม่อีกครั้ง");
  await channels.addFacebookPages(pages);
  return pages.map((p) => p.name);
}

const SECRET_NAMES: Record<Provider, string[]> = {
  facebook: ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN"],
  instagram: ["INSTAGRAM_ACCESS_TOKEN"],
  tiktok: ["TIKTOK_REFRESH_TOKEN"],
};

export async function disconnect(p: Provider): Promise<void> {
  if (p === "facebook") return channels.removeAllFacebook();
  for (const name of SECRET_NAMES[p]) await gh.deleteSecret(name);
  const doc = await readDoc();
  delete doc.accounts[p];
  await writeDoc(doc);
}

export async function saveMetaSecret(appSecret: string): Promise<void> {
  const doc = await readDoc();
  await writeDoc({ ...doc, apps: { ...doc.apps, meta: { appSecret } } });
}

export async function saveTiktokApp(clientKey: string, clientSecret: string): Promise<void> {
  const doc = await readDoc();
  await writeDoc({ ...doc, apps: { ...doc.apps, tiktok: { clientKey, clientSecret } } });
}

// ---------------------------------------------------------------------------
// Daily refresh (Vercel cron): keeps Instagram's 60-day token and TikTok's
// rotating refresh token alive without anyone reconnecting.
// ---------------------------------------------------------------------------
export async function refreshTokens(): Promise<Record<string, string>> {
  const doc = await readDoc();
  const out: Record<string, string> = {};
  const ig = doc.accounts.instagram;
  if (ig?.token) {
    const left = Date.parse(ig.expiresAt ?? "") - Date.now();
    if (!(left > 45 * 86_400_000)) {
      try {
        const r = await json<{ access_token: string; expires_in: number }>(await fetch(`${IG_GRAPH}/refresh_access_token?${new URLSearchParams({
          grant_type: "ig_refresh_token", access_token: ig.token,
        })}`), "refresh");
        await gh.setSecret("INSTAGRAM_ACCESS_TOKEN", r.access_token);
        Object.assign(ig, { token: r.access_token, expiresAt: new Date(Date.now() + r.expires_in * 1000).toISOString() });
        out.instagram = "refreshed";
      } catch (e) {
        out.instagram = String(e);
      }
    } else out.instagram = "fresh";
  }
  const tt = doc.accounts.tiktok;
  const app = tiktokApp(doc);
  if (tt?.token && app) {
    try {
      const r = await json<{ refresh_token: string; refresh_expires_in: number }>(await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ client_key: app.key, client_secret: app.secret, grant_type: "refresh_token", refresh_token: tt.token }),
      }), "refresh");
      if (r.refresh_token !== tt.token) await gh.setSecret("TIKTOK_REFRESH_TOKEN", r.refresh_token);
      Object.assign(tt, { token: r.refresh_token, expiresAt: new Date(Date.now() + r.refresh_expires_in * 1000).toISOString() });
      out.tiktok = "refreshed";
    } catch (e) {
      out.tiktok = String(e);
    }
  }
  await writeDoc(doc);
  return out;
}
