import { NextResponse, type NextRequest } from "next/server";
import { PROVIDERS, completeConnect, type Provider } from "@/lib/social";

// Step 2: the provider sends the user back with ?code=…&state=…
export async function GET(request: NextRequest, ctx: { params: Promise<{ provider: string }> }) {
  const { provider } = await ctx.params;
  const back = new URL("/settings", request.url);
  back.hash = "social";
  const p = provider as Provider;
  const q = request.nextUrl.searchParams;
  const expected = request.cookies.get(`oauth_${p}`)?.value;
  const fail = (msg: string) => {
    console.error(`[connect:${provider}] ${msg}`);
    back.searchParams.set("social_error", msg);
    return NextResponse.redirect(back);
  };
  if (!PROVIDERS.includes(p)) return fail("ไม่รู้จักบริการนี้");
  if (q.get("error")) return fail(`ยกเลิกหรือถูกปฏิเสธ: ${q.get("error_description") || q.get("error")}`);
  const code = q.get("code");
  if (!code || !expected || q.get("state") !== expected) return fail("ลิงก์เชื่อมหมดอายุ — กดเชื่อมใหม่อีกครั้ง");
  try {
    const result = await completeConnect(p, code, request.nextUrl.origin);
    const res = result.done
      ? NextResponse.redirect(Object.assign(back, { search: `?connected=${p}&name=${encodeURIComponent(result.name)}` }))
      : NextResponse.redirect(new URL("/settings/pick-page", request.url));
    res.cookies.delete({ name: `oauth_${p}`, path: "/api/connect" });
    return res;
  } catch (e) {
    return fail(e instanceof Error ? e.message.slice(0, 200) : "เชื่อมไม่สำเร็จ");
  }
}
