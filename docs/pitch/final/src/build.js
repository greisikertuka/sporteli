// Sportel final pitch deck v2 — minimal text, big type (readable from the back of the room).
// Run from a folder with pptxgenjs, sharp, react, react-dom, react-icons installed:
//   node build.js ../FirmatGroup_Final.pptx
const pptxgen = require("pptxgenjs");
const React = require("react");
const RDS = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const path = require("path");
const N = require("./notes.js");

const OUT = process.argv[2] || "FirmatGroup_Final.pptx";
const ASSETS = path.join(__dirname, "..", "..", "assets");
const AI4S_LOGO = path.join(ASSETS, "ai4society-logo.png");
const SPORTEL_ICON = path.join(ASSETS, "sportel-icon.png");
const SCREEN = (name) => path.join(ASSETS, "screens", name + ".png"); // English UI, synthetic data

const NAVY = "1C2B5A", NAVY2 = "27376B", TEAL = "08B3AE", TEAL_D = "0B8F8B", MINT = "EFF9F8",
  ICE = "D6DEF2", SOFT = "F1F5FB", GREY = "6B7280", LINE = "E5E7EB", WHITE = "FFFFFF",
  RED = "C2410C", REDBG = "FFF1E8", GREEN = "15803D", GREENBG = "E8F7EE", AMBER = "B45309",
  AMBERBG = "FEF3C7", INK = "1F2937", LIGHT = "7CE8E3";
const HF = "Arial";

async function icon(name, color) {
  const svg = RDS.renderToStaticMarkup(React.createElement(fa[name], { color: "#" + color, size: 256 }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5, as the AI4Society template
  pres.title = "Sportel — Final pitch";
  pres.company = "FirmatGroup";
  const W = 13.333;
  let n = 0;

  const T = (s, t, x, y, w, h, o = {}) =>
    s.addText(t, Object.assign({ x, y, w, h, fontFace: HF, fontSize: 20, color: INK, margin: 0, valign: "top", isTextBox: true }, o));
  const box = (s, x, y, w, h, fill, o = {}) =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: o.r ?? 0.14, line: { color: o.line || fill, width: o.lw || 1 } });
  async function dot(s, name, x, y, d, bg, fg) {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg } });
    const p = d * 0.25;
    s.addImage({ data: await icon(name, fg), x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p });
  }
  // A screenshot centred (contain) inside a white framed box with a soft shadow.
  async function screen(s, name, x, y, w, h, pad = 0.08) {
    const { width, height } = await sharp(SCREEN(name)).metadata();
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: WHITE }, rectRadius: 0.1, line: { color: "CBD5E1", width: 1 },
      shadow: { type: "outer", color: "1C2B5A", opacity: 0.18, blur: 8, offset: 3, angle: 90 } });
    const bw = w - 2 * pad, bh = h - 2 * pad, r = Math.min(bw / width, bh / height);
    const iw = width * r, ih = height * r;
    s.addImage({ path: SCREEN(name), x: x + pad + (bw - iw) / 2, y: y + pad + (bh - ih) / 2, w: iw, h: ih });
  }
  function chrome(s, kicker, title) {
    n++;
    s.background = { color: WHITE };
    s.addImage({ path: AI4S_LOGO, x: 0.5, y: 0.32, w: 1.1, h: 0.636 });
    s.addImage({ path: SPORTEL_ICON, x: 1.85, y: 0.36, w: 0.72, h: 0.558 });
    T(s, String(n).padStart(2, "0"), W - 1.0, 7.0, 0.5, 0.3, { fontSize: 11, bold: true, color: GREY, align: "right" });
    T(s, "Sportel · FirmatGroup", 0.5, 7.0, 5, 0.3, { fontSize: 11, color: GREY });
    if (kicker) T(s, kicker, 0.5, 1.2, 9, 0.4, { fontSize: 18, bold: true, color: TEAL_D });
    if (title) T(s, title, 0.5, 1.6, W - 1.0, 0.9, { fontSize: 40, bold: true, color: NAVY });
  }

  // 1 · Title -------------------------------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "Challenge 02 · Bashkia Elbasan");
    T(s, "Sportel", 0.5, 1.9, 6.8, 1.4, { fontSize: 88, bold: true, color: NAVY });
    T(s, "Every number, with its proof.", 0.5, 3.4, 6.8, 0.8, { fontSize: 34, color: NAVY2 });
    T(s, "Report once, prove every number.", 0.5, 4.35, 6.8, 0.6, { fontSize: 24, italic: true, bold: true, color: TEAL_D });
    await screen(s, "passport", 7.55, 1.3, 5.3, 3.75);
    T(s, "Indicator passport · synthetic data", 7.55, 5.15, 5.3, 0.35, { fontSize: 13, italic: true, color: GREY, align: "center" });
    T(s, "FirmatGroup  ·  AI4Society Hackathon Tirana", 0.5, 5.9, 12, 0.5, { fontSize: 20, bold: true, color: GREY });
    s.addNotes(N[0]);
  }

  // 2 · Problem -----------------------------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "Problem");
    box(s, 0.5, 1.75, W - 1.0, 1.75, MINT);
    T(s, "“How much of our waste cost does the cleaning fee cover?”", 0.9, 1.95, W - 1.8, 1.35, { fontSize: 36, bold: true, color: NAVY, valign: "middle" });
    const stats = [["2", "directorates"], ["2", "Excel files"], ["0", "proof of source"]];
    stats.forEach(([big, lab], i) => {
      const x = 0.5 + i * 4.18, fill = i === 2 ? NAVY : SOFT, fg = i === 2 ? WHITE : NAVY;
      box(s, x, 3.8, 3.98, 1.9, fill);
      T(s, big, x + 0.35, 3.95, 1.4, 1.6, { fontSize: 80, bold: true, color: i === 2 ? LIGHT : TEAL_D, valign: "middle" });
      T(s, lab, x + 1.6, 3.95, 2.3, 1.6, { fontSize: 24, bold: true, color: fg, valign: "middle" });
    });
    T(s, "National indicators: collected once a year.", 0.5, 6.05, W - 1.0, 0.5, { fontSize: 24, color: GREY });
    s.addNotes(N[1]);
  }

  // 3 · Solution + demo ---------------------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "Solution · one flow · synthetic demo data", "From “no answer” to proof");
    const steps = [
      ["NOT ANSWERABLE", REDBG, RED], ["UPLOAD EXCEL", AMBERBG, AMBER],
      ["RECONCILED", SOFT, NAVY], ["VERIFIED", GREENBG, GREEN],
    ];
    const cw = 2.9, gap = 0.21;
    steps.forEach(([stamp, bg, fg], i) => {
      const x = 0.5 + i * (cw + gap);
      box(s, x, 2.55, cw, 0.55, bg, { line: fg, lw: 1.5, r: 0.27 });
      T(s, stamp, x, 2.55, cw, 0.55, { fontSize: 18, bold: true, color: fg, align: "center", valign: "middle", charSpacing: 1 });
      if (i < 3) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + cw + 0.01, y: 2.68, w: 0.19, h: 0.3, fill: { color: GREY }, line: { color: GREY } });
    });
    await screen(s, "gap", 0.5, 3.35, 6.02, 3.0, 0.1);
    await screen(s, "verified", 6.81, 3.35, 6.02, 3.0, 0.1);
    T(s, "Before: names who owes the data", 0.5, 6.45, 6.02, 0.4, { fontSize: 18, bold: true, color: RED, align: "center" });
    T(s, "After: verified, with its source rows", 6.81, 6.45, 6.02, 0.4, { fontSize: 18, bold: true, color: GREEN, align: "center" });
    s.addNotes(N[2]);
  }

  // 4 · Users -------------------------------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "Users", "Who uses it");
    const roles = [
      ["FaUserTie", "Head of department", "decides on evidence", TEAL],
      ["FaUsers", "Department staff", "upload their Excel", NAVY],
      ["FaLandmark", "Mayor’s office + IT", "adopt it", NAVY],
    ];
    for (let i = 0; i < roles.length; i++) {
      const [ic, who, what, dotc] = roles[i], y = 2.7 + i * 1.3;
      await dot(s, ic, 0.5, y, 0.95, dotc, WHITE);
      T(s, who, 1.65, y + 0.02, 3.4, 0.5, { fontSize: 24, bold: true, color: NAVY });
      T(s, what, 1.65, y + 0.5, 3.4, 0.45, { fontSize: 20, color: GREY });
    }
    await screen(s, "board-after", 5.2, 2.6, 7.63, 3.9);
    T(s, "The head of department’s board: whom to ask, what is off track", 5.2, 6.58, 7.63, 0.35, { fontSize: 14, italic: true, color: GREY, align: "center" });
    s.addNotes(N[3]);
  }

  // 5 · How it works + data safety ----------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "How it works", "AI reads. Code counts. You confirm.");
    const tiles = [
      ["FaFont", "AI sees column names only", "No values, no rows"],
      ["FaCalculator", "Code computes every number", "AI never writes one"],
      ["FaServer", "Runs on the municipality’s server", "Data stays inside"],
    ];
    for (let i = 0; i < tiles.length; i++) {
      const [ic, head, sub] = tiles[i], x = 0.5 + i * 4.18, dark = i === 2;
      box(s, x, 2.75, 3.98, 3.3, dark ? NAVY : MINT);
      await dot(s, ic, x + 0.35, 3.05, 1.0, dark ? TEAL : TEAL_D, WHITE);
      T(s, head, x + 0.35, 4.2, 3.35, 1.05, { fontSize: 24, bold: true, color: dark ? WHITE : NAVY });
      T(s, sub, x + 0.35, 5.3, 3.35, 0.5, { fontSize: 20, color: dark ? LIGHT : TEAL_D });
    }
    T(s, "AI provider: zero data retention, EU region, or a local model", 0.5, 6.3, W - 1.0, 0.45, { fontSize: 18, color: GREY });
    s.addNotes(N[4]);
  }

  // 6 · Market ------------------------------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "Market", "Honest arithmetic");
    const m = [["61", "Albanian municipalities", TEAL, WHITE], ["99", "same reporting duty (AL + XK)", MINT, NAVY], ["450+", "Western Balkans", NAVY, WHITE]];
    m.forEach(([big, lab, fill, fg], i) => {
      const x = 0.5 + i * 4.18;
      box(s, x, 2.75, 3.98, 3.2, fill);
      T(s, big, x + 0.35, 2.95, 3.4, 1.6, { fontSize: 96, bold: true, color: fg });
      T(s, lab, x + 0.35, 4.75, 3.4, 1.0, { fontSize: 22, bold: true, color: fg });
    });
    T(s, "Pilot in Elbasan → replicate through the project partners", 0.5, 6.25, W - 1.0, 0.5, { fontSize: 22, color: GREY });
    s.addNotes(N[5]);
  }

  // 7 · What's next + cost ------------------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "What’s next + cost", "Pilot in 4 weeks");
    const weeks = ["Real exports", "Validate formulas", "Municipal server", "Rebuild last year"];
    weeks.forEach((w, i) => {
      const y = 2.75 + i * 0.78;
      s.addShape(pres.shapes.OVAL, { x: 0.5, y, w: 0.6, h: 0.6, fill: { color: TEAL }, line: { color: TEAL } });
      T(s, "W" + (i + 1), 0.5, y, 0.6, 0.6, { fontSize: 16, bold: true, color: WHITE, align: "center", valign: "middle" });
      T(s, w, 1.3, y, 5.2, 0.6, { fontSize: 22, bold: true, color: NAVY, valign: "middle" });
    });
    T(s, "Then", 0.5, 5.95, 1.2, 0.5, { fontSize: 18, bold: true, color: GREY, valign: "middle" });
    ["Logins", "All 52 indicators", "Feed city AI"].forEach((c, i) => {
      const x = [1.45, 2.95, 5.35][i], w = [1.35, 2.25, 2.0][i];
      box(s, x, 5.95, w, 0.5, SOFT, { r: 0.25 });
      T(s, c, x, 5.95, w, 0.5, { fontSize: 15, bold: true, color: NAVY, align: "center", valign: "middle" });
    });
    box(s, 7.6, 2.75, 5.23, 3.7, NAVY);
    const cost = [["Build", "€8–12k"], ["Pilot setup", "€2–4k"], ["Run / month", "< €100"], ["Maintain / year", "€4–6k"]];
    cost.forEach(([k, v], i) => {
      const y = 2.95 + i * 0.85;
      if (i) s.addShape(pres.shapes.LINE, { x: 7.9, y: y - 0.06, w: 4.63, h: 0, line: { color: NAVY2, width: 1 } });
      T(s, k, 7.9, y, 2.6, 0.7, { fontSize: 20, color: ICE, valign: "middle" });
      T(s, v, 10.3, y, 2.23, 0.7, { fontSize: 28, bold: true, color: LIGHT, align: "right", valign: "middle" });
    });
    s.addNotes(N[6]);
  }

  // 8 · Team --------------------------------------------------------------
  {
    const s = pres.addSlide(); chrome(s, "Team", "FirmatGroup");
    const tm = [["FaChartLine", "[Name]", "Problem & users"], ["FaDesktop", "[Name]", "Demo & product"], ["FaLaptopCode", "[Name]", "Data & AI"], ["FaClipboardCheck", "[Name]", "Testing"]];
    const cw = (W - 1.0 - 0.3 * 3) / 4;
    for (let i = 0; i < tm.length; i++) {
      const [ic, name, role] = tm[i], x = 0.5 + i * (cw + 0.3);
      box(s, x, 2.75, cw, 2.15, i % 2 ? SOFT : MINT);
      await dot(s, ic, x + 0.3, 2.95, 0.75, i % 2 ? NAVY : TEAL, WHITE);
      T(s, name, x + 0.3, 3.85, cw - 0.5, 0.45, { fontSize: 22, bold: true, color: NAVY });
      T(s, role, x + 0.3, 4.3, cw - 0.5, 0.45, { fontSize: 18, color: GREY });
    }
    box(s, 0.5, 5.2, W - 1.0, 1.45, NAVY);
    T(s, "Report once, prove every number.", 0.85, 5.2, 7.2, 1.45, { fontSize: 28, bold: true, italic: true, color: WHITE, valign: "middle" });
    T(s, "firmatgrouphq@gmail.com", 8.2, 5.35, 4.3, 0.55, { fontSize: 20, bold: true, color: WHITE, align: "right" });
    T(s, "github.com/greisikertuka/sporteli", 8.2, 5.9, 4.3, 0.5, { fontSize: 16, color: LIGHT, align: "right" });
    s.addNotes(N[7]);
  }

  await pres.writeFile({ fileName: OUT });
  console.log("wrote " + OUT);
})();
