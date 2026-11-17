// Render every shot of a toon3d job to its own mp4.
//   node render.mjs job.json
// The page (index.html + scene.js) runs three.js on software WebGL (SwiftShader) in headless Chromium,
// so it needs no GPU. Each frame is read back as JPEG and piped into ffmpeg.
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const here = dirname(fileURLToPath(import.meta.url));
const job = JSON.parse(readFileSync(process.argv[2], "utf8"));
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript" };
const FILES = {
  "/index.html": join(here, "index.html"),
  "/scene.js": join(here, "scene.js"),
  "/three.module.js": join(here, "node_modules/three/build/three.module.js"),
  "/three.core.js": join(here, "node_modules/three/build/three.core.js"),
};

const browser = await puppeteer.launch({
  headless: "shell",
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
         "--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage();
page.on("console", (m) => { if (!m.text().includes("GL Driver")) console.log(`    [page] ${m.text()}`); });
page.on("pageerror", (e) => console.log(`    [page error] ${e.message}`));
await page.setRequestInterception(true);
page.on("request", (req) => {
  const path = new URL(req.url()).pathname;
  const file = FILES[path];
  if (!file) return req.respond({ status: 404, body: "" });
  req.respond({ status: 200, contentType: TYPES[extname(file)], body: readFileSync(file) });
});
await page.setViewport({ width: 360, height: 640 });
await page.goto("http://toon3d.local/index.html");
await page.waitForFunction("window.ready === true", { timeout: 60000 });
await page.evaluate((j) => window.setup(j), job);

const started = Date.now();
let frames = 0;
for (const [b, beat] of job.beats.entries()) {
  if (!beat.out) continue;
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg",
    "-framerate", String(job.fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
    "-pix_fmt", "yuv420p", beat.out], { stdio: ["pipe", "inherit", "inherit"] });
  const t0 = Date.now();
  for (let f = 0; f < beat.frames; f++) {
    const data = await page.evaluate((bi, fi) => window.draw(bi, fi), b, f);
    const ok = ff.stdin.write(Buffer.from(data.slice(data.indexOf(",") + 1), "base64"));
    if (!ok) await new Promise((r) => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await new Promise((r, x) => ff.on("close", (c) => (c === 0 ? r() : x(new Error(`ffmpeg ${c}`)))));
  frames += beat.frames;
  const ms = (Date.now() - t0) / beat.frames;
  console.log(`    [toon3d] shot ${b + 1}/${job.beats.length} ${beat.shot} ${beat.frames}f · ${ms.toFixed(0)} ms/frame`);
}
console.log(`    [toon3d] ${frames} frames in ${((Date.now() - started) / 1000).toFixed(0)} s`);
await browser.close();
