import { NextResponse, type NextRequest } from "next/server";
import { PROVIDERS, appReady, authUrl, readDoc, type Provider } from "@/lib/social";

// Step 1 of a connect: remember a random state in a short cookie, send the user to the provider.
export async function GET(request: NextRequest, ctx: { params: Promise<{ provider: string }> }) {
  const { provider } = await ctx.params;
  const back = new URL("/settings#social", request.url);
  if (!PROVIDERS.includes(provider as Provider)) return NextResponse.redirect(back);
  const p = provider as Provider;
  if (!appReady(p, await readDoc())) {
    back.searchParams.set("social_error", p === "tiktok" ? "ใส่ Client key / secret ของแอป TikTok ก่อน" : p === "youtube" ? "ใส่ Google OAuth Client ID / secret ก่อน" : "ยังไม่ได้ตั้ง META_APP_ID / META_APP_SECRET");
    return NextResponse.redirect(back);
  }
  const state = crypto.randomUUID();
  const res = NextResponse.redirect(await authUrl(p, request.nextUrl.origin, state));
  res.cookies.set(`oauth_${p}`, state, { httpOnly: true, secure: true, sameSite: "lax", maxAge: 600, path: "/api/connect" });
  return res;
}
