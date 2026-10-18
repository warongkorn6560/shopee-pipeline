import type { Metadata } from "next";
import { Suspense } from "react";
import { ArrowUpRight } from "lucide-react";
import { Card, CardHeader, PageHeader, Pill, Skeleton, StateIcon, type Tone } from "@/components/ui";
import { requireSession } from "@/lib/dal";
import { number, thaiDate } from "@/lib/format";
import { elevenLabs, gatewayCredits } from "@/lib/health";
import { BILLING_LABEL, SERVICES, type Billing } from "@/lib/services";

export const metadata: Metadata = { title: "บริการ & ค่าใช้จ่าย" };

const BILLING_TONE: Record<Billing, Tone> = {
  paid: "warn", free: "ok", "no-card": "ok", unknown: "bad", optional: "idle",
};

const NEEDS = [
  {
    tone: "bad" as Tone, title: "GitHub fine-grained token", cost: "ฟรี",
    detail: "ให้ dashboard สั่งรันและแก้ตั้งค่าได้ — ทำครั้งเดียว ~2 นาที (หน้าตั้งค่ามีขั้นตอน)",
  },
  {
    tone: "warn" as Tone, title: "เชื่อมเพจ Facebook", cost: "ฟรี",
    detail: "จำเป็นเฉพาะถ้าจะให้ Flow B โพสต์ Reels เอง · โหมดตรวจก่อนใช้ Telegram ได้เลย",
  },
  {
    tone: "idle" as Tone, title: "เติมเครดิต AI Gateway (ไม่บังคับ)", cost: "≈ $0.04 / ภาพ",
    detail: "เปิดภาพประกอบ AI ใน Flow B (~4 ภาพ/คลิป ≈ $5/เดือน ถ้ารันทุกวัน) — ตอนนี้ใช้แผนที่จริงจาก Wikimedia ฟรี",
  },
  {
    tone: "idle" as Tone, title: "TikTok app audit (ไม่บังคับ)", cost: "ฟรี",
    detail: "ต้องผ่านก่อน TikTok จะยอมให้โพสต์สาธารณะผ่าน API · ใช้เวลา 2–6 สัปดาห์",
  },
];

export default function ServicesPage() {
  const paid = SERVICES.filter((s) => s.billing === "paid");
  const unknown = SERVICES.filter((s) => s.billing === "unknown");
  return (
    <div className="space-y-6">
      <PageHeader title="บริการ & ค่าใช้จ่าย" subtitle="ทุกบริการที่ระบบแตะ จ่ายอยู่หรือไม่ และตรวจล่าสุดเมื่อไร" />

      <div className="grid gap-4 sm:grid-cols-3">
        <Summary tone="warn" big={String(paid.length)} label="บริการที่จ่ายเงินอยู่" note={paid.map((s) => s.name).join(" · ")} />
        <Summary tone="bad" big={String(unknown.length)} label="ต้องเข้าไปตรวจเอง" note={unknown.map((s) => s.name).join(" · ") || "—"} />
        <Summary tone="ok" big="$0" label="ค่าใช้จ่ายเพิ่มต่อคลิป" note="ทั้งสอง flow ใช้ของที่จ่ายแล้วหรือของฟรี" />
      </div>

      <Card>
        <CardHeader eyebrow={`${SERVICES.length} บริการ`} title="รายการทั้งหมด" />
        <Suspense fallback={<Skeleton className="m-5 h-96" />}>
          <ServiceList />
        </Suspense>
      </Card>

      <Card>
        <CardHeader eyebrow="ไม่มีรายการไหนต้องจ่ายเงิน" title="สิ่งที่ยังต้องเพิ่ม" />
        <ul className="mt-3 divide-y divide-line">
          {NEEDS.map((n) => (
            <li key={n.title} className="flex items-start gap-3 px-5 py-3.5">
              <StateIcon tone={n.tone} className="mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink">{n.title}</div>
                <div className="text-sm text-ink-2">{n.detail}</div>
              </div>
              <span className="shrink-0 text-sm font-medium text-ink">{n.cost}</span>
            </li>
          ))}
        </ul>
        <div className="h-2" />
      </Card>
    </div>
  );
}

function Summary({ tone, big, label, note }: { tone: Tone; big: string; label: string; note: string }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 text-sm text-ink-2"><StateIcon tone={tone} />{label}</div>
      <div className="mt-2 font-display text-4xl font-semibold text-ink tabular">{big}</div>
      <div className="mt-1 text-xs text-ink-3">{note}</div>
    </Card>
  );
}

async function ServiceList() {
  await requireSession();
  const [eleven, gateway] = await Promise.all([elevenLabs(), gatewayCredits()]);
  const liveNote: Record<string, string | undefined> = {
    elevenlabs: eleven.ok ? `ใช้ไป ${number(eleven.data!.used)} / ${number(eleven.data!.limit)} ตัวอักษร · รีเซ็ต ${thaiDate(eleven.data!.resetAt)}` : undefined,
    gateway: gateway.ok ? `เครดิตคงเหลือ $${gateway.data!.balance.toFixed(2)}` : undefined,
  };
  return (
    <ul className="mt-3 divide-y divide-line">
      {SERVICES.map((s) => (
        <li key={s.name} className="grid gap-x-4 gap-y-1.5 px-5 py-4 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1.6fr)_auto]">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-ink">{s.name}</span>
              {s.url && (
                <a href={s.url} target="_blank" rel="noreferrer" aria-label={`เปิด ${s.name}`} className="text-ink-3 hover:text-ink">
                  <ArrowUpRight className="size-3.5" />
                </a>
              )}
            </div>
            <div className="text-xs text-ink-3">{s.role}</div>
          </div>
          <div className="min-w-0 text-sm">
            <div className="text-ink">{s.cost}{s.renews && <span className="text-ink-3"> · ต่ออายุ {thaiDate(s.renews)}</span>}</div>
            {s.live && liveNote[s.live] && <div className="text-xs text-ok">สด: {liveNote[s.live]}</div>}
            <div className="text-xs text-ink-2">{s.decision}</div>
          </div>
          <div className="flex items-start gap-2 md:flex-col md:items-end">
            <Pill tone={BILLING_TONE[s.billing]}>{BILLING_LABEL[s.billing]}</Pill>
            <span className="text-[11px] text-ink-3">ตรวจ {thaiDate(s.checked)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
