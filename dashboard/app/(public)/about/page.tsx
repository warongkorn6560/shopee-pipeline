import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { CONTACT } from "@/lib/brand";

export const metadata: Metadata = { title: "แผนที่สัตว์ไทย · Thai Wildlife Map", robots: { index: true, follow: true } };

export default function About() {
  return (
    <>
      <Image src="/brand/logo-256.png" alt="แผนที่สัตว์ไทย logo" width={96} height={96} className="rounded-2xl" />
      <h1>แผนที่สัตว์ไทย · Thai Wildlife Map</h1>
      <p>
        คลิปสารคดีสั้นเรื่องสัตว์ป่าและธรรมชาติไทย สัตว์แต่ละชนิดอยู่ที่ไหน เป็นอย่างไร เล่าผ่านแผนที่จริง ภาพจริง
        และข้อมูลที่อ้างอิงแหล่งที่มาได้ (Wikipedia, Wikimedia Commons) คลิปใหม่ทุกวัน
      </p>
      <p>
        Short documentary videos about Thailand&apos;s wildlife and nature: where each species lives and how it is doing,
        told with real maps, real photos and cited sources (Wikipedia, Wikimedia Commons). New videos every day.
      </p>

      <h2>เครื่องมือนี้ทำอะไร · What this tool does</h2>
      <p>
        เว็บนี้เป็นเครื่องมือส่วนตัวของผู้สร้างคลิปเพียงคนเดียว ใช้ผลิตคลิป ตรวจคลิปก่อนเผยแพร่ และโพสต์คลิปที่ผู้สร้างทำเอง
        ลงบัญชีของผู้สร้างเองบน Facebook Page, Instagram และ TikTok ด้วยการกดครั้งเดียว
      </p>
      <p>
        This website is a private tool for a single creator. It produces the videos, lets the creator review them, and
        publishes the creator&apos;s own videos to the creator&apos;s own Facebook Page, Instagram and TikTok accounts in one
        click. It does not access or post to anyone else&apos;s account.
      </p>

      <h2>ติดตาม · Follow</h2>
      <ul>
        <li><a href="https://www.facebook.com/364496773402558" target="_blank" rel="noreferrer">Facebook: แผนที่สัตว์ไทย</a></li>
        <li><a href="https://www.instagram.com/flickfixsummaries/" target="_blank" rel="noreferrer">Instagram: @flickfixsummaries</a></li>
        <li><a href="https://www.tiktok.com/@flickfixsummaries" target="_blank" rel="noreferrer">TikTok: @flickfixsummaries</a></li>
      </ul>

      <h2>ติดต่อ · Contact</h2>
      <p><a href={`mailto:${CONTACT}`}>{CONTACT}</a></p>
      <p><Link href="/privacy">Privacy Policy</Link> · <Link href="/terms">Terms of Service</Link></p>
    </>
  );
}
