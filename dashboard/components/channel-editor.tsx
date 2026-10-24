"use client";

import { useActionState, useEffect, useState, useTransition } from "react";
import { Save, Trash2 } from "lucide-react";
import { removeChannel, saveChannel } from "@/app/(app)/actions";
import type { PublicChannel } from "@/lib/channels";
import { hourText } from "@/lib/format";
import { useToast } from "./toast";
import { Pill, btn, cx } from "./ui";

type Option = { value: string; label: string; hint?: string };

function Segmented({ name, options, value, onChange }: { name: string; options: Option[]; value: string; onChange: (v: string) => void }) {
  return (
    <div role="radiogroup" className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <label
          key={o.value}
          className={cx(
            "flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-1.5 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus",
            value === o.value ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink-2 hover:border-line-strong",
          )}
        >
          <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} className="sr-only" />
          {o.label}
          {o.hint && <span className={cx("text-[11px]", value === o.value ? "text-surface/60" : "text-ink-3")}>{o.hint}</span>}
        </label>
      ))}
    </div>
  );
}

const MODES: Option[] = [
  { value: "review", label: "ตรวจก่อน", hint: "Telegram + หน้ารีวิว" },
  { value: "auto", label: "โพสต์อัตโนมัติ" },
];

const input = "w-full rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-focus";

/** One Facebook page: what it posts about and how. */
export function ChannelEditor({ channel, themes, primary, seriesDefault, nicheDefault, defaultHours }: {
  channel: PublicChannel; themes: Option[]; primary: boolean; seriesDefault: string; nicheDefault: string; defaultHours: string;
}) {
  const toast = useToast();
  const [state, action, pending] = useActionState(saveChannel, null);
  const [removing, startRemove] = useTransition();
  const [theme, setTheme] = useState(channel.theme);
  const [mode, setMode] = useState<string>(channel.publishMode);
  const [enabled, setEnabled] = useState(channel.enabled);
  useEffect(() => {
    if (state) toast(state);
  }, [state, toast]);

  return (
    <form action={action} className="space-y-4 px-5 py-5">
      <input type="hidden" name="id" value={channel.id} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <a href={`https://www.facebook.com/${channel.pageId}`} target="_blank" rel="noreferrer" className="text-[15px] font-semibold text-ink hover:underline">
              {channel.name}
            </a>
            {primary && <Pill tone="idle">เพจหลัก</Pill>}
            {enabled ? <Pill tone="ok">เปิดใช้</Pill> : <Pill tone="idle">ปิดไว้</Pill>}
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-ink-3">{channel.id}</div>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" name="enabled" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="size-4 accent-ink" />
          ให้ระบบทำคลิปให้เพจนี้
        </label>
      </div>

      <div className="space-y-1.5">
        <div className="text-sm font-medium text-ink">เพจนี้เล่าเรื่องอะไร</div>
        <Segmented name="theme" options={themes} value={theme} onChange={setTheme} />
      </div>

      <div className="grid [&>*]:min-w-0 gap-3 sm:grid-cols-2">
        <label className="space-y-1.5">
          <span className="text-sm font-medium text-ink">ชื่อซีรีส์ (ป้ายบนคลิป)</span>
          <input name="seriesName" defaultValue={channel.seriesName} maxLength={60} placeholder={`ว่าง = ${seriesDefault}`} className={input} />
        </label>
        <label className="space-y-1.5">
          <span className="text-sm font-medium text-ink">แนวเนื้อหาเพิ่มเติม</span>
          <input name="niche" defaultValue={channel.niche} maxLength={300} placeholder={`ว่าง = ${nicheDefault}`} className={input} />
        </label>
      </div>

      <div className="space-y-1.5">
        <div className="text-sm font-medium text-ink">เวลาโพสต์ต่อวัน (เวลาไทย)</div>
        <div className="flex flex-wrap gap-2">
          {[0, 1, 2].map((i) => (
            <select key={i} name="postHour" defaultValue={channel.postHours[i] ?? ""} aria-label={`รอบที่ ${i + 1}`}
              className="rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-focus">
              <option value="">{i === 0 ? `ใช้เวลากลาง (${defaultHours})` : "— ไม่มีรอบนี้"}</option>
              {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>รอบ {i + 1} · {hourText(h)}</option>)}
            </select>
          ))}
        </div>
        <p className="text-xs text-ink-3">วันละ 1–3 คลิป · ระบบเช็กทุกชั่วโมง อาจช้ากว่าเวลาจริง 5–20 นาที · ว่างทั้งหมด = ใช้เวลาจากแท็บ Flow B</p>
      </div>

      <div className="space-y-1.5">
        <div className="text-sm font-medium text-ink">โหมดการโพสต์</div>
        <Segmented name="publishMode" options={MODES} value={mode} onChange={setMode} />
        {mode === "auto" && <p className="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">คลิปของเพจนี้จะโพสต์สาธารณะทันทีโดยไม่มีคนตรวจ</p>}
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={pending} className={cx(btn.base, btn.primary, "px-3 py-1.5")}>
          <Save className="size-3.5" /> {pending ? "กำลังบันทึก…" : "บันทึก"}
        </button>
        <button
          type="button"
          disabled={removing}
          onClick={() => {
            if (confirm(`นำเพจ ${channel.name} ออกจากระบบ? (เพจบน Facebook ไม่ถูกลบ)`)) startRemove(async () => toast(await removeChannel(channel.id)));
          }}
          className={cx(btn.base, btn.ghost, "px-3 py-1.5")}
        >
          <Trash2 className="size-3.5" /> นำออก
        </button>
      </div>
    </form>
  );
}
