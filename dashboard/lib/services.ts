// Billing + role of every external service, as verified during setup.
// "checked" is when the billing state was last confirmed by hand or API.

export type Billing = "paid" | "free" | "no-card" | "unknown" | "optional";

export interface ServiceInfo {
  name: string;
  role: string;
  billing: Billing;
  cost: string;
  renews?: string;
  decision: string;
  checked: string;
  live?: "elevenlabs" | "gateway" | "telegram" | "github" | "sheets";
  url?: string;
}

export const SERVICES: ServiceInfo[] = [
  {
    name: "ElevenLabs", role: "เสียงพากย์ไทยทั้งสอง flow", billing: "paid",
    cost: "≈ $50 / ปี (Starter รายปี)", renews: "2027-06-16",
    decision: "ใช้ต่อ — 90,000 ตัวอักษร/เดือน พอสำหรับ 2 คลิป/วัน และเติมเกินโควตาไม่ได้ จึงไม่มีค่าใช้จ่ายแอบแฝง",
    checked: "2026-10-19", live: "elevenlabs", url: "https://elevenlabs.io/app/subscription",
  },
  {
    name: "Vercel Pro", role: "โฮสต์ dashboard นี้ + AI Gateway", billing: "paid",
    cost: "แพ็กเกจ Pro รายเดือน · รอบ ก.ย. 2026 มียอด $16.82 (ส่วนใหญ่จากโปรเจกต์อื่น)",
    decision: "ใช้ต่อ — dashboard ใช้ทรัพยากรน้อยมาก ไม่เพิ่มค่าใช้จ่ายที่มีนัยสำคัญ",
    checked: "2026-09-29", url: "https://vercel.com/dashboard",
  },
  {
    name: "Vercel AI Gateway", role: "เขียนบทด้วย AI", billing: "free",
    cost: "Free tier · เครดิตฟรี ~$5/เดือน · ใช้ ≈ $0.005/คลิปเรื่องเล่า",
    decision: "ใช้ต่อแบบฟรี — เติมเครดิตเฉพาะถ้าอยากได้ภาพ AI ใน Flow B (~$0.04/ภาพ)",
    checked: "2026-10-19", live: "gateway", url: "https://vercel.com/dashboard/ai",
  },
  {
    name: "GitHub Actions", role: "รัน pipeline ตามเวลา", billing: "free",
    cost: "ฟรี (repo สาธารณะ)", decision: "ใช้ต่อ",
    checked: "2026-10-19", live: "github", url: "https://github.com/warongkorn6560/shopee-pipeline/actions",
  },
  {
    name: "Google Sheets / Cloud", role: "คิวสินค้าและหัวข้อ", billing: "free",
    cost: "ฟรี · โปรเจกต์ GCP ปิด billing อยู่", decision: "ใช้ต่อ",
    checked: "2026-09-29", live: "sheets",
  },
  {
    name: "Telegram Bot", role: "ส่งวิดีโอให้ตรวจก่อนโพสต์", billing: "free",
    cost: "ฟรี", decision: "ใช้ต่อ", checked: "2026-10-19", live: "telegram",
  },
  {
    name: "Wikimedia Commons + Wikipedia", role: "ภาพแผนที่จริงและแหล่งข้อมูลของ Flow B", billing: "free",
    cost: "ฟรี · แสดงเครดิตภาพตามสัญญาอนุญาต", decision: "ใช้ต่อ", checked: "2026-10-19",
  },
  {
    name: "fal.ai", role: "AI วิดีโอแบบเดิม (Flux + Kling)", billing: "no-card",
    cost: "ยอด $0 · ไม่มีบัตร · auto top-up ปิด", decision: "ไม่ใช้แล้ว — เก็บไว้เป็นทางเลือก (โหมด fal) ไม่มีทางเรียกเก็บเงินได้",
    checked: "2026-09-27", url: "https://fal.ai/dashboard/billing",
  },
  {
    name: "Make.com", role: "ระบบ v1 ที่เลิกใช้", billing: "free",
    cost: "แพ็กเกจ Free (1,000 operations)", decision: "ไม่ได้ใช้ — ไม่มีค่าใช้จ่าย ลบบัญชีได้ถ้าต้องการ",
    checked: "2026-10-19",
  },
  {
    name: "JSON2Video", role: "ระบบ v1 ที่เลิกใช้", billing: "free",
    cost: "แพ็กเกจ Free", decision: "ไม่ได้ใช้ — ไม่มีค่าใช้จ่าย", checked: "2026-10-19",
  },
  {
    name: "Azure Speech", role: "เสียงพากย์สำรองแบบเดิม", billing: "unknown",
    cost: "ยังไม่ได้ตรวจ (ต้อง az login)", decision: "ไม่จำเป็นแล้ว — ถ้าเคยผูกบัตร ควรเข้าไปเช็ค portal.azure.com",
    checked: "2026-09-29", url: "https://portal.azure.com/#view/Microsoft_Azure_CostManagement",
  },
  {
    name: "upload-post.com", role: "โพสต์อัตโนมัติ (Flow A, โหมด auto)", billing: "optional",
    cost: "Free 10 อัปโหลด/เดือน", decision: "ไม่บังคับ — ใช้เฉพาะถ้าเปิดโหมด auto",
    checked: "2026-09-29",
  },
];

export const BILLING_LABEL: Record<Billing, string> = {
  paid: "จ่ายอยู่",
  free: "ฟรี",
  "no-card": "ไม่มีบัตร",
  unknown: "ต้องตรวจ",
  optional: "ไม่บังคับ",
};
