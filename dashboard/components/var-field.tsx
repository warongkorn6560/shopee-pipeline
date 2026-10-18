"use client";

import { useActionState, useEffect, useState, useTransition } from "react";
import { RotateCcw, Save } from "lucide-react";
import { resetVariable, saveVariable } from "@/app/(app)/actions";
import type { VarDef } from "@/lib/flows";
import { useToast } from "./toast";
import { btn, cx } from "./ui";

export function VarField({ def, current, isSet, disabled }: {
  def: VarDef; current: string; isSet: boolean; disabled?: boolean;
}) {
  const toast = useToast();
  const [state, action, pending] = useActionState(saveVariable, null);
  const [resetting, startReset] = useTransition();
  const [value, setValue] = useState(current);
  useEffect(() => {
    if (state) toast(state);
  }, [state, toast]);
  const dirty = value !== current;
  const id = `var-${def.name}`;
  const showDanger = def.danger && value !== def.workflowDefault && def.kind === "segmented";

  return (
    <form action={action} className="space-y-2.5 px-5 py-4">
      <input type="hidden" name="name" value={def.name} />
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <label htmlFor={def.kind === "segmented" ? undefined : id} className="text-sm font-medium text-ink">{def.label}</label>
        <span className="font-mono text-[11px] text-ink-3">{def.name}{!isSet && " · ค่าเริ่มต้น"}</span>
      </div>

      {def.kind === "segmented" && (
        <div role="radiogroup" aria-label={def.label} className="flex flex-wrap gap-1.5">
          {def.options!.map((o) => (
            <label
              key={o.value}
              className={cx(
                "flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-1.5 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus",
                value === o.value ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink-2 hover:border-line-strong",
                disabled && "pointer-events-none opacity-60",
              )}
            >
              <input
                type="radio"
                name="value"
                value={o.value}
                checked={value === o.value}
                onChange={() => setValue(o.value)}
                disabled={disabled}
                className="sr-only"
              />
              {o.label}
              {o.hint && <span className={cx("text-[11px]", value === o.value ? "text-surface/60" : "text-ink-3")}>{o.hint}</span>}
            </label>
          ))}
        </div>
      )}
      {def.kind === "text" && (
        <input
          id={id}
          name="value"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          maxLength={300}
          disabled={disabled}
          className="w-full rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-focus disabled:opacity-60"
        />
      )}
      {def.kind === "select" && (
        <select
          id={id}
          name="value"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={disabled}
          className="w-full rounded-xl border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-focus disabled:opacity-60"
        >
          {!def.options!.some((o) => o.value === value) && <option value={value}>{value}</option>}
          {def.options!.map((o) => (
            <option key={o.value} value={o.value}>{o.label}{o.hint ? ` — ${o.hint}` : ""}</option>
          ))}
        </select>
      )}

      <p className="text-xs leading-relaxed text-ink-3">{def.help}</p>
      {showDanger && <p className="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">{def.danger}</p>}

      {!disabled && (dirty || isSet) && (
        <div className="flex gap-2 pt-1">
          {dirty && (
            <button type="submit" disabled={pending} className={cx(btn.base, btn.primary, "px-3 py-1.5")}>
              <Save className="size-3.5" /> {pending ? "กำลังบันทึก…" : "บันทึก"}
            </button>
          )}
          {isSet && !dirty && (
            <button
              type="button"
              disabled={resetting}
              onClick={() => startReset(async () => toast(await resetVariable(def.name)))}
              className={cx(btn.base, btn.ghost, "px-3 py-1.5")}
            >
              <RotateCcw className="size-3.5" /> ใช้ค่าเริ่มต้น
            </button>
          )}
        </div>
      )}
    </form>
  );
}
