import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { artifactDownloadUrl } from "@/lib/github";
import { SESSION_COOKIE, verifySessionValue } from "@/lib/session";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await verifySessionValue((await cookies()).get(SESSION_COOKIE)?.value))) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  if (!/^\d+$/.test(id)) return NextResponse.json({ error: "bad id" }, { status: 400 });
  const url = await artifactDownloadUrl(Number(id));
  if (!url) return NextResponse.json({ error: "artifact not available" }, { status: 404 });
  return NextResponse.redirect(url);
}
