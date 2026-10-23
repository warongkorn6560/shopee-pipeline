"use client";

import { useActionState, useEffect, useRef, useTransition } from "react";
import { KeyRound, Trash2 } from "lucide-react";
import { removeClaudeKey, saveClaudeKey } from "@/app/(app)/actions";
import { useToast } from "./toast";
import { btn, cx } from "./ui";

export function ClaudeKeyForm({ hasKey, disabled }: { hasKey: boolean; disabled: boolean }) {
  const toast = useToast();
  const [state, action, pending] = useActionState(saveClaudeKey, null);
  const [removing, startRemove] = useTransition();
  const ref = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (!state) return;
    toast(state);
    if (state.ok) ref.current?.reset();
  }, [state, toast]);

  return (
    <form ref={ref} action={action} className="space-y-2.5">
      <label htmlFor="claude-key" className="block text-sm font-medium text-ink">
        {hasKey ? "เปลี่ยน Claude API key" : "ใส่ Claude API key"}
      </label>
      <div className="flex flex-wrap gap-2">
        <input
          id="claude-key"
          name="key"
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder="sk-ant-…"
          disabled={disabled || pending}
          className="min-w-0 flex-1 rounded-xl border border-line-strong bg-surface px-3 py-2 font-mono text-sm text-ink outline-none focus:border-focus disabled:opacity-60"
        />
        <button type="submit" disabled={disabled || pending} className={cx(btn.base, btn.primary)}>
          <KeyRound className="size-4" /> {pending ? "กำลังตรวจ…" : "ตรวจและบันทึก"}
        </button>
        {hasKey && (
          <button
            type="button"
            disabled={disabled || removing}
            onClick={() => startRemove(async () => toast(await removeClaudeKey()))}
            className={cx(btn.base, btn.ghost)}
          >
            <Trash2 className="size-4" /> ลบ
          </button>
        )}
      </div>
      <p className="text-xs leading-relaxed text-ink-3">
        ระบบเช็คกับ Anthropic ก่อนว่า key ใช้ได้ แล้วเข้ารหัสเก็บเป็น GitHub Secret <span className="font-mono">ANTHROPIC_API_KEY</span> — หน้านี้จะไม่แสดง key อีก
        · ต้องให้ GitHub token มีสิทธิ์ Secrets: Read and write
      </p>
    </form>
  );
}

export function VoiceSample({ id, label }: { id: string; label: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line px-3 py-2">
      <span className="text-sm text-ink">{label}</span>
      <audio controls preload="none" src={`/voices/${id}.mp3`} className="h-8 w-56 max-w-full">
        <track kind="captions" />
      </audio>
    </div>
  );
}
