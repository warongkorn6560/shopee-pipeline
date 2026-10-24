import type { Metadata } from "next";
import { CONTACT } from "@/lib/brand";

export const metadata: Metadata = { title: { absolute: "Privacy Policy · แผนที่สัตว์ไทย" }, robots: { index: true, follow: true } };

export default function Privacy() {
  return (
    <>
      <h1>Privacy Policy · นโยบายความเป็นส่วนตัว</h1>
      <p className="text-sm text-ink-3">Last updated: 24 October 2026</p>

      <p>
        แผนที่สัตว์ไทย (&quot;the tool&quot;) is a private publishing tool used by one creator to post their own videos to
        their own social media accounts. It has no public sign-up and no other users.
      </p>

      <h2>Data we access</h2>
      <ul>
        <li>
          <b>TikTok (Login Kit, Content Posting API)</b>: with the <code>user.info.basic</code> scope we read the account&apos;s
          open_id and display name, only to show which account is connected. With <code>video.publish</code> we upload
          videos that the account owner created and chose to publish, to that same account. We do not read followers,
          messages, other videos, or any other user&apos;s data.
        </li>
        <li>
          <b>Meta (Facebook Pages, Instagram)</b>: we read the names and IDs of the Pages / Instagram professional account
          the owner selects, and publish the owner&apos;s own videos (Reels) to them. We do not read messages, comments or
          personal profile data.
        </li>
      </ul>

      <h2>How we store it</h2>
      <ul>
        <li>Access tokens are encrypted (AES-256-GCM) and kept in private storage and in encrypted CI secrets.</li>
        <li>Data is used only to publish the owner&apos;s videos. It is never sold, shared with third parties, or used for advertising.</li>
        <li>Rendered videos are kept for up to 30 days for review, then deleted.</li>
      </ul>

      <h2>Deleting your data</h2>
      <p>
        Disconnect the account in the tool&apos;s Settings page (this deletes the stored tokens), or revoke access from the
        platform (TikTok: Settings → Security → Manage app permissions; Facebook: Settings → Business integrations).
        You can also email us and we will delete everything within 7 days.
      </p>

      <h2>สรุปภาษาไทย</h2>
      <p>
        เครื่องมือนี้ใช้โดยผู้สร้างคลิปคนเดียว เพื่อโพสต์คลิปของตัวเองลงบัญชีของตัวเอง เราอ่านเฉพาะรหัสบัญชีและชื่อที่แสดง
        เพื่อแสดงว่าเชื่อมบัญชีไหนอยู่ และใช้สิทธิ์โพสต์คลิปเท่านั้น token ถูกเข้ารหัส ไม่ขายหรือแบ่งปันให้ใคร
        ยกเลิกการเชื่อมในหน้าตั้งค่า หรืออีเมลมาเพื่อให้ลบข้อมูลทั้งหมดได้
      </p>

      <h2>Contact</h2>
      <p><a href={`mailto:${CONTACT}`}>{CONTACT}</a></p>
    </>
  );
}
