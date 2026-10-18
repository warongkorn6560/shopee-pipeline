"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { cx } from "./ui";

interface Toast {
  id: number;
  ok: boolean;
  message: string;
}

const ToastContext = createContext<(t: { ok: boolean; message: string }) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((t: { ok: boolean; message: string }) => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all.slice(-2), { id, ...t }]);
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), t.ok ? 4500 : 8000);
  }, []);
  return (
    <ToastContext value={push}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom,0px))] z-50 flex flex-col items-center gap-2 md:inset-x-auto md:right-6 md:bottom-6 md:items-end"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cx(
              "pointer-events-auto flex max-w-md items-start gap-2.5 rounded-xl border bg-surface px-4 py-3 text-sm shadow-card",
              t.ok ? "border-ok/30 text-ink" : "border-bad/40 text-ink",
            )}
          >
            {t.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-bad" />}
            <span className="min-w-0 break-words">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
