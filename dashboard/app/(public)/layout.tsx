import Image from "next/image";
import Link from "next/link";
import { CONTACT } from "@/lib/brand";

// Public pages (no sign-in): what the project is, privacy and terms.
// Required by the TikTok / Meta app reviews.
export default function PublicLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="min-h-full bg-bg">
      <header className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-6">
        <Link href="/about" className="flex items-center gap-3">
          <Image src="/brand/logo-256.png" alt="" width={40} height={40} className="rounded-xl" />
          <span className="font-display text-lg font-semibold text-ink">แผนที่สัตว์ไทย</span>
        </Link>
        <nav className="flex gap-4 text-sm text-ink-2">
          <Link href="/privacy" className="hover:text-ink">Privacy</Link>
          <Link href="/terms" className="hover:text-ink">Terms</Link>
        </nav>
      </header>
      <main className="mx-auto max-w-3xl px-4 pb-16">
        <article className="space-y-5 rounded-2xl border border-line bg-surface p-6 text-[15px] leading-relaxed text-ink-2 shadow-card sm:p-8 [&_h1]:font-display [&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:text-ink [&_h2]:pt-2 [&_h2]:font-display [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-ink [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5 [&_a]:text-ink [&_a]:underline">
          {children}
        </article>
        <p className="mt-6 text-center text-xs text-ink-3">© 2026 แผนที่สัตว์ไทย · Contact: <a href={`mailto:${CONTACT}`} className="underline">{CONTACT}</a></p>
      </main>
    </div>
  );
}
