import { Suspense } from "react";
import { RefreshButton } from "@/components/controls";
import {
  AttentionList, FlowPanel, FlowPanelSkeleton, HealthPanel, RecentRuns,
} from "@/components/overview";
import { Card, PageHeader, Skeleton } from "@/components/ui";
import { FLOWS } from "@/lib/flows";

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="ภาพรวม"
        subtitle="สถานะสด ทั้งสอง flow · กดรัน เปิด/ปิดตารางเวลา และดูวิดีโอล่าสุดได้จากที่นี่"
        action={<RefreshButton />}
      />

      <Suspense fallback={<Skeleton className="h-16 rounded-2xl" />}>
        <AttentionList />
      </Suspense>

      <div className="grid [&>*]:min-w-0 gap-5 xl:grid-cols-2">
        {FLOWS.map((f) => (
          <Suspense key={f.id} fallback={<FlowPanelSkeleton flowId={f.id} />}>
            <FlowPanel flowId={f.id} />
          </Suspense>
        ))}
      </div>

      <div className="grid [&>*]:min-w-0 gap-5 lg:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
        <Suspense fallback={<Card className="h-80"><Skeleton className="m-5 h-64" /></Card>}>
          <RecentRuns />
        </Suspense>
        <Suspense fallback={<Card className="h-80"><Skeleton className="m-5 h-64" /></Card>}>
          <HealthPanel />
        </Suspense>
      </div>
    </div>
  );
}
