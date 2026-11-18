import type { Metadata } from "next";
import shelf from "@/lib/shelf.json";

// The Instagram bio link: captions there are not clickable, so every product from the clips lives here.
// Source of truth is pipeline/story/shelf.json (copied by `python -m pipeline.story.shelf`).
export const metadata: Metadata = { title: { absolute: "ของจากคลิป · แผนที่สัตว์ไทย" }, robots: { index: false, follow: false } };

export default function Shop() {
  return (
    <>
      <h1>ของจากคลิป 🛒</h1>
      <p>ของที่เกี่ยวกับสัตว์ในคลิปของช่อง กดแล้วไปที่ Shopee</p>
      <ul className="!list-none !pl-0 space-y-2">
        {shelf.items.map((i) => (
          <li key={i.url}>
            <a href={i.url} target="_blank" rel="noreferrer sponsored"
               className="block rounded-xl border border-line px-4 py-3 !no-underline hover:bg-bg">
              {i.label || i.name}
            </a>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink-3">ลิงก์ affiliate — ช่องได้ค่าคอมเล็กน้อยเมื่อสั่งผ่านลิงก์ ราคาไม่เพิ่มสำหรับคุณ</p>
    </>
  );
}
