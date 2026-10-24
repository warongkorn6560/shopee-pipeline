"use client";

import { useActionState, useEffect, useRef, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Link2, Unlink } from "lucide-react";
import { disconnectSocial, pickFacebookPages, saveMetaSecret, saveTiktokApp } from "@/app/(app)/actions";
import type { Provider } from "@/lib/social";
import { useToast } from "./toast";
import { btn, cx } from "./ui";

const NAMES: Record<Provider, string> = { facebook: "เพจ Facebook", instagram: "Instagram", tiktok: "TikTok" };

export function ConnectButtons({ provider, connected, ready }: { provider: Provider; connected: boolean; ready: boolean }) {
  const toast = useToast();
  const [pending, start] = useTransition();
  return (
    <div className="flex flex-wrap gap-2">
      {/* A plain link: the connect route redirects to the provider's sign-in page. */}
      <a
        href={ready ? `/api/connect/${provider}` : undefined}
        aria-disabled={!ready}
        className={cx(btn.base, connected ? btn.secondary : btn.primary, !ready && "pointer-events-none opacity-50")}
      >
        <Link2 className="size-4" /> {connected ? "เชื่อมใหม่" : "เชื่อม"}
      </a>
      {connected && (
        <button
          type="button"
          disabled={pending}
          onClick={() => start(async () => toast(await disconnectSocial(provider)))}
          className={cx(btn.base, btn.ghost)}
        >
          <Unlink className="size-4" /> ยกเลิก
        </button>
      )}
    </div>
  );
}

/** Shows the result of an OAuth round trip (?connected=… / ?social_error=…) once, then cleans the URL. */
export function ConnectResult() {
  const params = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const shown = useRef(false);
  useEffect(() => {
    const ok = params.get("connected") as Provider | null;
    const err = params.get("social_error");
    if (shown.current || (!ok && !err)) return;
    shown.current = true;
    toast(ok
      ? { ok: true, message: `เชื่อม ${NAMES[ok] ?? ok} สำเร็จ${params.get("name") ? ` — ${params.get("name")}` : ""}` }
      : { ok: false, message: err! });
    router.replace(`/settings#${ok === "facebook" || !ok ? "channels" : "social"}`, { scroll: false });
  }, [params, router, toast]);
  return null;
}

export function TiktokAppForm({ saved }: { saved: boolean }) {
  const toast = useToast();
  const [state, action, pending] = useActionState(saveTiktokApp, null);
  const ref = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (!state) return;
    toast(state);
    if (state.ok) ref.current?.reset();
  }, [state, toast]);
  const input = "min-w-0 flex-1 rounded-xl border border-line-strong bg-surface px-3 py-2 font-mono text-sm text-ink outline-none focus:border-focus";
  return (
    <form ref={ref} action={action} className="space-y-2">
      <div className="text-xs text-ink-3">{saved ? "บันทึกแอป TikTok แล้ว · ใส่ใหม่ถ้าต้องการเปลี่ยน" : "ใส่ Client key / secret จาก developers.tiktok.com ก่อน"}</div>
      <div className="flex flex-wrap gap-2">
        <input name="clientKey" placeholder="Client key" autoComplete="off" spellCheck={false} className={input} />
        <input name="clientSecret" type="password" placeholder="Client secret" autoComplete="off" spellCheck={false} className={input} />
        <button type="submit" disabled={pending} className={cx(btn.base, btn.secondary)}>บันทึก</button>
      </div>
    </form>
  );
}

export function MetaSecretForm({ appId, saved }: { appId: string; saved: boolean }) {
  const toast = useToast();
  const [state, action, pending] = useActionState(saveMetaSecret, null);
  const ref = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (!state) return;
    toast(state);
    if (state.ok) ref.current?.reset();
  }, [state, toast]);
  return (
    <form ref={ref} action={action} className="space-y-2">
      <div className="text-xs text-ink-3">
        {saved ? "บันทึก App secret แล้ว · ใส่ใหม่ถ้าต้องการเปลี่ยน" : "ใส่ App secret ของแอป ShopeePipeline ก่อน (ครั้งเดียว)"} ·{" "}
        <a href={`https://developers.facebook.com/apps/${appId}/settings/basic/`} target="_blank" rel="noreferrer" className="underline">
          เปิดหน้า App settings → Basic → App secret → Show
        </a>
      </div>
      <div className="flex flex-wrap gap-2">
        <input name="appSecret" type="password" placeholder="App secret" autoComplete="off" spellCheck={false}
          className="min-w-0 flex-1 rounded-xl border border-line-strong bg-surface px-3 py-2 font-mono text-sm text-ink outline-none focus:border-focus" />
        <button type="submit" disabled={pending} className={cx(btn.base, btn.secondary)}>บันทึก</button>
      </div>
    </form>
  );
}

export function PagePicker({ pages, connected }: { pages: { id: string; name: string }[]; connected: string[] }) {
  const toast = useToast();
  const [pending, start] = useTransition();
  const [picked, setPicked] = useState<string[]>(() => {
    const already = pages.filter((p) => connected.includes(p.id)).map((p) => p.id);
    return already.length ? already : pages.map((p) => p.id);
  });
  const toggle = (id: string) => setPicked((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  return (
    <div>
      <ul className="divide-y divide-line">
        {pages.map((p) => (
          <li key={p.id}>
            <label className="flex cursor-pointer items-center gap-3 px-5 py-3 hover:bg-surface-2">
              <input type="checkbox" checked={picked.includes(p.id)} onChange={() => toggle(p.id)} className="size-4 accent-ink" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink">{p.name}</div>
                <div className="font-mono text-xs text-ink-3">{p.id}{connected.includes(p.id) && " · เชื่อมอยู่แล้ว (จะต่ออายุ token ให้)"}</div>
              </div>
            </label>
          </li>
        ))}
      </ul>
      <div className="px-5 pt-3 pb-5">
        <button
          type="button"
          disabled={pending || !picked.length}
          onClick={() => start(async () => {
            const r = await pickFacebookPages(picked);
            if (r && !r.ok) toast(r);
          })}
          className={cx(btn.base, btn.primary)}
        >
          {pending ? "กำลังเชื่อม…" : `เชื่อม ${picked.length} เพจ`}
        </button>
      </div>
    </div>
  );
}
