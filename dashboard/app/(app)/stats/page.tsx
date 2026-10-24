import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Card, CardHeader, InlineError, PageHeader, Skeleton, cx } from "@/components/ui";
import { channels } from "@/lib/channels";
import { requireSession } from "@/lib/dal";
import { getVideos, settle } from "@/lib/data";
import { compact, relative, thaiDate } from "@/lib/format";
import { PLATFORM_LABEL, STAT_PLATFORMS, cutoff, summary } from "@/lib/stats";
import { storeConfigured } from "@/lib/store";

export const metadata: Metadata = { title: "สถิติ" };

const RANGES = [
  { key: "7", label: "7 วัน" },
  { key: "30", label: "30 วัน" },
  { key: "all", label: "ทั้งหมด" },
] as const;

export default function StatsPage({ searchParams }: PageProps<"/stats">) {
  return (
    <div className="space-y-6">
      <PageHeader title="สถิติ" subtitle="ยอดวิวและการมีส่วนร่วมของคลิปเล่าเรื่อง · อัปเดตทุก 6 ชั่วโมง · AI ใช้ข้อมูลนี้เลือกหัวข้อถัดไป" />
      <Suspense fallback={<Skeleton className="h-96 rounded-2xl" />}>
        <StatsContent searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function StatsContent({ searchParams }: { searchParams: PageProps<"/stats">["searchParams"] }) {
  await requireSession();
  const sp = await searchParams;
  const range = RANGES.find((r) => r.key === sp.range)?.key ?? "30";
  const channel = typeof sp.channel === "string" ? sp.channel : "";
  const [res, ch] = await Promise.all([getVideos(), storeConfigured() ? settle(channels()) : null]);
  if (!res.ok) return <InlineError title="โหลดข้อมูลไม่สำเร็จ" detail={res.error} />;
  const pages = ch?.ok ? ch.value.channels : [];
  const primaryId = ch?.ok ? ch.value.primaryId : "";

  const since = cutoff(range);
  const rows = res.value
    .filter((v) => v.flow === "story" && v.stats && Date.parse(v.createdAt) >= since)
    .filter((v) => !channel || (v.channelId || primaryId) === channel)
    .map((v) => ({ v, ...summary(v) }))
    .sort((a, b) => b.views - a.views);

  const totals = STAT_PLATFORMS.map((k) => ({
    k, views: rows.reduce((t, r) => t + r.p[k].views, 0), reactions: rows.reduce((t, r) => t + r.p[k].reactions, 0),
  }));
  const allViews = rows.reduce((t, r) => t + r.views, 0);
  const allReactions = rows.reduce((t, r) => t + r.reactions, 0);
  const href = (q: { range?: string; channel?: string }) => {
    const p = new URLSearchParams({ range: q.range ?? range, ...(q.channel ?? channel ? { channel: q.channel ?? channel } : {}) });
    return `/stats?${p}`;
  };
  const chip = (active: boolean) => cx(
    "rounded-full border px-3 py-1 text-xs",
    active ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink-2 hover:border-line-strong",
  );

  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        {RANGES.map((r) => <Link key={r.key} href={href({ range: r.key })} className={chip(r.key === range)}>{r.label}</Link>)}
        {pages.length > 1 && (
          <>
            <span className="mx-1 h-4 w-px bg-line" />
            <Link href={href({ channel: "" })} className={chip(!channel)}>ทุกเพจ</Link>
            {pages.map((c) => <Link key={c.id} href={href({ channel: c.id })} className={chip(channel === c.id)}>{c.name}</Link>)}
          </>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Total label="รวมทุกช่องทาง" views={allViews} reactions={allReactions} note={`${rows.length} คลิป`} />
        {totals.map((t) => <Total key={t.k} label={PLATFORM_LABEL[t.k]} views={t.views} reactions={t.reactions} />)}
      </div>

      <Card>
        <CardHeader eyebrow="เรียงตามยอดวิวรวม" title="คลิปที่คนดูมากที่สุด" />
        {rows.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-ink-3">ยังไม่มีสถิติในช่วงนี้ — ระบบดึงตัวเลขจากแต่ละแพลตฟอร์มทุก 6 ชั่วโมงหลังโพสต์</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-y border-line text-left text-xs text-ink-3">
                  <th className="py-2 pl-5 font-medium">#</th>
                  <th className="py-2 font-medium">คลิป</th>
                  {STAT_PLATFORMS.map((k) => <th key={k} className="py-2 text-right font-medium">{PLATFORM_LABEL[k]}</th>)}
                  <th className="py-2 text-right font-medium">วิวรวม</th>
                  <th className="py-2 pr-5 text-right font-medium">มีส่วนร่วม</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r, i) => (
                  <tr key={r.v.id}>
                    <td className="py-2.5 pl-5 tabular text-ink-3">{i + 1}</td>
                    <td className="max-w-[320px] py-2.5">
                      <Link href={`/review?status=all#v-${r.v.id}`} className="line-clamp-1 font-medium text-ink hover:underline">{r.v.title}</Link>
                      <div className="text-xs text-ink-3">{thaiDate(r.v.createdAt)} · อัปเดต {relative(r.v.stats!.updatedAt)}</div>
                    </td>
                    {STAT_PLATFORMS.map((k) => (
                      <td key={k} className="py-2.5 text-right tabular text-ink-2">{r.p[k].views ? compact(r.p[k].views) : "—"}</td>
                    ))}
                    <td className="py-2.5 text-right font-medium tabular text-ink">{compact(r.views)}</td>
                    <td className="py-2.5 pr-5 text-right tabular text-ink-2">{r.views ? `${(r.rate * 100).toFixed(1)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="px-5 pt-2 pb-4 text-xs text-ink-3">
          มีส่วนร่วม = (ถูกใจ + คอมเมนต์ + แชร์ + บันทึก) ÷ วิว · TikTok ยังไม่มีสถิติจนกว่าแอปจะผ่านการอนุมัติ
        </p>
      </Card>
    </>
  );
}

function Total({ label, views, reactions, note }: { label: string; views: number; reactions: number; note?: string }) {
  return (
    <Card className="p-5">
      <div className="text-sm text-ink-2">{label}</div>
      <div className="mt-2 font-display text-3xl font-semibold tabular text-ink">{compact(views)}</div>
      <div className="mt-1 text-xs text-ink-3">
        วิว · ❤ {compact(reactions)}{views ? ` · ${((reactions / views) * 100).toFixed(1)}%` : ""}{note ? ` · ${note}` : ""}
      </div>
    </Card>
  );
}
