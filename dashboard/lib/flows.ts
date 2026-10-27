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
  hoursVar?: string; // GitHub variable with the Bangkok posting hours ("9,13,19"); the workflow runs hourly and gates on it
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
      { file: "daily-video.yml", role: "สร้างและส่งวิดีโอ", primary: true, cron: "0 2 * * *", scheduleLabel: "ทุกวัน 09:00 น.", hoursVar: "SHOP_POST_HOURS" },
    ],
    steps: [
      { key: "input", label: "สินค้า", tool: "คิวสินค้าในเว็บนี้", service: "store" },
      { key: "script", label: "บทขาย", tool: "Claude (หรือ Gemini ถ้ายังไม่ใส่ key)", service: "gateway" },
      { key: "visual", label: "ภาพ", tool: "รูปสินค้า + Ken Burns", service: "local" },
      { key: "voice", label: "เสียง", tool: "ElevenLabs v4 · เสียงคนไทย", service: "elevenlabs" },
      { key: "render", label: "ตัดต่อ", tool: "FFmpeg + คำบรรยายไทย", service: "ffmpeg" },
      { key: "deliver", label: "ส่ง", tool: "หน้ารีวิว + Telegram", service: "telegram" },
    ],
    publishVar: "PUBLISH_MODE",
    queueTab: "Inbox",
    costNote: "≈ $0.03 ต่อคลิปเมื่อใช้ Claude (เสียงใช้เครดิต ElevenLabs ที่จ่ายรายปีแล้ว)",
  },
  {
    id: "story",
    name: "คลิปเล่าเรื่อง",
    short: "Flow B",
    tagline: "ธีมสัตว์ไทย (ปัจจุบัน) หรือประวัติศาสตร์การเมือง · อ้างอิง Wikipedia · มีด่านตรวจเนื้อหาก่อนผลิต",
    workflows: [
      {
        file: "story-video.yml", role: "สร้างและส่งคลิปเล่าเรื่อง", primary: true,
        cron: "0 12 * * *", scheduleLabel: "ทุกวัน 19:00 น.", hoursVar: "STORY_POST_HOURS", inputs: { topic: true },
      },
    ],
    steps: [
      { key: "input", label: "หัวข้อ", tool: "คิวหัวข้อในเว็บนี้", service: "store" },
      { key: "script", label: "บท + ตรวจเนื้อหา", tool: "Claude + Wikipedia · ด่านตรวจความเป็นกลาง", service: "gateway" },
      { key: "visual", label: "ภาพ", tool: "ภาพจริง Wikimedia · แผนที่ดาวเทียม · การ์ดปี พ.ศ.", service: "wikimedia" },
      { key: "voice", label: "เสียง", tool: "ElevenLabs v4 · เสียงคนไทย", service: "elevenlabs" },
      { key: "render", label: "ตัดต่อ", tool: "กล้องเคลื่อน + แผนที่ + ดนตรีตามธีม + เสียงเปลี่ยนฉาก", service: "ffmpeg" },
      { key: "deliver", label: "ส่ง", tool: "หน้ารีวิว + Telegram", service: "telegram" },
    ],
    publishVar: "STORY_PUBLISH_MODE",
    queueTab: "Stories",
    costNote: "≈ $0.10 ต่อคลิปเมื่อใช้ Claude Opus 5.5 (คีย์ของคุณ)",
  },
];

/** Posts one approved review video (dispatched by the approve button). */
export const POST_VIDEO_WORKFLOW = "post-video.yml";
export const WORKFLOW_FILES = [...FLOWS.flatMap((f) => f.workflows.map((w) => w.file)), POST_VIDEO_WORKFLOW];

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

/** Series label each STORY_THEME uses when none is set (mirrors pipeline/config.py). */
export const THEME_SERIES: Record<string, string> = { wildlife: "สัตว์ไทยน่ารู้", politics: "ย้อนรอยการเมืองไทย", money: "ลองดูสิ…ถ้าทำแบบนี้" };

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
    name: "SHOP_POST_HOURS", label: "จำนวนและเวลาโพสต์ต่อวัน", scope: "shopee", kind: "select",
    workflowDefault: "9",
    help: "เวลาไทย ระบบเช็กทุกชั่วโมงแล้วทำคลิปเมื่อถึงเวลาที่เลือก (อาจช้ากว่าเวลาจริง 5–20 นาที) · แต่ละรอบใช้สินค้าหนึ่งชิ้นจากคิว",
    options: [
      { value: "9", label: "วันละ 1 · 09:00" },
      { value: "12", label: "วันละ 1 · 12:00" },
      { value: "19", label: "วันละ 1 · 19:00" },
      { value: "9,19", label: "วันละ 2 · 09:00, 19:00" },
      { value: "12,20", label: "วันละ 2 · 12:00, 20:00" },
      { value: "9,13,19", label: "วันละ 3 · 09:00, 13:00, 19:00" },
      { value: "8,12,20", label: "วันละ 3 · 08:00, 12:00, 20:00" },
      { value: "99", label: "พัก · ไม่โพสต์ตามเวลา", hint: "สั่งรันเองได้" },
    ],
  },
  {
    name: "STORY_POST_HOURS", label: "จำนวนและเวลาโพสต์ต่อวัน", scope: "story", kind: "select",
    workflowDefault: "19",
    help: "เวลาไทย ใช้กับเพจที่ยังไม่ได้ตั้งเวลาของตัวเองในแท็บเพจ & ช่องทาง · ระบบเช็กทุกชั่วโมง (อาจช้ากว่าเวลาจริง 5–20 นาที) · แต่ละรอบใช้หัวข้อหนึ่งเรื่อง",
    options: [
      { value: "19", label: "วันละ 1 · 19:00" },
      { value: "12", label: "วันละ 1 · 12:00" },
      { value: "20", label: "วันละ 1 · 20:00" },
      { value: "12,19", label: "วันละ 2 · 12:00, 19:00" },
      { value: "8,19", label: "วันละ 2 · 08:00, 19:00" },
      { value: "8,12,19", label: "วันละ 3 · 08:00, 12:00, 19:00" },
      { value: "9,13,20", label: "วันละ 3 · 09:00, 13:00, 20:00" },
      { value: "99", label: "พัก · ไม่โพสต์ตามเวลา", hint: "สั่งรันเองได้" },
    ],
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
    name: "STORY_THEME", label: "ธีมเนื้อหา", scope: "story", kind: "segmented",
    workflowDefault: "wildlife",
    help: "เปลี่ยนแล้วบท คำถามหัวข้อใหม่ เพลง และกฎตรวจเนื้อหาเปลี่ยนตามทั้งหมด · ล้างชื่อซีรีส์/แนวเนื้อหาด้านล่างให้ใช้ค่าของธีม",
    options: [
      { value: "wildlife", label: "สัตว์ & ธรรมชาติไทย" },
      { value: "politics", label: "ประวัติศาสตร์การเมือง", hint: "ควรตรวจก่อนโพสต์" },
      { value: "money", label: "เงินทองจำลอง", hint: "สถานการณ์จำลอง" },
    ],
  },
  {
    name: "STORY_SERIES_NAME", label: "ชื่อซีรีส์ (ป้ายบนคลิป)", scope: "story", kind: "text",
    workflowDefault: "สัตว์ไทยน่ารู้",
    help: "แสดงเป็นป้ายมุมบนของทุกฉาก และใช้ในข้อความโพสต์",
  },
  {
    name: "STORY_NICHE", label: "แนวเนื้อหา", scope: "story", kind: "text",
    workflowDefault: "ค่าของธีมที่เลือก",
    help: "ใช้ตอนคิวว่างแล้ว AI เสนอหัวข้อใหม่เอง · ว่างไว้ = ใช้แนวของธีมที่เลือก · ระบบตัดเนื้อหาเกี่ยวกับสถาบันฯ ออกเสมอทุกธีม",
  },
  {
    name: "STORY_STYLE_MIX", label: "สไตล์การตัดต่อ", scope: "story", kind: "select",
    workflowDefault: "classic:80,reaction:20",
    help: "สุ่มสไตล์ต่อคลิปตามสัดส่วน · classic = แบบเดิม · reaction = ตัวละครรีแอ็กชันมุมจอ ป้ายตัวเลขเด้ง ซับตัวใหญ่ ซูมกระแทก · ข้อมูล แผนที่ และภาพจริงเหมือนเดิมทุกสไตล์ · เทียบยอดวิวแต่ละสไตล์ได้ในหน้าสถิติ",
    options: [
      { value: "classic:100", label: "แบบเดิมทั้งหมด" },
      { value: "classic:80,reaction:20", label: "เดิม 80% · reaction 20%" },
      { value: "classic:50,reaction:50", label: "เดิม 50% · reaction 50%" },
      { value: "reaction:100", label: "reaction ทั้งหมด" },
    ],
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
    workflowDefault: "wikimedia",
    help: "ค่าเริ่มต้นใช้ภาพจริงจาก Wikimedia เท่านั้น ไม่ใช้ภาพ AI ของบุคคลหรือเหตุการณ์จริง ถ้าหาภาพไม่ได้จะใช้การ์ดกราฟิกแทน",
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
    help: "ใช้เฉพาะตอนที่ยังไม่ได้ใส่ Claude key — รุ่นที่ AI Gateway free tier เรียกได้",
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
    help: "ใช้เฉพาะตอนที่ยังไม่ได้ใส่ Claude key (Flow A)",
    options: [
      { value: "google/gemini-2.5-flash-lite", label: "Gemini 2.5 Flash-Lite", hint: "ค่าเริ่มต้น" },
      { value: "openai/gpt-4.1-mini", label: "GPT-4.1 mini" },
      { value: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    ],
  },
  {
    name: "CLAUDE_MONTHLY_BUDGET", label: "งบ Claude ต่อเดือน (USD)", scope: "shared", kind: "text",
    workflowDefault: "100",
    help: "ใช้แสดงในการ์ดสถานะบริการเท่านั้น ไม่ได้ตัดการใช้งาน · Opus 5.5 คิด $4 / $20 ต่อล้าน token (เข้า/ออก) ≈ $0.3–0.6 ต่อคลิปเล่าเรื่อง",
  },
  {
    name: "CLAUDE_MODEL", label: "โมเดล Claude", scope: "shared", kind: "select",
    workflowDefault: "claude-opus-5-5",
    help: "ใช้เขียนบท วางช็อตแผนที่ และคิดหัวข้อ ทั้งสอง flow เมื่อใส่ Claude key แล้ว",
    options: [
      { value: "claude-opus-5-5", label: "Claude Opus 5.5", hint: "คุณภาพสูงสุด ≈ $0.10/คลิป" },
      { value: "claude-sonnet-5-5", label: "Claude Sonnet 5.5", hint: "≈ $0.05/คลิป" },
      { value: "claude-haiku-5-5", label: "Claude Haiku 5.5", hint: "ประหยัดสุด" },
    ],
  },
  {
    name: "STORY_VOICE_ID", label: "เสียงผู้บรรยาย", scope: "story", kind: "select",
    workflowDefault: "random",
    help: "เสียงคนไทยจาก ElevenLabs Voice Library (โมเดล eleven_v4) · สุ่ม = เปลี่ยนผู้บรรยายชาย/หญิงทุกคลิป",
    options: [
      { value: "random", label: "สุ่มทุกคลิป — ชายบ้าง หญิงบ้าง", hint: "แนะนำ" },
      { value: "jucSqawHKM1rUNf78oZQ", label: "Duang — ผู้ชาย เล่าเรื่องเสียงทุ้ม" },
      { value: "7XW5JhaNn90bnFojQ5DA", label: "Mali — ผู้หญิง ชัด เป็นธรรมชาติ" },
      { value: "yq05eeRaHPMGuWTVpqeP", label: "Tonce — ผู้ชาย เป็นกันเอง" },
      { value: "MYZYcGOqrkYQcwDunXl7", label: "Hammy — ผู้หญิง อบอุ่น เป็นกันเอง" },
    ],
  },
  {
    name: "STORY_TARGET_SECONDS", label: "ความยาวคลิป", scope: "story", kind: "segmented",
    workflowDefault: "75",
    help: "เพจแผนที่ที่ยอดวิวสูงทำคลิปยาว 1–2 นาที · ยาวขึ้น = ใช้เครดิตเสียงมากขึ้น (~13 ตัวอักษร/วินาที)",
    options: [
      { value: "45", label: "45 วิ" },
      { value: "60", label: "60 วิ" },
      { value: "75", label: "75 วิ" },
      { value: "90", label: "90 วิ" },
    ],
  },
  {
    name: "SHOP_VOICE_ID", label: "เสียงพากย์", scope: "shopee", kind: "select",
    workflowDefault: "7XW5JhaNn90bnFojQ5DA",
    help: "เสียงคนไทยจาก ElevenLabs Voice Library (โมเดล eleven_v4)",
    options: [
      { value: "7XW5JhaNn90bnFojQ5DA", label: "Mali — ผู้หญิง ชัด เป็นธรรมชาติ", hint: "แนะนำ" },
      { value: "yq05eeRaHPMGuWTVpqeP", label: "Tonce — ผู้ชาย เป็นกันเอง" },
      { value: "jucSqawHKM1rUNf78oZQ", label: "Duang — ผู้ชาย เสียงทุ้ม" },
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
  need: "required" | "auto" | "recommended";
}

export const SECRETS: SecretDef[] = [
  { name: "PIPELINE_API_KEY", purpose: "ให้ pipeline คุยกับเว็บนี้ (คิว + ส่งวิดีโอรีวิว)", flows: ["shopee", "story"], need: "required" },
  { name: "ANTHROPIC_API_KEY", purpose: "Claude เขียนบทและวางช็อต (ใส่ที่การ์ด AI & เสียง)", flows: ["shopee", "story"], need: "recommended" },
  { name: "AI_GATEWAY_API_KEY", purpose: "AI สำรองเมื่อไม่มี Claude key", flows: ["shopee", "story"], need: "required" },
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
