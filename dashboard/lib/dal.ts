import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { connection } from "next/server";
import { SESSION_COOKIE, verifySessionValue } from "./session";

/** Every data read and every server action calls this first. */
export async function requireSession(): Promise<void> {
  // Auth must run per request (it compares the cookie expiry with the clock).
  await connection();
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!(await verifySessionValue(value))) redirect("/login");
}
