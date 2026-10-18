"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  SESSION_COOKIE, SESSION_TTL_MS, authConfigured, createSessionValue, passwordMatches,
} from "@/lib/session";

export async function login(_: { error: string } | null, form: FormData): Promise<{ error: string }> {
  if (!authConfigured()) return { error: "ยังไม่ได้ตั้งรหัสผ่านของ dashboard" };
  const password = String(form.get("password") ?? "");
  if (!(await passwordMatches(password))) {
    // Slow down guessing.
    await new Promise((r) => setTimeout(r, 900));
    return { error: "รหัสผ่านไม่ถูกต้อง" };
  }
  (await cookies()).set(SESSION_COOKIE, await createSessionValue(), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_TTL_MS / 1000,
  });
  redirect("/");
}
