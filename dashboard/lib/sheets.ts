import "server-only";
import { createSign } from "node:crypto";

// Inbox  : A Date | B Name | C Price | D Commission | E Sales | F Affiliate URL | G Niche
//          H Status | I Notes | J Image URL | K TikTok | L Instagram | M Shopee Video
// Stories: A Date | B Topic | C Angle | D Status | E Title | F Run | G Published | H Log

export interface Product {
  row: number;
  date: string;
  name: string;
  price: string;
  commission: string;
  sales: string;
  url: string;
  status: string;
  notes: string;
  image: string;
  tiktok: string;
  instagram: string;
}

export interface Story {
  row: number;
  date: string;
  topic: string;
  angle: string;
  status: string;
  title: string;
  run: string;
  published: string;
  log: string;
}

export function sheetsConfigured(): boolean {
  return Boolean(process.env.GOOGLE_SHEET_ID && process.env.GOOGLE_SERVICE_ACCOUNT_JSON);
}

let cached: { token: string; exp: number } | null = null;

async function token(): Promise<string> {
  if (cached && cached.exp > Date.now() + 60_000) return cached.token;
  const sa = JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_JSON!) as {
    client_email: string; private_key: string; token_uri?: string;
  };
  const now = Math.floor(Date.now() / 1000);
  const enc = (o: object) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const unsigned = `${enc({ alg: "RS256", typ: "JWT" })}.${enc({
    iss: sa.client_email,
    scope: "https://www.googleapis.com/auth/spreadsheets",
    aud: sa.token_uri ?? "https://oauth2.googleapis.com/token",
    iat: now,
    exp: now + 3600,
  })}`;
  const signature = createSign("RSA-SHA256").update(unsigned).sign(sa.private_key, "base64url");
  const res = await fetch(sa.token_uri ?? "https://oauth2.googleapis.com/token", {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion: `${unsigned}.${signature}`,
    }),
  });
  if (!res.ok) throw new Error(`Google auth failed (${res.status})`);
  const data = (await res.json()) as { access_token: string; expires_in: number };
  cached = { token: data.access_token, exp: Date.now() + data.expires_in * 1000 };
  return cached.token;
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const id = process.env.GOOGLE_SHEET_ID!;
  const res = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${id}${path}`, {
    ...init,
    cache: "no-store",
    headers: { Authorization: `Bearer ${await token()}`, "Content-Type": "application/json", ...init.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Sheets ${res.status}: ${body.slice(0, 160)}`);
  }
  return (await res.json()) as T;
}

async function values(range: string): Promise<string[][]> {
  const data = await api<{ values?: string[][] }>(`/values/${encodeURIComponent(range)}`);
  return data.values ?? [];
}

const cell = (r: string[], i: number) => (r[i] ?? "").trim();

export async function getProducts(): Promise<Product[]> {
  const rows = await values("Inbox!A2:M");
  return rows
    .map((r, i) => ({
      row: i + 2, date: cell(r, 0), name: cell(r, 1), price: cell(r, 2), commission: cell(r, 3),
      sales: cell(r, 4), url: cell(r, 5), status: cell(r, 7) || "New", notes: cell(r, 8),
      image: cell(r, 9), tiktok: cell(r, 10), instagram: cell(r, 11),
    }))
    .filter((p) => p.name);
}

export async function storiesTabExists(): Promise<boolean> {
  const meta = await api<{ sheets: { properties: { title: string } }[] }>("?fields=sheets.properties.title");
  return meta.sheets.some((s) => s.properties.title === "Stories");
}

export async function getStories(): Promise<Story[] | null> {
  if (!(await storiesTabExists())) return null;
  const rows = await values("Stories!A2:H");
  return rows
    .map((r, i) => ({
      row: i + 2, date: cell(r, 0), topic: cell(r, 1), angle: cell(r, 2), status: cell(r, 3) || "Ready",
      title: cell(r, 4), run: cell(r, 5), published: cell(r, 6), log: cell(r, 7),
    }))
    .filter((s) => s.topic);
}

export async function setStatus(tab: "Inbox" | "Stories", row: number, status: string): Promise<void> {
  const col = tab === "Inbox" ? "H" : "D";
  await api(`/values/${encodeURIComponent(`${tab}!${col}${row}`)}?valueInputOption=RAW`, {
    method: "PUT",
    body: JSON.stringify({ values: [[status]] }),
  });
}

async function append(range: string, row: string[]): Promise<void> {
  await api(`/values/${encodeURIComponent(range)}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, {
    method: "POST",
    body: JSON.stringify({ values: [row] }),
  });
}

const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Bangkok" });

export async function addProduct(p: { name: string; price: string; url: string; image: string; notes: string }) {
  await append("Inbox!A:J", [today(), p.name, p.price, "", "", p.url, "", "Ready", p.notes, p.image]);
}

export async function addStory(topic: string, angle: string): Promise<void> {
  if (!(await storiesTabExists())) {
    await api(":batchUpdate", {
      method: "POST",
      body: JSON.stringify({
        requests: [{ addSheet: { properties: { title: "Stories", gridProperties: { frozenRowCount: 1 } } } }],
      }),
    });
    await api(`/values/${encodeURIComponent("Stories!A1")}?valueInputOption=RAW`, {
      method: "PUT",
      body: JSON.stringify({
        values: [["Date", "Topic", "Angle / Notes", "Status", "Title", "Run", "Published", "Log"]],
      }),
    });
  }
  await append("Stories!A:H", [today(), topic, angle, "Ready", "", "", "", ""]);
}

export function sheetUrl(): string | null {
  const id = process.env.GOOGLE_SHEET_ID;
  return id ? `https://docs.google.com/spreadsheets/d/${id}/edit` : null;
}
