import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE, verifySessionValue } from "./lib/session";

export async function proxy(request: NextRequest) {
  const ok = await verifySessionValue(request.cookies.get(SESSION_COOKIE)?.value);
  if (ok) return NextResponse.next();
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  // /api/pipeline authenticates with PIPELINE_API_KEY and /api/cron with CRON_SECRET inside the route.
  matcher: ["/((?!login|about|privacy|terms|brand/|api/pipeline|api/telegram|api/cron|_next/static|_next/image|icon.svg|favicon.ico|robots.txt|tiktok[A-Za-z0-9]*\\.txt).*)"],
};
