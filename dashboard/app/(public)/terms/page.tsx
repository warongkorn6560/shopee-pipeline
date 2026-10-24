import type { Metadata } from "next";
import { CONTACT } from "@/lib/brand";

export const metadata: Metadata = { title: { absolute: "Terms of Service · แผนที่สัตว์ไทย" }, robots: { index: true, follow: true } };

export default function Terms() {
  return (
    <>
      <h1>Terms of Service · ข้อกำหนดการใช้งาน</h1>
      <p className="text-sm text-ink-3">Last updated: 24 October 2026</p>

      <h2>1. The service</h2>
      <p>
        แผนที่สัตว์ไทย is a private tool operated by a single creator to produce short educational videos about Thai
        wildlife and to publish them to the creator&apos;s own Facebook Page, Instagram and TikTok accounts. Access to the
        tool is password-protected and limited to its owner.
      </p>

      <h2>2. Content</h2>
      <ul>
        <li>All videos are created by the owner. Facts are drawn from cited public sources (Wikipedia).</li>
        <li>Images come from Wikimedia Commons under public-domain or Creative Commons licences, credited on screen, or are maps and graphics made by the owner.</li>
        <li>Each video is reviewed or published under the owner&apos;s responsibility and in line with each platform&apos;s community guidelines.</li>
      </ul>

      <h2>3. Third-party platforms</h2>
      <p>
        Publishing uses the official TikTok, Meta and Instagram APIs. Use of those platforms is also governed by their
        own terms. The tool only acts on accounts that the owner has connected and can disconnect at any time.
      </p>

      <h2>4. No warranty</h2>
      <p>The tool is provided as is. Educational content may be updated or corrected when better sources are found.</p>

      <h2>5. Contact</h2>
      <p>
        Questions, corrections or takedown requests: <a href={`mailto:${CONTACT}`}>{CONTACT}</a>
      </p>

      <h2>สรุปภาษาไทย</h2>
      <p>
        เว็บนี้เป็นเครื่องมือส่วนตัวของผู้สร้างคลิปคนเดียว ใช้ทำคลิปความรู้เรื่องสัตว์ป่าไทยและโพสต์ลงบัญชีของตัวเอง
        ข้อมูลอ้างอิงจากแหล่งสาธารณะ ภาพใช้สัญญาอนุญาตที่ถูกต้องและให้เครดิตทุกภาพ แจ้งแก้ไขหรือขอให้นำออกได้ทางอีเมลด้านบน
      </p>
    </>
  );
}
