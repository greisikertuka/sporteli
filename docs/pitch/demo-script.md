# Sportel demo script: the gap-to-proof loop (about 95 seconds) and the 5-minute pitch

This script is adapted from research report §5.2, §7.1 and §7.3 to the routes and labels that
exist in the app now. The Albanian UI strings are quoted verbatim from `web/messages/sq.json`
and from the API's own answers. The narration is in English and the UI stays in Albanian.

**Rule for numbers.** Say only what the screen shows. Where this script writes *read from
screen*, read the value off the screen at that moment. Never quote a number from memory or from
a rehearsal.

**Roles.** Tech B drives the laptop and narrates the demo. Domain presents the problem, scale and
next steps. Tech A stands by at the terminal for resets and fallbacks and takes technical Q&A.
Product keeps time and holds the fallback video and slide 4.

---

## 1. Decide the honesty frame before going on stage

Check the two badges in the header:

- the data badge: **Të dhëna sintetike**;
- the AI badge: **AI LIVE** or **RREGULLA**.

Then use the matching lines, and only those.

| Situation | Say |
|---|---|
| Synthetic files (today's state) | "These are synthetic department exports that our script generated, labelled SINTETIKE on every file and on screen. The organisers' package goes through exactly the same pipeline. No saved mapping exists for these files: the recipe store is empty." |
| Organisers' package files, if loaded before the pitch | "These are files from the organisers' package. No code or saved mapping exists for them; the recipe store is empty." |
| Header shows **AI LIVE** | "This AI call is live. Its latency and cost are on the receipt." |
| Header shows **RREGULLA** | "No AI key is set right now, so you are seeing RULES mode. The mapping comes from synonyms, and a person confirms every column. With a key, Claude Haiku proposes it. The numbers come from code either way." |

**Never say:**

- "unseen";
- "real exports", unless the organisers confirm the files are unmodified department exports;
- "your questionnaire", or that the return "fills itself";
- that any municipal number is wrong or that any process is manual or broken;
- that the AI calculated anything;
- that the product runs on a local model;
- anything that predicts grant points.

---

## 2. Start-state checklist

**T-30 minutes**

- [ ] Laptop on power; notifications off; screen sharing tested on the projector at 1280×720. Set the browser zoom so the board's tiles are readable from the back.
- [ ] Code at the agreed tag; `git status` clean.
- [ ] API running: `make api`, or `cd api && uv run uvicorn app.main:app --port 8000`.
- [ ] Web running: `make web`, or `cd web && pnpm dev`. In dev mode each page compiles on its first visit, so **open every route once** now: `/`, `/ask`, `/ingest`, `/trust`, `/coverage`, `/briefing`, `/indicators/REQ-02`.
- [ ] `curl -s http://localhost:8000/api/v1/health`: `"mode"` is `"live"` or `"rules"`. Choose the matching honesty line (section 1).
- [ ] If LIVE: the key is the one declared in Annex E; `LLM_BUDGET_USD` is set; `/trust` → **Shpenzimi kundrejt buxhetit** (spend against budget) is readable.
- [ ] If LIVE, optional: ask the exploratory example once so its intent is cached. On stage it then shows the **CACHED** badge. Say so if asked. The gap and verified chips never call the model.
- [ ] Envelope files on the desktop and on a USB stick, copied from `api/samples/`:
  - `zarfi-1_SINTETIKE_pastrimi_mbetjet_2026.csv`
  - `zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx`
  - `zarfi-3_SINTETIKE_burimet_njerezore_2026.xlsx`
- [ ] Physical envelopes numbered 1, 2 and 3 (optional props; nobody walks over).
- [ ] Old `sportel-treguesit-*.xlsx` files removed from Downloads, so the new one is obvious.
- [ ] Excel running, and LibreOffice Calc tested with an export from the rehearsal.
- [ ] Fallback video open in a player and paused at 0:00 *[team to fill: file path]*. The deck is open on slide 4 in another window.
- [ ] Phone hotspot ready. It is only needed in LIVE mode, because RULES mode and localhost need no network.

**T-5 minutes** (after the last rehearsal, which loads envelopes)

- [ ] `make demo-reset`, or `curl -fsS -X POST http://localhost:8000/api/v1/demo/reset`. The response shows the coverage as computable/total; the start state is 6 of 13.
- [ ] Reload every tab, so the board shows the start state and the ask history is empty.
- [ ] `/ingest` shows **Asnjë recetë e ruajtur** (no saved recipe). **Burimet e ngarkuara** (loaded sources) lists only the three preloaded files, each marked **Barazuar** (reconciled). The requests file also says *2 kolona personale u hoqën para AI*: these are the invented name and phone columns in the synthetic file.
- [ ] On `/ask`, the three gap chips carry the tag **MANGËSI** (gap). Each one changes to **ME PROVË** (with proof) once its envelope is loaded.
- [ ] Browser tabs, left to right:
  1. `http://localhost:3000/`: **Paneli** (board)
  2. `http://localhost:3000/ask`: **Pyet të dhënat** (ask the data)
  3. `http://localhost:3000/ingest`: **Integro të dhëna** (ingest)
  4. `http://localhost:3000/trust`: **Besueshmëria** (trust; for Q&A)
  5. `http://localhost:8000/api/v1/indicators/REV-02`, or `http://localhost:8000/docs`, for the interoperability beat
  6. only if request item 1 (SMP list, `cp2-checklist.md` §6) is approved: `http://localhost:3000/coverage`, **Mbulimi SMP**
- [ ] Language: Albanian. The header shows **Të dhëna sintetike**, **AI LIVE** or **RREGULLA**, and **API aktive**.

---

## 3. Which envelope lights what

| Number called | Example chip on `/ask` (exact text) | Grey tiles it lights | Owner shown | File | Personal-data banner in the preview |
|---|---|---|---|---|---|
| **1** | *Sa kg mbetje prodhon një banor në vit?* | WST-01 *Mbetje të grumbulluara*, WST-02 *Mbetje për banor (kg/banor/vit)*, WST-03 *Kosto për ton* | *Drejtoria e Shërbimeve Publike* | `zarfi-1_…csv` | *Nuk u gjetën kolona personale* |
| **2** | *Sa e mbulon tarifa e pastrimit koston e mbetjeve?* | REV-01 *Arkëtimi i të ardhurave vendore*, REV-02 *Mbulimi i kostos së mbetjeve nga tarifa* | *Drejtoria e të Ardhurave Vendore* | `zarfi-2_…xlsx` | *Nuk u gjetën kolona personale* |
| **3** | *Sa punonjës ka bashkia për 1.000 banorë?* | HR-01 *Punonjës për 1.000 banorë*, HR-02 *Shkalla e rotacionit të punonjësve (largime / numri mesatar)* | *Drejtoria e Burimeve Njerëzore* | `zarfi-3_…xlsx` | *1 kolonë personale u hoq para AI* |

What is special about each envelope:

- **Envelope 1:** a CSV with `;` separators and decimal commas. After the load, the board's
  **Sinjale për verifikim** (signals to check) gains waste signals. One of them flags a month
  that reports 0 tonnes and says to check the quantity or unit. Use it as the signal beat.
- **Envelope 2:** the step log shows the `(000 lekë)` unit and the ×1,000 multiplier. REV-02
  joins the revenue export with the budget export, so its sources list two files from two
  directorates.
- **Envelope 3:** the dropped column is `Përgjegjësi i drejtorisë` (head of directorate). Say
  "this column holds invented names in our synthetic file; the gate drops it before anything
  else runs."

The owners are role-based placeholders. Their names are confirmed with the municipality.

---

## 4. The 95 seconds

| t | Tab and action | What the screen shows (exact labels) | Tech B says |
|---|---|---|---|
| 0:00–0:08 | **Tab 1, Paneli.** Point at the counter, then at the grey tiles, then at the lead box. | The counter reads *… nga 13 tregues me provë* (*read from screen*; 6 at start), with the same count in the header pill. The grey tiles sit in three areas (Mbetjet, Të ardhurat vendore, Burimet njerëzore). Each shows **MUNGON EKSPORTI** (export missing), the dataset name, **Përgjegjës: Drejtoria …** (owner) and the button **Ngarko eksportin** (load the export). The box **Për drejtuesit, këtë muaj** (for leadership this month) → **Kujt t'i kërkohen të dhënat** (whom to ask for data) lists the three directorates, each with *zhbllokon N tregues* (unlocks N indicators). | "Three gaps, three directorates, three envelopes. Please call a number: one, two or three." |
| 0:08–0:15 | **Tab 2, Pyet të dhënat.** Under **Pyetje shembull** (example questions), click the chip for the number called (section 3). Each chip starts with *Pyet:* (ask) and is tagged **MANGËSI**. | Stamp **PA PËRGJIGJE** (not answerable). The answer reads *Treguesi … nuk llogaritet ende: mungon eksporti i … Përgjegjës: … Asnjë numër nuk u hamendësua.* (no number was guessed). **Kuptuar si** (interpreted as): *Treguesi … · …*. The gap card shows **MUNGON EKSPORTI**, the dataset, *Përgjegjës: …*, *Skedari: zarfi-…* and the button **Ngarko eksportin**. | "Most assistants would guess. Ours names the missing file and who owns it." |
| 0:15–0:35 | **Tab 3, Integro të dhëna.** Drag the envelope file from the desktop onto **Tërhiqni skedarin këtu** (drag the file here). Backup: click the envelope **ZARFI N** under **Skedarët shembull në server** (server sample files). | The step log **Çfarë bëri kodi** (what the code did) reveals eight numbered steps one by one: **Leximi** (read), **Titujt** (header row; the units, e.g. `(000 lekë)` ×1.000, appear here), **Përjashtimet** (excluded rows; the `TOTALI`/`Gjithsej` row is kept for reconciliation), **Të dhënat personale** (personal data; section 3), **Profili** (profile), **Grupi i të dhënave** (dataset), **Receta** (recipe: none yet), **Përputhja** (mapping). Then **Përputhja e kolonave** (column mapping) with confidence chips; the note reads *E gjelbër ≥ 0,8 · e verdha kërkon një klikim konfirmimi* (green ≥ 0.8, amber needs a click). **RREGULLA:** every chip shows 0,60 *rregull* (rule), and the footer reads *N kolona presin konfirmim* (N columns await confirmation); click **Konfirmo të gjitha (N)** (confirm all). **AI LIVE:** click **Konfirmo** on each amber row. If a card **Një pyetje para ngarkimit** (one question before loading) appears, answer it. Leave **Ruaj recetën për muajin e ardhshëm** (save the recipe for next month) ticked. Click **Konfirmo dhe ngarko** (confirm and load). | "Code cleans the file: header, units, total row, personal columns. The AI only proposes which column means what. When it isn't sure, a person clicks." (In RULES mode, use the RULES line from section 1.) |
| 0:35–0:45 | Receipt, same tab. | **Fatura e ngarkimit** (load receipt), stamped **E BARAZUAR** (reconciled) and marked **TË DHËNA SINTETIKE**. **Rreshta të lexuar / Të ngarkuar / Të përjashtuar** (rows read / loaded / excluded), each exclusion with its reason. The line *lexuar = ngarkuar + përjashtuar · … = … + …* ends with *në rregull* (OK); *read from screen*. **Barazimi me totalin e skedarit** (reconciliation with the file total): *në skedar* (in file) against *e ngarkuar* (loaded), per money or quantity field. **Kolona personale të hequra para AI** (personal columns removed before AI). **Shumëzuesi i njësisë** (unit multiplier). **Thirrje AI** (AI call): model, latency and cost in LIVE (*read from screen*), or *rregulla · pa AI* (rules, no AI). **Receta**: *u ruajt · rcp-…* (saved). **Tregues të zhbllokuar** (indicators unlocked) chips. *Mbulimi tani: …/13* (coverage now; *read from screen*). Footer: *Kodi numëroi çdo rresht. Asnjë numër nuk u shkrua nga AI.* (code counted every row; no number was written by AI). | "Every load has a receipt. Rows read equal rows loaded plus rows set aside, and the sums match the file's own total row." |
| 0:45–1:00 | **Tab 2.** Click the **same chip** again. Its tag now reads **ME PROVË**. Backup: the receipt's **Pyet sërish** (ask again) button, which asks the question in tab 3. | Stamp **E VERIFIKUAR** (verified). The line *Më parë: Pa përgjigje → E verifikuar* (before: not answerable) appears only in tab 2, and the earlier answer moves to **Pyetjet e mëparshme** (previous questions). **Kuptuar si**: *Treguesi … · …*. The value and the templated sentence are *read from screen*. **SQL e ekzekutuar** (the SQL that ran) has a **Kopjo SQL** (copy) button. **Burimet** (sources) lists the file names with *rreshtat …* row ranges; for REV-02 there are two files. | "Same question, now proven, from the file you chose a minute ago." **(WOW 1)** |
| 1:00–1:10 | **Tab 1.** The tile is green now, and the counter has moved (*read from screen*). Click the tile. | The passport drawer shows *Pasaporta e treguesit · v…*, the badge **Draft — në pritje të validimit** (draft, awaiting validation), *Përgjegjës: …* (owner), the value with **Periudha / Gjendja / Objektivi / Më parë** (period / status / target / previous), **Seria** (series), **Formula**, **SQL që llogarit vlerën** (the SQL that computes the value), **Prejardhja: skedarët dhe rreshtat** (lineage: files and rows), **Rreshtat burimorë** (source rows, with the row number in the original file), and **Kontrollet e besueshmërisë** (plausibility checks), each marked **Kaloi** (passed) or **Për verifikim** (to check). Close it. **Tregues jashtë objektivit** (indicators off target) now includes the new indicators whose value misses the target. For envelope 1, also point at **Sinjale për verifikim**. | "Every number proves where it came from. And this is the decision for leadership: which directorate to ask for data this month, and which indicator is off target." |
| 1:10–1:25 | **Tab 1.** Click **Shkarko raportin (.xlsx)** (download the report). It saves `sportel-treguesit-<latest month>.xlsx` (`…-2026-08.xlsx` on the synthetic data); open it in Excel. | Sheet `Treguesit` has the visible column `Burimi` (source): file, rows, passport version, computed at. Sheet `Burimet` lists the source files with their hashes. Sheet `Shënime` (notes) holds the draft-formula and synthetic-data notes. Value cells carry comments. | "Each cell carries its proof." **(WOW 2)** |
| 1:25–1:35 | *Only if request item 1 (SMP list) is approved:* **Tab 6, Mbulimi SMP**. | The banner reads **Hartëzim paraprak · në pritje të miratimit nga organizatorët** (draft mapping, pending organiser approval). State chips: **Me provë** (with proof), **Kontroll dokumenti** (document check), **Kombëtar · AMVV** (national), **Mungon** (missing), **Manual**. Counts are *read from screen*. | "Same engine, national indicators. The grey ones are our week-1 pilot data list." |

If the approval is missing, skip the last row and end on the Excel file.

**Show the English toggle once**, for example on the passport drawer, then switch back to
Albanian. Use the language button at the right of the header: it shows `sq`, and its screen-reader label is **Gjuha** (language).

This flow (tabs 1–3, envelope 2, RULES mode) was walked through end to end in the real UI on
26 Sep against a private API seeded with `seed_demo.py`. Every label above was checked on
screen.

---

## 5. Fallbacks

| Problem | What happens | What to do and say |
|---|---|---|
| AI slow or unreachable (LIVE) | Mapping falls back to rules by itself, and the preview says *AI dështoi (…); u përdorën rregullat.* (the AI failed, rules were used). Every chip turns amber. | Click **Konfirmo të gjitha (N)**. Say: "The AI is unreachable, so it asks more questions. The numbers don't change." |
| AI budget spent | The header switches to **RREGULLA**, and the preview says *Buxheti i AI për këtë demo u shterua; përputhja u bë me rregulla.* (the AI budget for this demo is spent; the mapping used rules). | Same as above. |
| API stops during the demo | The web app switches to **REPLAY** by itself. The header shows the **REPLAY** badge, and the API badge shows **API jashtë linje** (API offline). The loop keeps working with recorded responses, including a drag-and-drop of the envelope files, which are matched by name. The xlsx button becomes **Shkarko CSV (REPLAY)** (download CSV, REPLAY), a browser-built CSV with the `Burimi` column. | Say: "The API is down, so you are seeing REPLAY: responses our API recorded earlier over the same synthetic files. The browser computes nothing." Tech A restarts the API (`make api`) and runs `make demo-reset` only after the pitch. |
| Planned offline run | Start the web app with `NEXT_PUBLIC_USE_FIXTURES=1 pnpm --dir web dev`. REPLAY is forced and no API is needed. | Say the REPLAY line at the start. |
| Web app down | | Play the recorded video *[team to fill: path; it must cover all three envelopes]*. |
| Everything down | | Slide 4: the three-screenshot sequence (refusal naming the owner → receipt → Verified with the green tile). |
| Excel slow to open | | Open the file in LibreOffice Calc, or keep talking while it opens. Never show a file downloaded before the demo as if it were new. |
| A juror offers their own file | | "Please pick one of the envelopes." Rule 10.3 allows only organiser data and approved items. |

---

## 6. The five-minute pitch (research §7.1, adapted)

Public figures are **only** cited if request item 3 (public figures, `docs/pitch/cp2-checklist.md` §6) is approved. Without
it, say "national performance indicators" and drop the numbers. Confirm the wording of Elbasan's
recognition at the municipal desk before using it. The desk quote is used only with recorded
consent.

| Time | Who | Beat |
|---|---|---|
| 0:00–0:25 | Domain | **Credit, then the problem.** Open with credit: Elbasan's recognition as a national good-practice model for validating performance indicators (28 May 2026; confirm the wording first). The national indicators are collected once a year. Department data lives in separate exports, and a number on a dashboard rarely shows which file it came from. Add the desk quote, if consent was given. |
| 0:25–0:45 | Domain | **Who we are.** "Sportel, the data counter: raporto një herë, provo çdo numër." The municipality announced an AI window that answers citizens. Sportel produces and proves the numbers underneath, and can feed it. |
| 0:45–2:20 | Tech B | **Live demo (section 4).** WOW 1 at about 1:30, WOW 2 at about 2:05. Name the leadership decision: which directorate to ask for data, and which indicator is off target. |
| 2:20–2:40 | Tech B | **The other two labels.** On `/ask`, click *Si ka ndryshuar zgjidhja brenda afatit sipas drejtorive në dy muajt e fundit?*: the stamp reads **EKSPLORUESE** (exploratory), with the SQL and a result table. In RULES mode, "Kuptuar si" says *SQL e përgatitur për shembullin (AI jashtë linje)* (prepared SQL for this example, AI offline); say it is a prepared query that passed the same guard. Then click *Më jep emrat dhe telefonat e kërkuesve*: the stamp reads **E BLLOKUAR** (blocked) and the reason is shown. If the eval chips are visible: "On our own 24-question set, indicative only, verified answers matched in *read from screen* of *read from screen*." |
| 2:40–2:55 | Tech B | **Interoperability.** Tab 5 shows `GET /api/v1/indicators/REV-02`, or any unlocked code: value, passport, lineage and basis. "Any AI window or national platform can cite this." |
| 2:55–3:05 | Tech B | **Spoken AI declaration** (Annex E §3): "Built with Claude Code, including multi-agent runs. Claude Haiku proposes column mappings and Claude Sonnet reads free-text questions, only when a key is set. ChatGPT designed our pre-event UI prototype. Claude helped with research. Code computes every number." |
| 3:05–3:40 | Domain | **Why it works here.** No connectors: only the exports departments already make. AI maps, code computes, a person confirms. The limits are on screen (`/trust`, **Kufijtë, të thënë hapur**, "limits, stated openly"). Quote a cost per file only from the `/trust` log of a live run (*read from screen*). The UNDP readiness figure is used only if request item 3 is approved. |
| 3:40–4:15 | Domain | **Scale.** The same passport mechanism works for other Albanian municipalities, a Kosovo pack (MPMS, Gjakova) and Serbia (Pirot posed the same challenge). Recipes can be shared between municipalities that use the same software. Price model: a flat annual fee per municipality, preferential for Elbasan, to be tested in the Validation Lab. Counts and grant amounts only if request item 3 is approved. |
| 4:15–5:00 | Domain | **Four weeks (research §7.4).** Week 1: a data agreement and three real exports with receipts. Week 2: passports reviewed with the Performance Unit. Week 3: running on a sandbox or municipal machine; eval rerun on real staff questions. Week 4: a parallel run reproducing the 2025 return from exports, cell by cell; this validates the tool, not the municipality. "Then the MVP Validation Lab and the February 2027 presentation to Elbasan. Raporto një herë." |

After the pitch, Tech A runs `make demo-reset`.
