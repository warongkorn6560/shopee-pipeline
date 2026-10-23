// Billing + role of every service this system touches, plus other recurring
// charges found on the same accounts. "checked" is when billing was last
// confirmed (API, CLI, or console).

export type Billing = "paid" | "included" | "free" | "no-card" | "unknown" | "optional" | "other";

export interface ServiceInfo {
  name: string;
  role: string;
  billing: Billing;
  cost: string;
  renews?: string;
  decision: string;
  checked: string;
  live?: "elevenlabs" | "gateway";
  url?: string;
}

export const SERVICES: ServiceInfo[] = [
  {
    name: "Claude API (Anthropic)", role: "เขียนบท วางช็อตแผนที่ และคิดหัวข้อ ทั้งสอง flow", billing: "paid",
    cost: "คีย์ของคุณ (งบ ~$100/เดือน) · ≈ $0.10/คลิปเรื่องเล่า (Opus 5.5), ≈ $0.03/คลิปขาย",
    decision: "ใช้แทน AI Gateway เมื่อใส่ key ที่หน้าตั้งค่า — ทำวันละ 2 คลิปตกราว $4/เดือน",
    checked: "2026-10-24", url: "https://console.anthropic.com/settings/billing",
  },
  {
    name: "ElevenLabs", role: "เสียงพากย์ไทยทั้งสอง flow", billing: "paid",
    cost: "≈ $50 / ปี (Starter รายปี)", renews: "2027-06-16",
    decision: "ใช้ต่อ — 90,000 ตัวอักษร/เดือน พอสำหรับ 2 คลิป/วัน เติมเกินโควตาไม่ได้ จึงไม่มีบิลเพิ่ม · ต่ออายุอัตโนมัติถ้าไม่ปิด",
    checked: "2026-10-24", live: "elevenlabs", url: "https://elevenlabs.io/app/subscription",
  },
  {
    name: "Vercel Pro", role: "โฮสต์ dashboard นี้ + เว็บอื่นของคุณ", billing: "paid",
    cost: "$20/เดือน + ค่าใช้งาน · ยอดรวม ก.ค. $33.86 · ส.ค. $45.02 · ก.ย. $24.82",
    decision: "ใช้ต่อ — ค่าใช้งานส่วนเกินมาจากเว็บอื่น (ก.ย. thaipography-frontend $4.43) ระบบนี้ใช้น้อยจนไม่ขึ้นบิล",
    checked: "2026-10-24", url: "https://vercel.com/dashboard",
  },
  {
    name: "Vercel Blob · pipeline-data", role: "เก็บคิวงานและวิดีโอรีวิวของระบบนี้", billing: "included",
    cost: "รวมใน Vercel Pro · ใช้ไม่ถึง 1 GB (ลบวิดีโอเก่ากว่า 30 วันให้อัตโนมัติ)",
    decision: "ใช้ — แทน Google Sheet ทำให้ทุกอย่างอยู่ในเว็บเดียว", checked: "2026-10-24",
  },
  {
    name: "Vercel AI Gateway", role: "เขียนบทด้วย AI", billing: "free",
    cost: "Free tier · เครดิตฟรี ~$5/เดือน · ใช้ ≈ $0.005/คลิปเรื่องเล่า",
    decision: "ใช้ต่อแบบฟรี — เติมเครดิตเฉพาะถ้าอยากได้ภาพ AI ใน Flow B (~$0.04/ภาพ)",
    checked: "2026-10-24", live: "gateway", url: "https://vercel.com/dashboard/ai",
  },
  {
    name: "GitHub Actions", role: "รัน pipeline ตามเวลา", billing: "free",
    cost: "ฟรี (repo สาธารณะ)", decision: "ใช้ต่อ", checked: "2026-10-24",
    url: "https://github.com/warongkorn6560/shopee-pipeline/actions",
  },
  {
    name: "Telegram Bot", role: "แจ้งเตือนเมื่อมีคลิปใหม่", billing: "free",
    cost: "ฟรี", decision: "ใช้ต่อ", checked: "2026-10-24",
  },
  {
    name: "Wikimedia Commons + Wikipedia", role: "ภาพแผนที่จริงและแหล่งข้อมูลของ Flow B", billing: "free",
    cost: "ฟรี · แสดงเครดิตภาพตามสัญญาอนุญาต", decision: "ใช้ต่อ", checked: "2026-10-24",
  },
  {
    name: "Google Sheets", role: "คิวงานแบบเดิม", billing: "free",
    cost: "ฟรี · โปรเจกต์ shopee-pipeline ปิด billing",
    decision: "เลิกใช้แล้ว — ย้ายข้อมูลมาไว้ในเว็บนี้ ชีตเก่าเก็บไว้เป็นสำรองอ่านอย่างเดียว",
    checked: "2026-10-24",
  },
  {
    name: "Neon Postgres (ผ่าน Vercel)", role: "โปรเจกต์อื่น: workwark, lull, firmworks, claude-app, promschool_2026", billing: "other",
    cost: "แผน Launch คิดตามใช้งาน ($0.106/CU-hour, $0.35/GB-เดือน) · ออกบิลผ่าน Vercel",
    decision: "ไม่เกี่ยวกับระบบนี้ — ไม่ได้แตะ ถ้าโปรเจกต์ไหนเลิกใช้ ลบฐานข้อมูลนั้นใน Vercel → Storage",
    checked: "2026-10-24", url: "https://vercel.com/dashboard/stores",
  },
  {
    name: "Upstash Redis · upstash-kv-indigo-flask", role: "โปรเจกต์อื่น: 5lab-tokyo-2026", billing: "other",
    cost: "Pay As You Go ($0.2 / 100K คำสั่ง) · ออกบิลผ่าน Vercel",
    decision: "ไม่เกี่ยวกับระบบนี้ — ถ้างาน 5lab-tokyo-2026 จบแล้ว ลบได้ใน Vercel → Storage",
    checked: "2026-10-24", url: "https://vercel.com/dashboard/stores",
  },
  {
    name: "Google Cloud · warongkorn.most", role: "โปรเจกต์อื่น: ระบบส่งเมลของ thaipography, nng", billing: "other",
    cost: "My Billing Account เปิดอยู่บัญชีเดียว · 30 วันล่าสุด ฿0 · อีก 3 บัญชีปิดแล้ว",
    decision: "ไม่เกี่ยวกับระบบนี้ — Gmail API ฟรี จึงไม่ควรมีค่าใช้จ่าย",
    checked: "2026-10-24", url: "https://console.cloud.google.com/billing",
  },
  {
    name: "fal.ai", role: "AI วิดีโอแบบเดิม", billing: "no-card",
    cost: "ยอด $0 · ไม่มีบัตร · auto top-up ปิด", decision: "ไม่ใช้แล้ว — เรียกเก็บเงินไม่ได้",
    checked: "2026-09-27", url: "https://fal.ai/dashboard/billing",
  },
  {
    name: "Make.com · JSON2Video", role: "ระบบ v1 ที่เลิกใช้", billing: "free",
    cost: "แพ็กเกจ Free ทั้งคู่", decision: "ไม่ได้ใช้ — ไม่มีค่าใช้จ่าย ลบบัญชีได้ถ้าต้องการ", checked: "2026-10-19",
  },
  {
    name: "Azure Speech", role: "เสียงพากย์สำรองแบบเดิม", billing: "unknown",
    cost: "ยังตรวจไม่ได้ (ต้อง az login เอง)", decision: "ไม่ใช้แล้ว — เข้า portal.azure.com → Cost Management ดูว่ามีบัตรผูกหรือมีบิลไหม",
    checked: "2026-10-24", url: "https://portal.azure.com/#view/Microsoft_Azure_CostManagement",
  },
];

export const BILLING_LABEL: Record<Billing, string> = {
  paid: "จ่ายอยู่",
  included: "รวมในแพ็กเกจ",
  free: "ฟรี",
  "no-card": "ไม่มีบัตร",
  unknown: "ต้องตรวจ",
  optional: "ไม่บังคับ",
  other: "บิลของงานอื่น",
};
