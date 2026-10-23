import "server-only";

// Shopee short links (s.shopee.co.th/…) answer link-preview bots with
// og:image, which gives us the real product photo without scraping.
const PREVIEW_UA = "Twitterbot/1.0";

export async function productImage(url: string): Promise<string> {
  if (!/^https:\/\/(s\.shopee\.co\.th|shopee\.co\.th)\//.test(url)) return "";
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": PREVIEW_UA, "Accept-Language": "th-TH,th;q=0.9" },
      redirect: "follow",
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return "";
    const html = (await res.text()).slice(0, 400_000);
    const m = html.match(/property="og:image"\s+content="([^"]+)"/) ?? html.match(/content="([^"]+)"\s+property="og:image"/);
    return m && m[1].startsWith("https://") ? m[1] : "";
  } catch {
    return "";
  }
}

/** Fill missing photos, a few at a time so Shopee doesn't rate-limit us. */
export async function fillImages<T extends { url: string; image: string }>(items: T[], limit = 40): Promise<number> {
  const todo = items.filter((p) => !p.image && p.url).slice(0, limit);
  let filled = 0;
  for (let i = 0; i < todo.length; i += 4) {
    await Promise.all(
      todo.slice(i, i + 4).map(async (p) => {
        const img = await productImage(p.url);
        if (img) {
          p.image = img;
          filled++;
        }
      }),
    );
  }
  return filled;
}

// ---------------------------------------------------------------------------
// Shopee Affiliate "Batch Product Links" CSV
// Item Id,Item Name,Price,Sales,Shop Name,Commission Rate,Commission,Product Link,Offer Link
// ---------------------------------------------------------------------------
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(cell);
      cell = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      if (row.some((x) => x.trim())) rows.push(row);
      row = [];
      cell = "";
    } else cell += c;
  }
  row.push(cell);
  if (row.some((x) => x.trim())) rows.push(row);
  return rows;
}

/** "1.4พัน" → "1400", "฿259" → "259", "2.3หมื่น" → "23000" */
export function thaiNumber(raw: string): string {
  const s = raw.replace(/[฿,\s]/g, "");
  const n = parseFloat(s);
  if (Number.isNaN(n)) return raw.trim();
  const mult = s.includes("ล้าน") ? 1e6 : s.includes("แสน") ? 1e5 : s.includes("หมื่น") ? 1e4 : s.includes("พัน") ? 1e3 : 1;
  return String(Math.round(n * mult));
}

export interface ImportedProduct {
  name: string;
  price: string;
  commission: string;
  sales: string;
  url: string;
  notes: string;
}

export function parseAffiliateCsv(text: string): ImportedProduct[] {
  const rows = parseCsv(text.replace(/^﻿/, ""));
  if (rows.length < 2) return [];
  const head = rows[0].map((h) => h.trim().toLowerCase());
  const col = (...names: string[]) => head.findIndex((h) => names.includes(h));
  const iName = col("item name", "name", "product name", "ชื่อสินค้า");
  const iPrice = col("price", "price_thb", "ราคา");
  const iSales = col("sales", "ยอดขาย");
  const iRate = col("commission rate", "commission_pct", "commission %");
  const iAmount = col("commission");
  const iOffer = col("offer link", "affiliate_url", "affiliate url");
  const iProduct = col("product link");
  const iShop = col("shop name");
  if (iName < 0 || (iOffer < 0 && iProduct < 0)) return [];
  return rows.slice(1).map((r) => {
    const get = (i: number) => (i >= 0 ? (r[i] ?? "").trim() : "");
    return {
      name: get(iName),
      price: thaiNumber(get(iPrice)),
      commission: get(iRate).replace("%", ""),
      sales: thaiNumber(get(iSales)),
      url: get(iOffer) || get(iProduct),
      notes: [get(iShop) && `ร้าน ${get(iShop)}`, get(iAmount) && `คอมฯ ${get(iAmount)}/ชิ้น`].filter(Boolean).join(" · "),
    };
  }).filter((p) => p.name && /^https?:\/\//.test(p.url));
}
