import { createHmac, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { decide } from "@/lib/post-video";

// Telegram buttons under each review video: "ap:<videoId>" approves and posts,
// "rj:<videoId>" rejects. Telegram proves itself with the secret token set in
// setWebhook (derived from the bot token, so there is nothing extra to store).

function webhookSecret(): string {
  return createHmac("sha256", process.env.TELEGRAM_BOT_TOKEN ?? "").update("pipeline-webhook").digest("hex").slice(0, 48);
}

async function telegram(method: string, body: unknown) {
  await fetch(`https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }).catch(() => null);
}

type Update = {
  callback_query?: { id: string; data?: string; message?: { message_id: number; chat: { id: number } } };
};

export async function POST(req: Request) {
  if (!process.env.TELEGRAM_BOT_TOKEN) return NextResponse.json({ ok: false }, { status: 404 });
  const got = Buffer.from(req.headers.get("x-telegram-bot-api-secret-token") ?? "");
  const want = Buffer.from(webhookSecret());
  if (got.length !== want.length || !timingSafeEqual(got, want)) return NextResponse.json({ ok: false }, { status: 401 });

  const cb = ((await req.json().catch(() => ({}))) as Update).callback_query;
  const m = cb?.data?.match(/^(ap|rj):([a-z0-9]{6,20})$/);
  if (!cb || !m) {
    if (cb) await telegram("answerCallbackQuery", { callback_query_id: cb.id });
    return NextResponse.json({ ok: true });
  }

  const result = await decide(m[2], m[1] === "ap" ? "approved" : "rejected");
  await telegram("answerCallbackQuery", { callback_query_id: cb.id, text: result.message.slice(0, 190), show_alert: !result.ok });
  if (cb.message && result.ok) {
    // Replace the buttons with the outcome so the chat shows what was decided.
    const label = m[1] === "ap" ? "✅ อนุมัติแล้ว" + (result.message.includes("โพสต์…") ? " · กำลังโพสต์" : "") : "❌ ไม่ผ่าน";
    await telegram("editMessageReplyMarkup", {
      chat_id: cb.message.chat.id, message_id: cb.message.message_id,
      reply_markup: { inline_keyboard: [[{ text: label, callback_data: "noop" }]] },
    });
  }
  return NextResponse.json({ ok: true });
}
