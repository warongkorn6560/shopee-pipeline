"use client";

import { useEffect, useRef, useState, useTransition, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Layers, Pause, Play, RefreshCw, X } from "lucide-react";
import { runStoryBurst, runWorkflow, setWorkflowEnabled, type ActionResult } from "@/app/(app)/actions";
import { useToast } from "./toast";
import { btn, cx } from "./ui";

function Dialog({ open, onClose, title, children }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-ink shadow-card"
    >
      <div className="flex items-start justify-between gap-4 px-5 pt-5">
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        <button type="button" onClick={onClose} aria-label="ปิด" className="rounded-lg p-1 text-ink-3 hover:bg-surface-2">
          <X className="size-4" />
        </button>
      </div>
      <div className="px-5 pt-3 pb-5">{children}</div>
    </dialog>
  );
}

function useAction() {
  const toast = useToast();
  const [pending, start] = useTransition();
  const run = (fn: () => Promise<ActionResult>, after?: () => void) =>
    start(async () => {
      const res = await fn();
      toast(res);
      if (res.ok) after?.();
    });
  return { pending, run };
}

export function RunButton({ file, flowName, facts, allowTopic, warning, disabled, compact }: {
  file: string;
  flowName: string;
  facts: { label: string; value: string }[];
  allowTopic?: boolean;
  warning?: string;
  disabled?: boolean;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const { pending, run } = useAction();
  return (
    <>
      <button
        type="button"
        disabled={disabled || pending}
        onClick={() => setOpen(true)}
        className={cx(btn.base, btn.primary, compact && "px-3 py-1.5")}
      >
        <Play className="size-4" />
        {pending ? "กำลังสั่ง…" : "รันตอนนี้"}
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} title={`รัน ${flowName} ตอนนี้?`}>
        <dl className="divide-y divide-line rounded-xl border border-line text-sm">
          {facts.map((f) => (
            <div key={f.label} className="flex items-center justify-between gap-4 px-3.5 py-2.5">
              <dt className="text-ink-2">{f.label}</dt>
              <dd className="text-right font-medium">{f.value}</dd>
            </div>
          ))}
        </dl>
        {allowTopic && (
          <label className="mt-4 block space-y-1.5" htmlFor={`topic-${file}`}>
            <span className="text-sm text-ink-2">หัวข้อเฉพาะครั้งนี้ <span className="text-ink-3">(เว้นว่าง = ใช้คิว)</span></span>
            <input
              id={`topic-${file}`}
              value={topic}
              maxLength={140}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="เช่น ทำไมญี่ปุ่นมีภูเขาไฟเยอะ"
              className="w-full rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm outline-none focus:border-focus"
            />
          </label>
        )}
        {warning && <p className="mt-4 rounded-xl bg-warn-soft px-3.5 py-2.5 text-sm text-warn">{warning}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={() => setOpen(false)} className={cx(btn.base, btn.ghost)}>ยกเลิก</button>
          <button
            type="button"
            disabled={pending}
            onClick={() => run(() => runWorkflow(file, topic || undefined), () => { setOpen(false); setTopic(""); })}
            className={cx(btn.base, btn.primary)}
          >
            <Play className="size-4" />
            ยืนยันรัน
          </button>
        </div>
      </Dialog>
    </>
  );
}

export function BurstButton({ autoMode, pages }: { autoMode: boolean; pages: number }) {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(10);
  const [preview, setPreview] = useState(false);
  const { pending, run } = useAction();
  const clips = count * Math.max(pages, 1);
  return (
    <>
      <button type="button" disabled={pending} onClick={() => setOpen(true)} className={cx(btn.base, btn.secondary)}>
        <Layers className="size-4" /> รัวคลิป
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} title="รัวคลิปต่อเนื่อง">
        <div className="space-y-4 text-sm">
          <label className="block space-y-1.5" htmlFor="burst-count">
            <span className="text-ink-2">จำนวนคลิป{pages > 1 ? " ต่อเพจ" : ""} (1–60)</span>
            <input id="burst-count" type="number" min={1} max={60} value={count}
              onChange={(e) => setCount(Math.min(60, Math.max(1, Number(e.target.value) || 1)))}
              className="w-32 rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm outline-none focus:border-focus" />
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-ink">
            <input type="checkbox" checked={preview} onChange={(e) => setPreview(e.target.checked)} className="size-4 accent-ink" />
            ตัวอย่างเท่านั้น — ส่งเข้าหน้ารีวิว + Telegram ไม่โพสต์
          </label>
          <p className="text-ink-2">
            ทำทีละคลิปต่อกัน รวม {clips} คลิป · ประมาณ {Math.ceil((clips * 17) / 60)} ชั่วโมง · ใช้ Claude ราว ${(clips * 0.45).toFixed(0)}
          </p>
          {!preview && autoMode && (
            <p className="rounded-xl bg-warn-soft px-3.5 py-2.5 text-warn">
              โหมดโพสต์อัตโนมัติ — แต่ละคลิปจะโพสต์สาธารณะทันทีที่ทำเสร็จ (ห่างกันราว 17 นาที) การโพสต์ถี่มากอาจทำให้เพจถูกลดการมองเห็น
            </p>
          )}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={() => setOpen(false)} className={cx(btn.base, btn.ghost)}>ยกเลิก</button>
          <button type="button" disabled={pending} onClick={() => run(() => runStoryBurst(count, preview), () => setOpen(false))} className={cx(btn.base, btn.primary)}>
            <Layers className="size-4" /> เริ่มรัว {clips} คลิป
          </button>
        </div>
      </Dialog>
    </>
  );
}

export function ScheduleToggle({ file, enabled, label }: { file: string; enabled: boolean; label: string }) {
  const [open, setOpen] = useState(false);
  const { pending, run } = useAction();
  return (
    <>
      <button type="button" disabled={pending} onClick={() => setOpen(true)} className={cx(btn.base, btn.secondary)}>
        {enabled ? <Pause className="size-4" /> : <Play className="size-4" />}
        {enabled ? "หยุดรันตามเวลา" : "เปิดรันตามเวลา"}
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} title={enabled ? "หยุดรันตามเวลา?" : "เปิดรันตามเวลา?"}>
        <p className="text-sm text-ink-2">
          {enabled
            ? `${label} จะไม่รันเองจนกว่าจะเปิดอีกครั้ง ยังกด “รันตอนนี้” ได้ตามปกติ`
            : `${label} จะรันเองทุกวันตามเวลาที่ตั้งไว้ วิดีโอจะถูกส่งตามโหมดการโพสต์ที่ตั้งไว้`}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={() => setOpen(false)} className={cx(btn.base, btn.ghost)}>ยกเลิก</button>
          <button
            type="button"
            disabled={pending}
            onClick={() => run(() => setWorkflowEnabled(file, !enabled), () => setOpen(false))}
            className={cx(btn.base, enabled ? btn.danger : btn.primary)}
          >
            {enabled ? "หยุด" : "เปิด"}
          </button>
        </div>
      </Dialog>
    </>
  );
}

export function RefreshButton() {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <button type="button" onClick={() => start(() => router.refresh())} className={cx(btn.base, btn.secondary)}>
      <RefreshCw className={cx("size-4", pending && "animate-spin")} />
      รีเฟรช
    </button>
  );
}

/** Re-fetches server data on an interval while something is running. */
export function AutoRefresh({ active, seconds = 12 }: { active: boolean; seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(id);
  }, [active, seconds, router]);
  return null;
}
