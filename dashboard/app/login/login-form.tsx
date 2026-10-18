"use client";

import { useActionState } from "react";
import { LogIn } from "lucide-react";
import { btn, cx } from "@/components/ui";
import { login } from "./actions";

export function LoginForm() {
  const [state, action, pending] = useActionState(login, null);
  return (
    <form action={action} className="space-y-4">
      <h1 className="font-display text-lg font-semibold text-ink">เข้าสู่ระบบ</h1>
      <label className="block space-y-1.5" htmlFor="password">
        <span className="text-sm text-ink-2">รหัสผ่าน dashboard</span>
        <input
          id="password"
          name="password"
          type="password"
          required
          autoFocus
          autoComplete="current-password"
          className="w-full rounded-xl border border-line-strong bg-surface px-3.5 py-2.5 text-ink outline-none focus:border-focus"
        />
      </label>
      {state?.error && <p role="alert" className="text-sm text-bad">{state.error}</p>}
      <button type="submit" disabled={pending} className={cx(btn.base, btn.primary, "w-full py-2.5")}>
        <LogIn className="size-4" />
        {pending ? "กำลังตรวจสอบ…" : "เข้าสู่ระบบ"}
      </button>
    </form>
  );
}
