// Static description of both pipelines. Must stay in sync with
// pipeline/config.py and .github/workflows/*.yml in the repo root.

export type FlowId = "shopee" | "story";

export type StepKey = "input" | "script" | "visual" | "voice" | "render" | "deliver";

export interface FlowStep {
  key: StepKey;
  label: string;
  tool: string;
  service: ServiceKey;
}

export type ServiceKey =
  | "store" | "gateway" | "wikimedia" | "local" | "elevenlabs" | "ffmpeg" | "telegram";

export interface WorkflowRef {
  file: string;
  role: string;
  primary?: boolean;
  cron: string;
  scheduleLabel: string;
  inputs?: { topic?: boolean };
}

export interface FlowDef {
  id: FlowId;
  name: string;
  short: string;
  tagline: string;
  workflows: WorkflowRef[];
  steps: FlowStep[];
  publishVar: string;
  queueTab: "Inbox" | "Stories";
  costNote: string;
}

export const FLOWS: FlowDef[] = [
  {
    id: "shopee",
    name: "Shopee Affiliate",
    short: "Flow A",
    tagline: "คลิปขายสินค้าจากรูปจริง + เสียงพากย์ไทย",
    workflows: [
      { file: "daily-video.yml", role: "สร้างและส่งวิดีโอ", primary: true, cron: "0 2 * * *", scheduleLabel: "ทุกวัน 09:00 น." },
    ],
    steps: [
      { key: "input", label: "สินค้า", tool: "คิวสินค้าในเว็บนี้", service: "store" },
      { key: "script", label: "บทขาย", tool: "Gemini via AI Gateway", service: "gateway" },
      { key: "visual", label: "ภาพ", tool: "รูปสินค้า + Ken Burns", service: "local" },
      { key: "voice", label: "เสียง", tool: "ElevenLabs", service: "elevenlabs" },
      { key: "render", label: "ตัดต่อ", tool: "FFmpeg + คำบรรยายไทย", service: "ffmpeg" },
      { key: "deliver", label: "ส่ง", tool: "หน้ารีวิว + Telegram", service: "telegram" },
    ],
    publishVar: "PUBLISH_MODE",
    queueTab: "Inbox",
    costNote: "$0 ต่อคลิป (เสียงใช้เครดิต ElevenLabs ที่จ่ายรายปีแล้ว)",
  },
  {
    id: "story",
    name: "เรื่องเล่าจากแผนที่",
    short: "Flow B",
    tagline: "คลิปให้ความรู้แนวเล่าเรื่อง อ้างอิง Wikipedia",
    workflows: [
      {
        file: "story-video.yml", role: "สร้างและส่งคลิปเล่าเรื่อง", primary: true,
        cron: "0 12 * * *", scheduleLabel: "ทุกวัน 19:00 น.", inputs: { topic: true },
      },
    ],
    steps: [
      { key: "input", label: "หัวข้อ", tool: "คิวหัวข้อในเว็บนี้", service: "store" },
      { key: "script", label: "บทบรรยาย", tool: "GPT-4.1 mini + Wikipedia", service: "gateway" },
      { key: "visual", label: "ภาพ", tool: "แผนที่จริงจาก Wikimedia", service: "wikimedia" },
      { key: "voice", label: "เสียง", tool: "ElevenLabs (จับเวลาตามคำ)", service: "elevenlabs" },
      { key: "render", label: "ตัดต่อ", tool: "FFmpeg + ดนตรีประกอบ", service: "ffmpeg" },
      { key: "deliver", label: "ส่ง", tool: "หน้ารีวิว + Telegram", service: "telegram" },
    ],
    publishVar: "STORY_PUBLISH_MODE",
    queueTab: "Stories",
    costNote: "≈ $0.005 ต่อคลิป (หักจากเครดิตฟรีของ AI Gateway)",
  },
];

export const WORKFLOW_FILES = FLOWS.flatMap((f) => f.workflows.map((w) => w.file));

export function flowById(id: string): FlowDef | undefined {
  return FLOWS.find((f) => f.id === id);
}

// ---------------------------------------------------------------------------
// GitHub Actions variables the dashboard can edit
// ---------------------------------------------------------------------------
export type VarKind = "segmented" | "text" | "select";

export interface VarDef {
  name: string;
  label: string;
  help: string;
  kind: VarKind;
  workflowDefault: string; // value the workflow uses when the variable is unset
  options?: { value: string; label: string; hint?: string }[];
  scope: FlowId | "shared";
  danger?: string; // shown when this value is selected
}

export const VARIABLES: VarDef[] = [
  {
    name: "PUBLISH_MODE", label: "โหมดการโพสต์", scope: "shopee", kind: "segmented",
    workflowDefault: "review",
    help: "review ส่งวิดีโอเข้า Telegram ให้คุณตรวจก่อนโพสต์เอง · auto โพสต์ไปบัญชีที่เชื่อมไว้ทันที",
    options: [
      { value: "review", label: "ตรวจก่อน", hint: "Telegram" },
      { value: "auto", label: "โพสต์อัตโนมัติ", hint: "TikTok · IG" },
    ],
    danger: "auto จะโพสต์สาธารณะทันทีโดยไม่มีคนตรวจ",
  },
  {
    name: "STORY_PUBLISH_MODE", label: "โหมดการโพสต์", scope: "story", kind: "segmented",
    workflowDefault: "review",
    help: "review ส่งเข้า Telegram ให้ตรวจ · auto โพสต์ Reels ไปเพจ Facebook (และ TikTok/IG ถ้าเชื่อมไว้)",
    options: [
      { value: "review", label: "ตรวจก่อน", hint: "Telegram" },
      { value: "auto", label: "โพสต์อัตโนมัติ", hint: "Facebook" },
    ],
    danger: "auto จะโพสต์ไปเพจ Facebook ทันทีโดยไม่มีคนตรวจ",
  },
  {
    name: "STORY_SERIES_NAME", label: "ชื่อซีรีส์ (ป้ายบนคลิป)", scope: "story", kind: "text",
    workflowDefault: "เรื่องเล่าจากแผนที่",
    help: "แสดงเป็นป้ายมุมบนของทุกฉาก และใช้ในข้อความโพสต์",
  },
  {
    name: "STORY_NICHE", label: "แนวเนื้อหา", scope: "story", kind: "text",
    workflowDefault: "เรื่องเล่าประวัติศาสตร์และภูมิศาสตร์ผ่านแผนที่ ทั้งไทยและโลก เล่าแบบสนุก เข้าใจง่าย",
    help: "ใช้ตอนคิวว่างแล้ว AI เสนอหัวข้อใหม่เอง",
  },
  {
    name: "STORY_AUTO_TOPIC", label: "คิวว่างให้ AI คิดหัวข้อเอง", scope: "story", kind: "segmented",
    workflowDefault: "on",
    help: "on = ถ้าไม่มีหัวข้อสถานะ Ready จะเสนอหัวข้อใหม่ที่ไม่ซ้ำของเดิม · off = ข้ามวันนั้น",
    options: [
      { value: "on", label: "เปิด" },
      { value: "off", label: "ปิด" },
    ],
  },
  {
    name: "STORY_IMAGE_PROVIDER", label: "แหล่งภาพ", scope: "story", kind: "segmented",
    workflowDefault: "auto",
    help: "auto ใช้ภาพจริงจาก Wikimedia เป็นหลัก และภาพ AI เมื่อมีเครดิต · cards ใช้การ์ดกราฟิกอย่างเดียว",
    options: [
      { value: "auto", label: "อัตโนมัติ" },
      { value: "wikimedia", label: "Wikimedia" },
      { value: "gateway", label: "AI", hint: "ต้องเติมเครดิต" },
      { value: "cards", label: "การ์ด" },
    ],
  },
  {
    name: "STORY_LLM_MODEL", label: "โมเดลเขียนบทเรื่องเล่า", scope: "story", kind: "select",
    workflowDefault: "openai/gpt-4.1-mini",
    help: "รุ่นที่ใช้ได้กับ AI Gateway free tier · ถ้ารุ่นที่เลือกถูกปฏิเสธ จะถอยไปใช้รุ่นพื้นฐานเอง",
    options: [
      { value: "openai/gpt-4.1-mini", label: "GPT-4.1 mini", hint: "แนะนำ" },
      { value: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
      { value: "moonshotai/kimi-k2", label: "Kimi K2" },
      { value: "google/gemini-2.5-flash-lite", label: "Gemini 2.5 Flash-Lite", hint: "เร็วสุด" },
    ],
  },
  {
    name: "LLM_MODEL", label: "โมเดลเขียนบทขาย", scope: "shopee", kind: "select",
    workflowDefault: "google/gemini-2.5-flash-lite",
    help: "ใช้เขียนบทคลิปขายของ Flow A",
    options: [
      { value: "google/gemini-2.5-flash-lite", label: "Gemini 2.5 Flash-Lite", hint: "ค่าเริ่มต้น" },
      { value: "openai/gpt-4.1-mini", label: "GPT-4.1 mini" },
      { value: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    ],
  },
];

// ---------------------------------------------------------------------------
// GitHub Secrets each flow needs (names only — values are never read)
// ---------------------------------------------------------------------------
export interface SecretDef {
  name: string;
  purpose: string;
  flows: FlowId[];
  need: "required" | "auto";
}

export const SECRETS: SecretDef[] = [
  { name: "PIPELINE_API_KEY", purpose: "ให้ pipeline คุยกับเว็บนี้ (คิว + ส่งวิดีโอรีวิว)", flows: ["shopee", "story"], need: "required" },
  { name: "AI_GATEWAY_API_KEY", purpose: "เขียนบทด้วย AI", flows: ["shopee", "story"], need: "required" },
  { name: "ELEVENLABS_API_KEY", purpose: "เสียงพากย์ไทย", flows: ["shopee", "story"], need: "required" },
  { name: "TELEGRAM_BOT_TOKEN", purpose: "ส่งวิดีโอให้ตรวจ", flows: ["shopee", "story"], need: "required" },
  { name: "TELEGRAM_CHAT_ID", purpose: "ห้องแชตที่รับวิดีโอ", flows: ["shopee", "story"], need: "required" },
  { name: "FACEBOOK_PAGE_ID", purpose: "เพจที่จะโพสต์ Reels", flows: ["story"], need: "auto" },
  { name: "FACEBOOK_PAGE_TOKEN", purpose: "สิทธิ์โพสต์เพจ", flows: ["story"], need: "auto" },
  { name: "TIKTOK_CLIENT_KEY", purpose: "แอป TikTok", flows: ["shopee", "story"], need: "auto" },
  { name: "TIKTOK_CLIENT_SECRET", purpose: "แอป TikTok", flows: ["shopee", "story"], need: "auto" },
  { name: "TIKTOK_REFRESH_TOKEN", purpose: "สิทธิ์โพสต์ TikTok", flows: ["shopee", "story"], need: "auto" },
  { name: "INSTAGRAM_ACCESS_TOKEN", purpose: "สิทธิ์โพสต์ IG (อายุ 60 วัน)", flows: ["shopee", "story"], need: "auto" },
  { name: "META_APP_ID", purpose: "แอป Meta", flows: ["shopee", "story"], need: "auto" },
  { name: "META_APP_SECRET", purpose: "แอป Meta", flows: ["shopee", "story"], need: "auto" },
];
