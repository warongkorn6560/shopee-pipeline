import { NextResponse, type NextRequest } from "next/server";
import { refreshTokens } from "@/lib/social";

// Vercel cron (vercel.json) — authenticated with CRON_SECRET.
export async function GET(request: NextRequest) {
  const secret = process.env.CRON_SECRET;
  if (!secret || request.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  return NextResponse.json(await refreshTokens());
}
