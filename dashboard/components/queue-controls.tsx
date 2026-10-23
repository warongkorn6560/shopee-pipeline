"use client";

import { useActionState, useEffect, useRef, useState, useTransition } from "react";
import { FileUp, Pause, Play, Plus, Sparkles, Trash2 } from "lucide-react";
import {
  addProduct, addStory, deleteQueueItem, importProductsCsv, runWorkflow, setQueueStatus,
  type ActionResult,
} from "@/app/(app)/actions";
import { useToast } from "./toast";
import { btn, cx } from "./ui";

type Tab = "products" | "stories";

export function StatusButtons({ tab, id, status }: { tab: Tab; id: string; status: string }) {
  const toast = useToast();
  const [pending, start] = useTransition();
  const set = (s: string) => start(async () => toast(await setQueueStatus(tab, id, s)));
  if (status === "Ready") {
    return (
      <button type="button" disabled={pending} onClick={() => set("Hold")} className={cx(btn.base, btn.ghost, "px-2.5 py-1 text-xs")}>
        <Pause className="size-3.5" /> พักไว้
      </button>
    );
  }
  if (status === "Producing" || status === "Posted" || status === "Done") return null;
  return (
    <button type="button" disabled={pending} onClick={() => set("Ready")} className={cx(btn.base, btn.secondary, "px-2.5 py-1 text-xs")}>
      <Play className="size-3.5" /> {status === "Failed" ? "ลองใหม่" : "เข้าคิว"}
    </button>
  );
}

function useTwoStep() {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);
  return [armed, setArmed] as const;
}

export function DeleteButton({ tab, id }: { tab: Tab; id: string }) {
  const toast = useToast();
  const [pending, start] = useTransition();
  const [armed, setArmed] = useTwoStep();
  return (
    <button
      type="button"
      disabled={pending}
      aria-label="ลบรายการนี้"
      title="ลบรายการนี้"
      onClick={() => {
        if (!armed) return setArmed(true);
        setArmed(false);
        start(async () => toast(await deleteQueueItem(tab, id)));
      }}
      className={cx(btn.base, armed ? btn.danger : btn.ghost, "px-2 py-1 text-xs")}
    >
      <Trash2 className="size-3.5" />
      {armed && "ยืนยันลบ"}
    </button>
  );
}

export function QuickStory({ topic, disabled }: { topic: string; disabled?: boolean }) {
  const toast = useToast();
  const [pending, start] = useTransition();
  const [armed, setArmed] = useTwoStep();
  return (
    <button
      type="button"
      disabled={disabled || pending}
      onClick={() => {
        if (!armed) return setArmed(true);
        setArmed(false);
        start(async () => toast(await runWorkflow("story-video.yml", topic)));
      }}
      className={cx(btn.base, armed ? btn.primary : btn.ghost, "px-2.5 py-1 text-xs")}
      title="สร้างคลิปจากหัวข้อนี้ทันที"
    >
      <Sparkles className="size-3.5" /> {pending ? "กำลังสั่ง…" : armed ? "กดอีกครั้งเพื่อยืนยัน" : "สร้างเลย"}
    </button>
  );
}

const input = "w-full rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-focus";

function useFormToast(state: ActionResult | null, form: React.RefObject<HTMLFormElement | null>) {
  const toast = useToast();
  useEffect(() => {
    if (!state) return;
    toast(state);
    if (state.ok) form.current?.reset();
  }, [state, toast, form]);
}

export function ImportCsvForm() {
  const [state, action, pending] = useActionState(importProductsCsv, null);
  const ref = useRef<HTMLFormElement>(null);
  useFormToast(state, ref);
  return (
    <form ref={ref} action={action} className="space-y-3">
      <p className="text-xs leading-relaxed text-ink-3">
        ไฟล์ <b className="text-ink-2">Batch Product Links</b> ที่ดาวน์โหลดจาก Shopee Affiliate ระบบจะดึงรูปสินค้าให้เอง และข้ามสินค้าที่มีอยู่แล้ว
      </p>
      <input
        id="csv-file"
        name="file"
        type="file"
        accept=".csv,text/csv"
        required
        className="block w-full text-sm text-ink-2 file:mr-3 file:rounded-lg file:border-0 file:bg-surface-2 file:px-3 file:py-1.5 file:text-sm file:text-ink hover:file:bg-line"
      />
      <label className="flex items-center gap-2 text-sm text-ink-2" htmlFor="csv-ready">
        <input id="csv-ready" name="ready" type="checkbox" className="size-4 accent-[var(--ink)]" />
        ส่งเข้าคิวผลิตทันที (ไม่ติ๊ก = เก็บเป็น “ใหม่” ให้เลือกทีหลัง)
      </label>
      <button type="submit" disabled={pending} className={cx(btn.base, btn.secondary)}>
        <FileUp className="size-4" /> {pending ? "กำลังนำเข้าและดึงรูป…" : "นำเข้า CSV"}
      </button>
    </form>
  );
}

export function AddProductForm() {
  const [state, action, pending] = useActionState(addProduct, null);
  const ref = useRef<HTMLFormElement>(null);
  useFormToast(state, ref);
  return (
    <form ref={ref} action={action} className="grid gap-3 sm:grid-cols-2">
      <label className="space-y-1 sm:col-span-2" htmlFor="p-name">
        <span className="text-xs text-ink-2">ชื่อสินค้า *</span>
        <input id="p-name" name="name" required maxLength={200} className={input} placeholder="ของเล่นยางกัดสุนัข ทนพิเศษ" />
      </label>
      <label className="space-y-1" htmlFor="p-url">
        <span className="text-xs text-ink-2">ลิงก์ affiliate *</span>
        <input id="p-url" name="url" type="url" required className={input} placeholder="https://s.shopee.co.th/…" />
      </label>
      <label className="space-y-1" htmlFor="p-price">
        <span className="text-xs text-ink-2">ราคา (บาท)</span>
        <input id="p-price" name="price" inputMode="decimal" className={input} placeholder="99" />
      </label>
      <label className="space-y-1 sm:col-span-2" htmlFor="p-image">
        <span className="text-xs text-ink-2">ลิงก์รูปสินค้า <span className="text-ink-3">(เว้นว่างได้ — ดึงจากลิงก์ Shopee ให้เอง)</span></span>
        <input id="p-image" name="image" type="url" className={input} placeholder="https://down-th.img.susercontent.com/file/…" />
      </label>
      <label className="space-y-1 sm:col-span-2" htmlFor="p-notes">
        <span className="text-xs text-ink-2">จุดขาย / โน้ตให้ AI</span>
        <input id="p-notes" name="notes" maxLength={300} className={input} placeholder="ขายดี ทนทาน เหมาะกับหมาพันธุ์ใหญ่" />
      </label>
      <div className="sm:col-span-2">
        <button type="submit" disabled={pending} className={cx(btn.base, btn.primary)}>
          <Plus className="size-4" /> {pending ? "กำลังเพิ่ม…" : "เพิ่มเข้าคิว"}
        </button>
      </div>
    </form>
  );
}

export function AddStoryForm() {
  const [state, action, pending] = useActionState(addStory, null);
  const ref = useRef<HTMLFormElement>(null);
  useFormToast(state, ref);
  return (
    <form ref={ref} action={action} className="grid gap-3 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto] sm:items-end">
      <label className="space-y-1" htmlFor="s-topic">
        <span className="text-xs text-ink-2">หัวข้อ (เป็นคำถามชวนสงสัยจะดีที่สุด) *</span>
        <input id="s-topic" name="topic" required maxLength={140} className={input} placeholder="ทำไมญี่ปุ่นถึงมีภูเขาไฟเยอะ" />
      </label>
      <label className="space-y-1" htmlFor="s-angle">
        <span className="text-xs text-ink-2">มุมเล่า</span>
        <input id="s-angle" name="angle" maxLength={300} className={input} placeholder="เล่าผ่านแผนที่วงแหวนแห่งไฟ" />
      </label>
      <button type="submit" disabled={pending} className={cx(btn.base, btn.primary)}>
        <Plus className="size-4" /> {pending ? "กำลังเพิ่ม…" : "เพิ่ม"}
      </button>
    </form>
  );
}
