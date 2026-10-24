import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Download, ExternalLink, FileX } from "lucide-react";
import { CopyButton, ReviewActions } from "@/components/review-controls";
import { Card, FlowTag, InlineError, PageHeader, Pill, Skeleton, cx, type Tone } from "@/components/ui";
import { requireSession } from "@/lib/dal";
import { getVideos } from "@/lib/data";
import { bytes, number, relative, thaiDateTime } from "@/lib/format";
import { VIDEO_RETENTION_DAYS, type Video, type VideoStatus } from "@/lib/store";

export const metadata: Metadata = { title: "รีวิววิดีโอ" };

const TABS: { key: VideoStatus | "all"; label: string }[] = [
  { key: "review", label: "รอตรวจ" },
  { key: "approved", label: "ผ่านแล้ว" },
  { key: "posted", label: "โพสต์แล้ว" },
  { key: "rejected", label: "ไม่ผ่าน" },
  { key: "all", label: "ทั้งหมด" },
];
const STATUS: Record<VideoStatus, { tone: Tone; label: string }> = {
  review: { tone: "warn", label: "รอตรวจ" },
  approved: { tone: "ok", label: "ผ่านแล้ว" },
  posted: { tone: "ok", label: "โพสต์แล้ว" },
  rejected: { tone: "bad", label: "ไม่ผ่าน" },
};

export default function ReviewPage({ searchParams }: PageProps<"/review">) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="รีวิววิดีโอ"
        subtitle={`ทุกคลิปที่ระบบทำเสร็จจะมาอยู่ที่นี่ (และแจ้งใน Telegram) · ไฟล์เก็บ ${VIDEO_RETENTION_DAYS} วัน`}
      />
      <Suspense fallback={<Skeleton className="h-[520px] rounded-2xl" />}>
        <ReviewContent searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function ReviewContent({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  await requireSession();
  const sp = await searchParams;
  const tab = (TABS.find((t) => t.key === sp.status)?.key ?? "review") as VideoStatus | "all";
  const res = await getVideos();
  if (!res.ok) return <InlineError title="โหลดวิดีโอไม่สำเร็จ" detail={res.error} />;
  const counts = res.value.reduce<Record<string, number>>((m, v) => ((m[v.status] = (m[v.status] ?? 0) + 1), m), {});
  const videos = tab === "all" ? res.value : res.value.filter((v) => v.status === tab);
  return (
    <>
      <div className="flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <Link
            key={t.key}
            href={`/review?status=${t.key}`}
            className={cx(
              "rounded-full border px-3 py-1 text-xs",
              tab === t.key ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink-2 hover:border-line-strong",
            )}
          >
            {t.label} <span className="tabular opacity-60">{t.key === "all" ? res.value.length : counts[t.key] ?? 0}</span>
          </Link>
        ))}
      </div>
      {videos.length === 0 ? (
        <Card className="px-6 py-14 text-center text-sm text-ink-3">
          {tab === "review" ? "ไม่มีคลิปรอตรวจ — คลิปใหม่จะเข้ามาหลังรอบโพสต์ตามเวลาที่ตั้งไว้" : "ไม่มีคลิปในสถานะนี้"}
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
          {videos.map((v) => <VideoCard key={v.id} v={v} />)}
        </div>
      )}
    </>
  );
}

function VideoCard({ v }: { v: Video }) {
  const s = STATUS[v.status];
  return (
    <div id={`v-${v.id}`} className="scroll-mt-24 rounded-2xl target:ring-2 target:ring-focus target:ring-offset-2 target:ring-offset-bg">
    <Card as="article" className="flex h-full flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-5 pt-4">
        <div className="min-w-0">
          <FlowTag flow={v.flow} />
          <h2 className="mt-1.5 line-clamp-2 font-display text-[16px] font-semibold leading-snug text-ink">{v.title || "(ไม่มีชื่อ)"}</h2>
          <p className="mt-0.5 text-xs text-ink-3" title={thaiDateTime(v.createdAt)}>
            {relative(v.createdAt)} · {v.size ? bytes(v.size) : ""}
            {v.cost && (
              <span title={`Claude ${number(v.cost.inputTokens)} token เข้า · ${number(v.cost.outputTokens)} token ออก · เสียง ${number(v.cost.ttsChars)} ตัวอักษร`}>
                {" "}· Claude ${v.cost.claudeUsd.toFixed(2)}
              </span>
            )}
            {v.runUrl && (
              <a href={v.runUrl} target="_blank" rel="noreferrer" className="ml-1 hover:text-ink">· log ↗</a>
            )}
          </p>
        </div>
        <Pill tone={s.tone}>{s.label}</Pill>
      </div>

      <div className="mx-5 mt-3 overflow-hidden rounded-xl bg-black">
        {v.pathname ? (
          <video
            controls
            playsInline
            preload="metadata"
            src={`/api/videos/${v.id}#t=0.5`}
            className="mx-auto aspect-[9/16] max-h-[520px] w-full max-w-full object-contain"
          />
        ) : (
          <div className="flex aspect-[9/16] max-h-[520px] w-full flex-col items-center justify-center gap-2 text-sm text-white/60">
            <FileX className="size-6" /> ไฟล์หมดอายุแล้ว (เก็บ {VIDEO_RETENTION_DAYS} วัน)
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 px-5 pt-4 pb-5">
        <div className="rounded-xl border border-line bg-surface-2/60">
          <div className="flex items-center justify-between border-b border-line px-3 py-1.5">
            <span className="eyebrow">แคปชันสำหรับโพสต์</span>
            <CopyButton text={v.caption} label="คัดลอกแคปชัน" />
          </div>
          <p className="max-h-40 overflow-y-auto whitespace-pre-wrap break-words px-3 py-2.5 text-sm text-ink">{v.caption}</p>
        </div>
        {v.link && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-ink-3">ลิงก์สินค้า</span>
            <a href={v.link} target="_blank" rel="noreferrer" className="min-w-0 truncate text-ink underline decoration-line-strong underline-offset-2">{v.link}</a>
            <CopyButton text={v.link} />
          </div>
        )}
        {v.sources?.length ? (
          <p className="text-xs text-ink-3">แหล่งข้อมูล: {v.sources.join(" · ")}</p>
        ) : null}
        {v.note && <p className="rounded-lg bg-bad-soft px-3 py-2 text-xs text-bad">หมายเหตุ: {v.note}</p>}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1">
          <ReviewActions id={v.id} status={v.status} />
          {v.pathname && (
            <a href={`/api/videos/${v.id}`} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink">
              <Download className="size-4" /> ดาวน์โหลด
            </a>
          )}
        </div>
        {v.flow === "shopee" && (
          <p className="flex items-center gap-1.5 text-[11px] text-ink-3">
            <ExternalLink className="size-3" /> Shopee Video ต้องอัปโหลดเองในแอป (ไม่มี API)
          </p>
        )}
      </div>
    </Card>
    </div>
  );
}
