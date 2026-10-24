import type { Metadata } from "next";
import { authConfigured } from "@/lib/session";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "เข้าสู่ระบบ" };

export default function LoginPage() {
  const ready = authConfigured();
  return (
    <main className="grid min-h-full place-items-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <Mark />
          <div>
            <div className="font-display text-lg font-semibold leading-none text-ink">Pipeline Control</div>
            <div className="mt-1 text-xs text-ink-3">Shopee Affiliate · ย้อนรอยการเมืองไทย</div>
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-6 shadow-card">
          {ready ? (
            <LoginForm />
          ) : (
            <div className="space-y-3 text-sm text-ink-2">
              <h1 className="font-display text-lg font-semibold text-ink">ตั้งรหัสผ่านก่อนใช้งาน</h1>
              <p>เพิ่ม Environment Variables สองตัวในโปรเจกต์ Vercel แล้ว deploy ใหม่:</p>
              <ul className="space-y-1.5 font-mono text-xs text-ink">
                <li className="rounded-lg bg-surface-2 px-3 py-2">DASHBOARD_PASSWORD</li>
                <li className="rounded-lg bg-surface-2 px-3 py-2">SESSION_SECRET <span className="text-ink-3">(สุ่ม 32+ ตัวอักษร)</span></li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

function Mark() {
  return (
    <svg viewBox="0 0 64 64" className="size-10" aria-hidden>
      <rect width="64" height="64" rx="14" className="fill-ink" />
      <rect x="10" y="40" width="20" height="6" rx="3" fill="#e8452a" />
      <rect x="34" y="40" width="20" height="6" rx="3" fill="#f2b544" />
      <circle cx="32" cy="24" r="9" fill="#e5322d" />
    </svg>
  );
}
