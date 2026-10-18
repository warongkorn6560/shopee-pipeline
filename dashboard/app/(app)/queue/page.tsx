import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { ArrowUpRight, ImageOff } from "lucide-react";
import { AddProductForm, AddStoryForm, QuickStory, StatusButtons } from "@/components/queue-controls";
import { Card, CardHeader, InlineError, PageHeader, Pill, Skeleton, cx, type Tone } from "@/components/ui";
import { requireSession } from "@/lib/dal";
import { getProducts, getStories } from "@/lib/data";
import { githubConfigured } from "@/lib/github";
import { sheetUrl, sheetsConfigured, type Product, type Story } from "@/lib/sheets";

export const metadata: Metadata = { title: "คิวงาน" };

const STATUS_TONE: Record<string, Tone> = {
  Ready: "ok", New: "idle", Posted: "ok", Done: "ok", Failed: "bad", Hold: "warn", Producing: "live",
};
const STATUS_TH: Record<string, string> = {
  Ready: "รอผลิต", New: "ใหม่", Posted: "โพสต์แล้ว", Done: "ส่งตรวจแล้ว", Failed: "ล้มเหลว", Hold: "พักไว้", Producing: "กำลังผลิต",
};

export default function QueuePage({ searchParams }: PageProps<"/queue">) {
  return (
    <div className="space-y-6">
      <PageHeader title="คิวงาน" subtitle="สิ่งที่ pipeline จะหยิบไปทำต่อ — อ่านและเขียนตรงกับ Google Sheet" />
      <Suspense fallback={<Skeleton className="h-96 rounded-2xl" />}>
        <QueueContent searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

type SP = Promise<Record<string, string | string[] | undefined>>;

async function QueueContent({ searchParams }: { searchParams: SP }) {
  await requireSession();
  const sp = await searchParams;
  const tab = sp.tab === "stories" ? "stories" : "products";
  const status = typeof sp.status === "string" ? sp.status : "Ready";
  if (!sheetsConfigured()) {
    return (
      <Card className="p-6 text-sm text-ink-2">
        เพิ่ม <code className="font-mono text-ink">GOOGLE_SHEET_ID</code> และ <code className="font-mono text-ink">GOOGLE_SERVICE_ACCOUNT_JSON</code> ใน Vercel เพื่อจัดการคิวจากหน้านี้
      </Card>
    );
  }
  const sheet = sheetUrl();
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" className="inline-flex rounded-xl border border-line bg-surface p-1">
          <TabLink href="/queue?tab=products" active={tab === "products"} label="สินค้า" tag="Flow A" />
          <TabLink href="/queue?tab=stories" active={tab === "stories"} label="หัวข้อเรื่องเล่า" tag="Flow B" />
        </div>
        {sheet && (
          <a href={sheet} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
            เปิด Google Sheet <ArrowUpRight className="size-3.5" />
          </a>
        )}
      </div>
      {tab === "products" ? <Products status={status} /> : <Stories status={status} />}
    </>
  );
}

function TabLink({ href, active, label, tag }: { href: string; active: boolean; label: string; tag: string }) {
  return (
    <Link
      href={href}
      role="tab"
      aria-selected={active}
      className={cx("flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm", active ? "bg-ink text-surface" : "text-ink-2 hover:text-ink")}
    >
      {label}
      <span className={cx("font-display text-[10px] font-semibold uppercase tracking-wide", active ? "text-surface/60" : "text-ink-3")}>{tag}</span>
    </Link>
  );
}

function Filters({ base, counts, current }: { base: string; counts: Record<string, number>; current: string }) {
  const keys = ["Ready", ...Object.keys(counts).filter((k) => k !== "Ready").sort(), "all"];
  return (
    <div className="flex flex-wrap gap-1.5">
      {keys.map((k) => (
        <Link
          key={k}
          href={`${base}&status=${k}`}
          className={cx(
            "rounded-full border px-3 py-1 text-xs",
            current === k ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink-2 hover:border-line-strong",
          )}
        >
          {k === "all" ? "ทั้งหมด" : STATUS_TH[k] ?? k}{" "}
          <span className="tabular opacity-60">{k === "all" ? Object.values(counts).reduce((a, b) => a + b, 0) : counts[k] ?? 0}</span>
        </Link>
      ))}
    </div>
  );
}

function countBy<T extends { status: string }>(rows: T[]) {
  return rows.reduce<Record<string, number>>((m, r) => ((m[r.status] = (m[r.status] ?? 0) + 1), m), {});
}

async function Products({ status }: { status: string }) {
  const res = await getProducts();
  if (!res.ok) return <InlineError title="โหลดสินค้าไม่สำเร็จ" detail={res.error} />;
  const all = res.value;
  const nextRow = all.find((p) => p.status === "Ready")?.row;
  const rows = status === "all" ? all : all.filter((p) => p.status === status);
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Card>
        <CardHeader eyebrow="Inbox" title="สินค้า" action={<Filters base="/queue?tab=products" counts={countBy(all)} current={status} />} />
        <p className="px-5 pt-2 text-xs text-ink-3">pipeline หยิบแถว “รอผลิต” ที่อยู่บนสุดก่อน · สินค้าจาก scraper เข้ามาเป็น “ใหม่” — กด “เข้าคิว” เพื่ออนุมัติ</p>
        <ul className="mt-3 divide-y divide-line">
          {rows.slice(0, 80).map((p) => <ProductRow key={p.row} p={p} next={p.row === nextRow} />)}
          {rows.length === 0 && <li className="px-5 py-8 text-center text-sm text-ink-3">ไม่มีรายการในสถานะนี้</li>}
        </ul>
        {rows.length > 80 && <p className="px-5 py-3 text-xs text-ink-3">แสดง 80 จาก {rows.length} รายการ</p>}
        <div className="h-2" />
      </Card>
      <Card className="h-fit">
        <CardHeader eyebrow="ใส่เอง" title="เพิ่มสินค้า" />
        <div className="px-5 pt-4 pb-5"><AddProductForm /></div>
      </Card>
    </div>
  );
}

function ProductRow({ p, next }: { p: Product; next: boolean }) {
  return (
    <li className="flex items-center gap-3 px-5 py-3">
      <div className="relative size-12 shrink-0 overflow-hidden rounded-lg border border-line bg-surface-2">
        {p.image.startsWith("http") ? (
          <Image src={p.image} alt="" fill sizes="48px" unoptimized className="object-cover" />
        ) : (
          <ImageOff className="absolute inset-0 m-auto size-4 text-ink-3" aria-label="ไม่มีรูป" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {next && <Pill tone="live" className="!py-0 text-[10px]">คิวถัดไป</Pill>}
          <span className="truncate text-sm font-medium text-ink" title={p.name}>{p.name}</span>
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-ink-3">
          {p.price && <span className="tabular">฿{p.price}</span>}
          {p.commission && <span>คอม {p.commission}%</span>}
          <span className="font-mono">แถว {p.row}</span>
          {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="hover:text-ink">ลิงก์ ↗</a>}
          {p.status === "Failed" && p.notes && <span className="truncate text-bad" title={p.notes}>{p.notes}</span>}
        </div>
      </div>
      <Pill tone={STATUS_TONE[p.status] ?? "idle"} className="hidden sm:inline-flex">{STATUS_TH[p.status] ?? p.status}</Pill>
      <StatusButtons tab="Inbox" row={p.row} status={p.status} />
    </li>
  );
}

async function Stories({ status }: { status: string }) {
  const res = await getStories();
  if (!res.ok) return <InlineError title="โหลดหัวข้อไม่สำเร็จ" detail={res.error} />;
  const all = res.value ?? [];
  const nextRow = all.find((s) => s.status === "Ready")?.row;
  const rows = status === "all" ? all : all.filter((s) => s.status === status);
  const canRun = githubConfigured();
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader eyebrow="ใส่เอง" title="เพิ่มหัวข้อ" />
        <div className="px-5 pt-4 pb-5"><AddStoryForm /></div>
      </Card>
      <Card>
        <CardHeader eyebrow="Stories" title="หัวข้อเรื่องเล่า" action={<Filters base="/queue?tab=stories" counts={countBy(all)} current={status} />} />
        {res.value === null ? (
          <p className="px-5 pt-3 pb-6 text-sm text-ink-2">
            ยังไม่มีแท็บ Stories — จะถูกสร้างพร้อมหัวข้อตั้งต้น 6 เรื่องเมื่อ Flow B รันครั้งแรก หรือเพิ่มหัวข้อด้านบนได้เลย
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {rows.map((s) => <StoryRow key={s.row} s={s} next={s.row === nextRow} canRun={canRun} />)}
            {rows.length === 0 && (
              <li className="px-5 py-8 text-center text-sm text-ink-3">
                ไม่มีรายการในสถานะนี้{status === "Ready" && " — ถ้าเปิด “AI คิดหัวข้อเอง” ไว้ ระบบจะเสนอหัวข้อใหม่ให้"}
              </li>
            )}
          </ul>
        )}
        <div className="h-2" />
      </Card>
    </div>
  );
}

function StoryRow({ s, next, canRun }: { s: Story; next: boolean; canRun: boolean }) {
  return (
    <li className="flex flex-wrap items-center gap-3 px-5 py-3 sm:flex-nowrap">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {next && <Pill tone="live" className="!py-0 text-[10px]">คิวถัดไป</Pill>}
          <span className="text-sm font-medium text-ink">{s.topic}</span>
        </div>
        <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-ink-3">
          {s.angle && <span className="truncate">{s.angle}</span>}
          {s.title && <span>คลิป: “{s.title}”</span>}
          {s.published && <span>{s.published}</span>}
          {s.run.startsWith("http") && <a href={s.run} target="_blank" rel="noreferrer" className="hover:text-ink">log ↗</a>}
          {s.status === "Failed" && s.log && <span className="truncate text-bad" title={s.log}>{s.log}</span>}
        </div>
      </div>
      <Pill tone={STATUS_TONE[s.status] ?? "idle"}>{STATUS_TH[s.status] ?? s.status}</Pill>
      <div className="flex items-center gap-1">
        {canRun && <QuickStory topic={s.topic} />}
        <StatusButtons tab="Stories" row={s.row} status={s.status} />
      </div>
    </li>
  );
}
