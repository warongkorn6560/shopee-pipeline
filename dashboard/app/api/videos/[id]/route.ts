import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { SESSION_COOKIE, verifySessionValue } from "@/lib/session";
import { list, presignedPlayback } from "@/lib/store";

// Signed-in viewers get a short-lived presigned URL to the private MP4, so the
// browser streams (and seeks) straight from Blob storage.
export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await verifySessionValue((await cookies()).get(SESSION_COOKIE)?.value))) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const video = (await list("videos")).find((v) => v.id === id);
  if (!video?.pathname) return NextResponse.json({ error: "video not available" }, { status: 404 });
  return NextResponse.redirect(await presignedPlayback(video.pathname), {
    headers: { "Cache-Control": "private, max-age=600" },
  });
}
