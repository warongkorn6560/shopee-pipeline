// Signed session cookie: "<expiresAtMs>.<base64url HMAC-SHA256>".
// Web Crypto only, so the same code runs in proxy.ts and in server actions.

export const SESSION_COOKIE = "pc_session";
export const SESSION_TTL_MS = 14 * 24 * 60 * 60 * 1000;

const enc = new TextEncoder();

function b64url(buf: ArrayBuffer): string {
  let s = "";
  for (const b of new Uint8Array(buf)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function hmac(secret: string, data: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function authConfigured(): boolean {
  return Boolean(process.env.DASHBOARD_PASSWORD && (process.env.SESSION_SECRET?.length ?? 0) >= 32);
}

export async function createSessionValue(): Promise<string> {
  const exp = String(Date.now() + SESSION_TTL_MS);
  return `${exp}.${await hmac(process.env.SESSION_SECRET!, `v1.${exp}`)}`;
}

export async function verifySessionValue(value: string | undefined): Promise<boolean> {
  if (!value || !authConfigured()) return false;
  const [exp, sig] = value.split(".");
  if (!exp || !sig || Number(exp) < Date.now()) return false;
  return safeEqual(sig, await hmac(process.env.SESSION_SECRET!, `v1.${exp}`));
}

export async function passwordMatches(input: string): Promise<boolean> {
  const expected = process.env.DASHBOARD_PASSWORD ?? "";
  if (!expected) return false;
  // Compare HMACs so the comparison is constant-time regardless of length.
  const secret = process.env.SESSION_SECRET ?? "";
  return safeEqual(await hmac(secret, input), await hmac(secret, expected));
}
