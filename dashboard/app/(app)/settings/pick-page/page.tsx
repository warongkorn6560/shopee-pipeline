import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { PagePicker } from "@/components/social-card";
import { Card, CardHeader, PageHeader, Skeleton, btn, cx } from "@/components/ui";
import { requireSession } from "@/lib/dal";
import { channels } from "@/lib/channels";
import { pendingPages } from "@/lib/social";

export const metadata: Metadata = { title: "เลือกเพจ Facebook" };

export default function PickPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="เลือกเพจ Facebook" subtitle="ติ๊กเพจที่จะให้ Flow B โพสต์ Reels — แต่ละเพจตั้งธีม ชื่อซีรีส์ และโหมดโพสต์แยกกันได้ในแท็บ เพจ & โซเชียล" />
      <Suspense fallback={<Skeleton className="h-48 rounded-2xl" />}>
        <Pages />
      </Suspense>
    </div>
  );
}

async function Pages() {
  await requireSession();
  const [pages, current] = await Promise.all([pendingPages(), channels()]);
  return (
    <Card>
      <CardHeader eyebrow="ต้องเลือกภายใน 15 นาที" title={pages.length ? `${pages.length} เพจ` : "หมดเวลาแล้ว"} />
      {pages.length ? (
        <div className="mt-3"><PagePicker pages={pages} connected={current.channels.map((c) => c.pageId)} /></div>
      ) : (
        <div className="px-5 py-4">
          <Link href="/settings#channels" className={cx(btn.base, btn.secondary)}>กลับไปกดเชื่อมใหม่</Link>
        </div>
      )}
      <div className="h-2" />
    </Card>
  );
}
