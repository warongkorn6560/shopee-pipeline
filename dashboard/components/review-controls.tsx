"use client";

import { useState, useTransition } from "react";
import { Check, Copy, RotateCcw, Send, Upload, X } from "lucide-react";
import { repostVideo, reviewVideo } from "@/app/(app)/actions";
import type { VideoStatus } from "@/lib/store";
import { useToast } from "./toast";
import { btn, cx } from "./ui";

export function CopyButton({ text, label = "คัดลอก" }: { text: string; label?: string }) {
  const toast = useToast();
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1800);
        } catch {
          toast({ ok: false, message: "คัดลอกไม่ได้ในเบราว์เซอร์นี้ — เลือกข้อความแล้วคัดลอกเอง" });
        }
      }}
      className={cx(btn.base, btn.ghost, "px-2.5 py-1 text-xs")}
    >
      {done ? <Check className="size-3.5 text-ok" /> : <Copy className="size-3.5" />}
      {done ? "คัดลอกแล้ว" : label}
    </button>
  );
}

export function ReviewActions({ id, status, canPost }: { id: string; status: VideoStatus; canPost?: boolean }) {
  const toast = useToast();
  const [pending, start] = useTransition();
  const act = (decision: VideoStatus, requeue = false) =>
    start(async () => toast(await reviewVideo(id, decision, { requeue })));
  const small = "px-3 py-1.5";
  if (status === "review") {
    return (
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={pending} onClick={() => act("approved")} className={cx(btn.base, btn.primary, small)}
          title={canPost ? "ผ่าน แล้วโพสต์ไปเพจของคลิปนี้ทันที" : undefined}>
          <Check className="size-4" /> {canPost ? "ผ่าน · โพสต์เลย" : "ผ่าน"}
        </button>
        <button type="button" disabled={pending} onClick={() => act("rejected")} className={cx(btn.base, btn.secondary, small)}>
          <X className="size-4" /> ไม่ผ่าน
        </button>
        <button type="button" disabled={pending} onClick={() => act("rejected", true)} className={cx(btn.base, btn.ghost, small)} title="ไม่ผ่าน และส่งสินค้า/หัวข้อนี้กลับเข้าคิวให้สร้างใหม่">
          <RotateCcw className="size-4" /> ไม่ผ่าน · ทำใหม่
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-2">
      {status === "approved" && canPost && (
        <button type="button" disabled={pending} onClick={() => start(async () => toast(await repostVideo(id)))} className={cx(btn.base, btn.primary, small)}>
          <Upload className="size-4" /> โพสต์อีกครั้ง
        </button>
      )}
      {status === "approved" && (
        <button type="button" disabled={pending} onClick={() => act("posted")} className={cx(btn.base, canPost ? btn.secondary : btn.primary, small)}>
          <Send className="size-4" /> {canPost ? "ทำเครื่องหมายว่าโพสต์แล้ว" : "โพสต์แล้ว"}
        </button>
      )}
      {status === "rejected" && (
        <button type="button" disabled={pending} onClick={() => act("rejected", true)} className={cx(btn.base, btn.secondary, small)}>
          <RotateCcw className="size-4" /> ส่งกลับไปทำใหม่
        </button>
      )}
      <button type="button" disabled={pending} onClick={() => act("review")} className={cx(btn.base, btn.ghost, small)}>
        กลับไปรอตรวจ
      </button>
    </div>
  );
}
