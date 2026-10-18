import "server-only";
import { cache } from "react";

export interface Probe<T> {
  ok: boolean;
  configured: boolean;
  data?: T;
  error?: string;
}

async function probe<T>(configured: boolean, fn: () => Promise<T>): Promise<Probe<T>> {
  if (!configured) return { ok: false, configured: false };
  try {
    return { ok: true, configured: true, data: await fn() };
  } catch (e) {
    return { ok: false, configured: true, error: e instanceof Error ? e.message : String(e) };
  }
}

async function json<T>(url: string, init: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface ElevenQuota {
  tier: string;
  used: number;
  limit: number;
  resetAt: number;
  canExtend: boolean;
}

export const elevenLabs = cache(() =>
  probe<ElevenQuota>(Boolean(process.env.ELEVENLABS_API_KEY), async () => {
    const s = await json<{
      tier: string; character_count: number; character_limit: number;
      next_character_count_reset_unix: number; can_extend_character_limit: boolean;
    }>("https://api.elevenlabs.io/v1/user/subscription", {
      headers: { "xi-api-key": process.env.ELEVENLABS_API_KEY! },
    });
    return {
      tier: s.tier, used: s.character_count, limit: s.character_limit,
      resetAt: s.next_character_count_reset_unix * 1000, canExtend: s.can_extend_character_limit,
    };
  }),
);

export const gatewayCredits = cache(() =>
  probe<{ balance: number; used: number }>(Boolean(process.env.AI_GATEWAY_API_KEY), async () => {
    const c = await json<{ balance: string; total_used: string }>("https://ai-gateway.vercel.sh/v1/credits", {
      headers: { Authorization: `Bearer ${process.env.AI_GATEWAY_API_KEY}` },
    });
    return { balance: Number(c.balance), used: Number(c.total_used) };
  }),
);

export const telegramBot = cache(() =>
  probe<{ username: string }>(Boolean(process.env.TELEGRAM_BOT_TOKEN), async () => {
    const r = await json<{ ok: boolean; result: { username: string } }>(
      `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/getMe`, {},
    );
    if (!r.ok) throw new Error("bot token rejected");
    return { username: r.result.username };
  }),
);
