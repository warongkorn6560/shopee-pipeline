import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { ImageOff } from "lucide-react";
import {
  AddProductForm, AddStoryForm, DeleteButton, ImportCsvForm, QuickStory, StatusButtons,
} from "@/components/queue-controls";
import { Card, CardHeader, InlineError, PageHeader, Pill, Skeleton, cx, type Tone } from "@/components/ui";
import { channels } from "@/lib/channels";
import { requireSession } from "@/lib/dal";
import { getProducts, getStories, settle } from "@/lib/data";
import { relative } from "@/lib/format";
import { githubConfigured } from "@/lib/github";
import { storeConfigured, type Product, type Story } from "@/lib/store";

export const metadata: Metadata = { title: "คิวงาน" };

const STATUS_TONE: Record<string, Tone> = {
  Ready: "ok", New: "idle", Posted: "ok", Done: "ok", Failed: "bad", Hold: "warn", Producing: "live",
};
const STATUS_TH: Record<string, string> = {
  Ready: "รอผลิต", New: "ใหม่", Posted: "โพสต์แล้ว", Done: "ผลิตแล้ว", Failed: "ล้มเหลว", Hold: "พักไว้", Producing: "กำลังผลิต",
};

export default function QueuePage({ searchParams }: PageProps<"/queue">) {
  return (
    <div className="space-y-6">
      <PageHeader title="คิวงาน" subtitle="สิ่งที่ pipeline จะหยิบไปทำต่อ — หยิบรายการ “รอผลิต” ที่อยู่บนสุดก่อน วันละ 1 รายการต่อ flow" />
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
  const status = typeof sp.status === "string" ? sp.status : tab === "stories" ? "" : "Ready";
  const channel = typeof sp.channel === "string" ? sp.channel : "";
  if (!storeConfigured()) {
    return <Card className="p-6 text-sm text-ink-2">ยังไม่ได้เชื่อมคลังข้อมูล (BLOB_READ_WRITE_TOKEN)</Card>;
  }
  return (
    <>
      <div role="tablist" className="inline-flex rounded-xl border border-line bg-surface p-1">
        <TabLink href="/queue?tab=products" active={tab === "products"} label="สินค้า" tag="Flow A" />
        <TabLink href="/queue?tab=stories" active={tab === "stories"} label="หัวข้อเรื่องเล่า" tag="Flow B" />
      </div>
      {tab === "products" ? <Products status={status} /> : <Stories status={status} channel={channel} />}
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
  const chip = (k: string) => cx(
    "rounded-full border px-3 py-1 text-xs",
    current === k ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink-2 hover:border-line-strong",
  );
  const keys = ["Ready", ...Object.keys(counts).filter((k) => k !== "Ready").sort(), "all"];
  return (
    <div className="flex flex-wrap gap-1.5">
      {keys.map((k) => (
        <Link
          key={k}
          href={`${base}&status=${k}`}
          className={chip(k)}
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
  const nextId = all.find((p) => p.status === "Ready")?.id;
  const rows = status === "all" ? all : all.filter((p) => p.status === status);
  return (
    <div className="grid [&>*]:min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Card>
        <CardHeader eyebrow={`${all.length} รายการ`} title="สินค้า" action={<Filters base="/queue?tab=products" counts={countBy(all)} current={status} />} />
        <ul className="mt-3 divide-y divide-line">
          {rows.slice(0, 100).map((p) => <ProductRow key={p.id} p={p} next={p.id === nextId} />)}
          {rows.length === 0 && (
            <li className="px-5 py-8 text-center text-sm text-ink-3">
              ไม่มีรายการในสถานะนี้{status === "Ready" && " — กด “เข้าคิว” ที่สินค้าในแท็บ ใหม่/ล้มเหลว หรือนำเข้า CSV"}
            </li>
          )}
        </ul>
        {rows.length > 100 && <p className="px-5 py-3 text-xs text-ink-3">แสดง 100 จาก {rows.length} รายการ</p>}
        <div className="h-2" />
      </Card>
      <div className="space-y-5">
        <Card className="h-fit">
          <CardHeader eyebrow="Shopee Affiliate" title="นำเข้าจาก CSV" />
          <div className="px-5 pt-4 pb-5"><ImportCsvForm /></div>
        </Card>
        <Card className="h-fit">
          <CardHeader eyebrow="ใส่เอง" title="เพิ่มสินค้า" />
          <div className="px-5 pt-4 pb-5"><AddProductForm /></div>
        </Card>
      </div>
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
          {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="hover:text-ink">ลิงก์ ↗</a>}
          <span>{relative(p.updatedAt)}</span>
          {p.status === "Failed" && p.lastError && <span className="truncate text-bad" title={p.lastError}>{p.lastError}</span>}
        </div>
      </div>
      <Pill tone={STATUS_TONE[p.status] ?? "idle"} className="hidden sm:inline-flex">{STATUS_TH[p.status] ?? p.status}</Pill>
      <div className="flex items-center gap-1">
        <StatusButtons tab="products" id={p.id} status={p.status} />
        {p.status !== "Producing" && <DeleteButton tab="products" id={p.id} />}
      </div>
    </li>
  );
}

async function Stories({ status: picked, channel }: { status: string; channel: string }) {
  const res = await getStories();
  if (!res.ok) return <InlineError title="โหลดหัวข้อไม่สำเร็จ" detail={res.error} />;
  const ch = storeConfigured() ? await settle(channels()) : null;
  const { channels: pages, primaryId } = ch?.ok ? ch.value : { channels: [], primaryId: "" };
  const all = channel ? res.value.filter((s) => (s.channelId || primaryId) === channel) : res.value;
  // Most topics are written by the AI as it makes the clip, so "Ready" is often empty: show everything then.
  const status = picked || (all.some((s) => s.status === "Ready") ? "Ready" : "all");
  const base = `/queue?tab=stories${channel ? `&channel=${encodeURIComponent(channel)}` : ""}`;
  const live = pages.filter((c) => c.enabled);
  const ordered = [...live.filter((c) => c.id === primaryId), ...live.filter((c) => c.id !== primaryId)];
  const owner = (s: Story) => s.channelId || primaryId;
  // The next topic each page will make.
  const nextIds = new Set([...new Set(all.map(owner))].map((o) => all.find((s) => s.status === "Ready" && owner(s) === o)?.id));
  const pageName = (s: Story) => (pages.length > 1 ? pages.find((c) => c.id === owner(s))?.name : undefined);
  const rows = status === "all" ? all : all.filter((s) => s.status === status);
  const canRun = githubConfigured();
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader eyebrow="ใส่เอง" title="เพิ่มหัวข้อ" />
        <div className="px-5 pt-4 pb-5"><AddStoryForm channels={ordered.map(({ id, name }) => ({ id, name }))} /></div>
      </Card>
      <Card>
        <CardHeader eyebrow={`${all.length} หัวข้อ`} title="หัวข้อเรื่องเล่า" action={<Filters base={base} counts={countBy(all)} current={status} />} />
        {pages.length > 1 && (
          <div className="mt-3 flex flex-wrap gap-1.5 px-5">
            {[{ id: "", name: "ทุกช่อง" }, ...ordered].map((c) => (
              <Link key={c.id} href={`/queue?tab=stories${c.id ? `&channel=${encodeURIComponent(c.id)}` : ""}`}
                className={cx("rounded-full border px-3 py-1 text-xs", channel === c.id ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink-2 hover:border-line-strong")}>
                {c.name}
              </Link>
            ))}
          </div>
        )}
        <ul className="mt-3 divide-y divide-line">
          {[...rows].reverse().map((s) => <StoryRow key={s.id} s={s} next={nextIds.has(s.id)} canRun={canRun} page={pageName(s)} />)}
          {rows.length === 0 && (
            <li className="px-5 py-8 text-center text-sm text-ink-3">
              ไม่มีรายการในสถานะนี้{status === "Ready" && " — ถ้าเปิด “AI คิดหัวข้อเอง” ไว้ ระบบจะเสนอหัวข้อใหม่ให้ทุกวัน"}
            </li>
          )}
        </ul>
        <div className="h-2" />
      </Card>
    </div>
  );
}

function StoryRow({ s, next, canRun, page }: { s: Story; next: boolean; canRun: boolean; page?: string }) {
  return (
    <li className="flex flex-wrap items-center gap-3 px-5 py-3 sm:flex-nowrap">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {next && <Pill tone="live" className="!py-0 text-[10px]">คิวถัดไป</Pill>}
          <span className="text-sm font-medium text-ink">{s.topic}</span>
          {s.source === "auto" && <span className="rounded bg-surface-2 px-1.5 text-[10px] text-ink-3">AI เสนอ</span>}
          {page && <span className="rounded bg-story-soft px-1.5 text-[10px] text-story">{page}</span>}
        </div>
        <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-ink-3">
          {s.angle && <span className="truncate">{s.angle}</span>}
          {s.title && <span>คลิป: “{s.title}”</span>}
          {s.runUrl?.startsWith("http") && <a href={s.runUrl} target="_blank" rel="noreferrer" className="hover:text-ink">log ↗</a>}
          <span>{relative(s.updatedAt)}</span>
          {s.status === "Failed" && s.lastError && <span className="truncate text-bad" title={s.lastError}>{s.lastError}</span>}
        </div>
      </div>
      <Pill tone={STATUS_TONE[s.status] ?? "idle"}>{STATUS_TH[s.status] ?? s.status}</Pill>
      <div className="flex items-center gap-1">
        {canRun && <QuickStory topic={s.topic} />}
        <StatusButtons tab="stories" id={s.id} status={s.status} />
        {s.status !== "Producing" && <DeleteButton tab="stories" id={s.id} />}
      </div>
    </li>
  );
}
