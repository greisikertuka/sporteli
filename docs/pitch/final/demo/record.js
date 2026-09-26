// Records the Sportel demo video (see ../VIDEO-SCRIPT.md) against a running app.
// Needs: API on :8000, web on :3000, puppeteer-core, Chrome, and FFMPEG pointing at an ffmpeg binary.
//   curl -X POST http://localhost:8000/api/v1/demo/reset
//   FFMPEG=/path/to/ffmpeg node record.js
const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const BASE = "http://localhost:3000";
const CSV = path.join(__dirname, "mbetjet_jan-gus_2026_SINTETIKE.csv");
const OUT = path.join(__dirname, "sportel-demo.mp4");
const FRAMES = path.join(require("os").tmpdir(), "sportel-frames");
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// On-screen cursor, click ripple and caption bar, injected into every document.
const OVERLAY = () => {
  const css = `
    #demo-cursor{position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
      background:rgba(28,43,90,.85);border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.35);z-index:2147483647;pointer-events:none;
      transition:transform .12s}
    #demo-cursor.down{transform:scale(.7)}
    .demo-ripple{position:fixed;width:60px;height:60px;margin:-30px 0 0 -30px;border-radius:50%;border:3px solid #08B3AE;
      z-index:2147483646;pointer-events:none;animation:demo-r .6s ease-out forwards}
    @keyframes demo-r{from{opacity:1;transform:scale(.2)}to{opacity:0;transform:scale(1.4)}}
    #demo-caption{position:fixed;left:50%;bottom:34px;transform:translateX(-50%);max-width:1180px;padding:16px 30px;
      background:rgba(28,43,90,.94);color:#fff;font:600 26px/1.3 Arial,sans-serif;border-radius:14px;text-align:center;
      box-shadow:0 8px 30px rgba(0,0,0,.25);z-index:2147483645;pointer-events:none;opacity:0;transition:opacity .35s}
    #demo-caption.on{opacity:1}`;
  const init = () => {
    if (document.getElementById("demo-cursor")) return;
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    const c = document.createElement("div"); c.id = "demo-cursor"; document.body.appendChild(c);
    const cap = document.createElement("div"); cap.id = "demo-caption"; document.body.appendChild(cap);
    const pos = window.__demoPos || { x: 800, y: 450 };
    c.style.left = pos.x + "px"; c.style.top = pos.y + "px";
    document.addEventListener("mousemove", (e) => { window.__demoPos = { x: e.clientX, y: e.clientY }; c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
    document.addEventListener("mousedown", (e) => {
      c.classList.add("down");
      const r = document.createElement("div"); r.className = "demo-ripple"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
      document.body.appendChild(r); setTimeout(() => r.remove(), 700);
    }, true);
    document.addEventListener("mouseup", () => c.classList.remove("down"), true);
    window.__caption = (t) => { cap.textContent = t || ""; cap.classList.toggle("on", !!t); };
    if (window.__pendingCaption) window.__caption(window.__pendingCaption);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
};

(async () => {
  fs.rmSync(FRAMES, { recursive: true, force: true });
  fs.mkdirSync(FRAMES, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: "new",
    defaultViewport: { width: 1600, height: 900, deviceScaleFactor: 1.2 },
  });
  const page = await browser.newPage();
  await page.setCookie({ name: "NEXT_LOCALE", value: "en", domain: "localhost", path: "/" });
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);

  // Warm up every route (Next dev compiles on first visit) before the camera rolls.
  for (const r of ["/", "/ask", "/ingest"]) await page.goto(BASE + r, { waitUntil: "networkidle0" });
  await page.evaluateOnNewDocument(OVERLAY);
  await page.goto(BASE + "/", { waitUntil: "networkidle0" });
  await page.waitForFunction(() => /missing export/i.test(document.body.innerText), { timeout: 60000 });
  await sleep(800);

  // ---------------------------------------------------------------- helpers
  let mouse = { x: 800, y: 450 };
  const caption = async (t) => { console.log("·", t); await page.evaluate((t) => { window.__pendingCaption = t; window.__caption && window.__caption(t); }, t); };
  async function locate(sel, text, { exact = false, last = true } = {}) {
    const h = await page.waitForFunction((sel, text, exact, last) => {
      const hit = (e) => { const tx = e.textContent.trim(); return exact ? tx === text : tx.includes(text); };
      // innermost visible matches only (an ancestor also "contains" the text)
      const els = [...document.querySelectorAll(sel)].filter((e) =>
        e.offsetParent && hit(e) && ![...e.querySelectorAll(sel)].some((c) => c.offsetParent && hit(c)));
      return els.length ? els[last ? els.length - 1 : 0] : null;
    }, { timeout: 30000 }, sel, text, exact, last).catch((e) => { throw new Error("locate failed: " + text); });
    return h.asElement();
  }
  async function reveal(el) {
    await el.evaluate((e) => e.scrollIntoView({ behavior: "smooth", block: "center" }));
    await sleep(900);
  }
  async function moveTo(el, ms = 700) {
    const b = await el.boundingBox();
    const x = b.x + Math.min(b.width / 2, 160), y = b.y + b.height / 2;
    await page.mouse.move(x, y, { steps: Math.max(12, Math.round(ms / 16)) });
    mouse = { x, y };
  }
  async function click(sel, text, opts) {
    const el = await locate(sel, text, opts);
    await reveal(el); await moveTo(el); await sleep(250);
    await page.mouse.down(); await sleep(90); await page.mouse.up();
    await el.evaluate((e) => e.click());
    return el;
  }
  async function scrollBy(dy) { await page.evaluate((dy) => window.scrollBy({ top: dy, behavior: "smooth" }), dy); await sleep(1000); }
  async function nav(label) { await click("a", label, { last: false }); await sleep(1500); }

  // ---------------------------------------------------------------- recording
  const cdp = await page.createCDPSession();
  const frames = [];
  cdp.on("Page.screencastFrame", async (f) => {
    const file = path.join(FRAMES, `f${String(frames.length).padStart(5, "0")}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, "base64"));
    frames.push({ file, t: f.metadata.timestamp });
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  await page.mouse.move(800, 450);

  // 1 · Board with the gap
  await caption("Head of Public Services: 6 of 13 indicators have proof. Waste has no data yet.");
  await sleep(1500);
  const psd = await locate("a,button,li,div", "Cleaning and waste collection", { last: true });
  await moveTo(psd, 1200);
  await sleep(2200);
  const gapTile = await locate("article.tile", "Waste per resident", { last: false });
  await reveal(gapTile); await moveTo(gapTile, 900);
  await sleep(2200);

  // 2 · Ask: not answerable, owner named
  await nav("Ask the data");
  await caption("Sportel does not guess. It names the missing export and who owns it.");
  await click("button", "How many kilograms of waste per resident per year");
  await sleep(1500);
  const na = await locate("*", "No number was guessed", { last: true }).catch(() => null);
  if (na) { await reveal(na); await moveTo(na, 800); }
  await sleep(3500);

  // 3 · Upload the hand-built file
  await nav("Integrate data");
  await caption("Upload the file the directorate already has.");
  await sleep(800);
  const chooserBtn = await locate("button,label", "Choose a file");
  await reveal(chooserBtn); await moveTo(chooserBtn, 900); await sleep(300);
  const [chooser] = await Promise.all([page.waitForFileChooser(), (async () => {
    await page.mouse.down(); await sleep(90); await page.mouse.up();
    await chooserBtn.evaluate((e) => e.click());
  })()]);
  await chooser.accept([CSV]);
  const steps = await locate("*", "What the code did");
  await reveal(steps);
  await caption("Code finds the header, the total row and any personal columns.");
  await locate("button", "Confirm and load");
  await sleep(1200);
  const mapHead = await locate("h2,h3,h4,p,div", "Column mapping", { last: false }).catch(() => null);
  if (mapHead) { await mapHead.evaluate((e) => e.scrollIntoView({ behavior: "smooth", block: "start" })); await sleep(1000); }
  await caption("The AI read column names only. No values left the server.");
  await sleep(3000);
  // Amber rows (AI unsure) need a click; the AI's confidence varies run to run.
  const amber = await page.$$eval("button", (bs) =>
    bs.filter((b) => /^Confirm( all.*)?$/.test(b.textContent.trim()) && !b.disabled && b.offsetParent).map((b) => b.textContent.trim()));
  if (amber.length) {
    await caption("Where the AI is unsure, a person confirms.");
    if (amber.some((t) => t.startsWith("Confirm all"))) await click("button", "Confirm all");
    else await click("button", "Confirm", { exact: true });
    await sleep(1200);
  } else {
    await caption("A person checks the mapping, then loads the file.");
    await sleep(2000);
  }
  await click("button", "Confirm and load");
  const receipt = await locate("*", "Load receipt");
  await sleep(800);
  await reveal(receipt);
  await caption("Every row counted. The totals match the file's own total.");
  await scrollBy(260);
  await sleep(3200);

  // 4 · Board: the KPI is no longer empty
  await nav("Board");
  await page.evaluate(() => window.scrollTo(0, 0));
  await caption("The waste KPIs are no longer empty, and each has its proof.");
  await sleep(1200);
  const tile = await locate("article.tile", "Waste per resident", { last: false });
  await reveal(tile); await moveTo(tile, 1000);
  await sleep(3500);

  // 5 · Same question, now verified
  await nav("Ask the data");
  await caption("Same question: verified, with the exact source rows.");
  await click("button", "How many kilograms of waste per resident per year");
  await sleep(2500);
  const src = await locate("*", "Sources", { last: true }).catch(() => null);
  await scrollBy(250);
  await sleep(2200);
  if (src) { await reveal(src); await moveTo(src, 800); }
  await sleep(3000);

  await caption("Sportel · Report once, prove every number.");
  await sleep(3000);
  await cdp.send("Page.stopScreencast");
  await browser.close();

  // ---------------------------------------------------------------- encode
  const list = [];
  for (let i = 0; i < frames.length; i++) {
    const d = i + 1 < frames.length ? Math.max(0.001, frames[i + 1].t - frames[i].t) : 1.5;
    list.push(`file '${frames[i].file.replace(/\\/g, "/")}'`, `duration ${d.toFixed(3)}`);
  }
  list.push(`file '${frames[frames.length - 1].file.replace(/\\/g, "/")}'`);
  const listFile = path.join(FRAMES, "list.txt");
  fs.writeFileSync(listFile, list.join("\n"));
  execFileSync(process.env.FFMPEG || "ffmpeg", ["-y", "-f", "concat", "-safe", "0", "-i", listFile,
    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white,fps=30,format=yuv420p",
    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-movflags", "+faststart", OUT], { stdio: "inherit" });
  console.log(`frames: ${frames.length} → ${OUT}`);
})().catch((e) => { console.error(e); process.exit(1); });
