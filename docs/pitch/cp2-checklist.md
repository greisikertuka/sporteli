# CP2 checklist: core demo, Saturday 26 Sep, 15:00

- **CP2 window:** 15:00–17:00, with a per-team slot. We have **5 minutes or less**.
- **Code freeze for the CP2 build:** 14:30. Rehearse twice after the freeze. Outside our slot,
  developers keep coding the post-CP2 list.
- **Scope:** the gap-to-proof loop from `docs/pitch/demo-script.md`, compressed. Every label
  and number shown must come from the running app. Say *read from screen* in your head. Never
  quote from memory.

## 1. What CP2 must show, and where it is in the app

| Must show (research §6) | Where | State |
|---|---|---|
| A department file goes in | `/ingest`: drag onto **Tërhiqni skedarin këtu**, or click **ZARFI 1/2/3** | Built |
| AI mapping with confidence | **Përputhja e kolonave**: confidence chips, green ≥ 0,8, amber needs a click. Without a key: RULES mode, every chip at 0,60 *rregull* | Built. **AI LIVE needs a key** (none on the build machine yet) |
| Confirm | **Konfirmo të gjitha (N)** or **Konfirmo** per row, then **Konfirmo dhe ngarko** | Built |
| Receipt counts | **Fatura e ngarkimit**: *lexuar = ngarkuar + përjashtuar*, **Barazimi me totalin e skedarit**, **E BARAZUAR** stamp | Built |
| KPI tiles and trend update | `/`: the tile turns green and the counter moves. In **Ecuria** (trend), pick the new indicator in **Treguesi** | Built |
| One Verified answer with SQL, source and label | `/ask`: the same chip again gives **E VERIFIKUAR** + **Kuptuar si** + **SQL e ekzekutuar** + **Burimet** | Built |
| One Not-answerable answer naming the owner | `/ask`, before the load: **PA PËRGJIGJE** + gap card *Përgjegjës: Drejtoria …* | Built |
| Extras if time allows | **E BLLOKUAR** and **EKSPLORUESE** chips; **Shkarko raportin (.xlsx)** with the `Burimi` column; the passport drawer | Built |

**Data honesty at CP2.** Everything on screen is synthetic (`SINTETIKE`, with the header badge
**Të dhëna sintetike**). Before 14:30, the team decides:

- **If the organisers' package has arrived:** try one package file through `/ingest` before the
  freeze. If it maps to one of the six datasets (requests, budget, waste, revenue, staff,
  population), show it and say it is the organisers' file. If it does not, show the synthetic
  envelope and say that mapping the package is the next step.
- **If the package has not arrived:** say so plainly: "Synthetic exports that our script
  generated, labelled on every file and on screen; the package drops into the same pipeline."

## 2. Pre-flight (commands)

Run them in Git Bash from the repository root. In PowerShell, use `pnpm` directly instead of
`cmd //c "pnpm …"`.

**T-60 min: build health** (stop if red; fix or hide the broken part before 14:30)

```bash
git status && git log --oneline -1
cd api && uv run pytest -q
cd api && uv run ruff check . && uv run ruff format --check .
cmd //c "pnpm --dir web lint"
cmd //c "pnpm --dir web test"
cmd //c "pnpm --dir web build"          # optional; takes a few minutes
```

**T-30 min: start the demo servers** (two terminals, ports 8000 and 3000)

```bash
cd api && uv run uvicorn app.main:app --port 8000
cmd //c "pnpm --dir web dev"
curl -s http://localhost:8000/api/v1/health     # "mode": "live" or "rules" decides the honesty line
```

If the organisers provide a key, add `ANTHROPIC_API_KEY=...` to `api/.env`, restart the API, and
check that `/health` says `"mode":"live"`. Set `LLM_BUDGET_USD` to 60–70% of the key's cap.

**T-25 min: whole-loop check** (this RESETS the demo data; run it before the final reset)

```bash
cmd //c "pnpm --dir web check-live http://localhost:8000 http://localhost:3000"
cd api && uv run python scripts/run_eval.py --mode rules    # refreshes the eval chips (/ask, /trust)
```

The eval script writes `api/eval_result.json`, a tracked file, so commit or discard the change
deliberately.

**T-5 min: start state**

```bash
curl -fsS -X POST http://localhost:8000/api/v1/demo/reset    # same as `make demo-reset`
```

Then:

- open every route once, so dev mode has compiled it: `/`, `/ask`, `/ingest`, `/trust`,
  `/indicators/REQ-02`;
- set the tabs to 1 `/`, 2 `/ask`, 3 `/ingest`, then reload all three;
- put the envelope files from `api/samples/zarfi-*` on the desktop and on USB;
- clean the Downloads folder;
- open Excel;
- open slide 4 and the fallback video.

The full list is in `docs/pitch/demo-script.md` §2.

## 3. Run sheet: who says what (5:00)

| Time | Who | Action | Line |
|---|---|---|---|
| 0:00–0:30 | **Domain** | Board on screen | Credit Elbasan (wording confirmed at the desk, or leave it out). "Since CP1 we renamed to Sportel: *raporto një herë, provo çdo numër*. Every number carries its proof; a missing number names its owner." Then the data-honesty line (section 1). |
| 0:30–0:45 | **Tech B** | Tab 1: counter and grey tiles; **Kujt t'i kërkohen të dhënat** | "Three gaps, three directorates, three envelopes. Pick a number." |
| 0:45–1:00 | **Tech B** | Tab 2: gap chip → **PA PËRGJIGJE** | "It names the missing file and the owner. No number was guessed." |
| 1:00–2:00 | **Tech B** | Tab 3: envelope → step log → mapping → confirm → receipt | "Code cleans and counts; the AI only proposes the mapping; a person confirms." In RULES mode: "No key right now, so rules propose it and we confirm every column." |
| 2:00–2:30 | **Tech B** | Tab 2: same chip → **E VERIFIKUAR**, SQL, sources. Tab 1: green tile, **Ecuria** | "Same question, now proven, with the SQL and the source rows." |
| 2:30–3:00 | **Tech B** | Tab 2: **Më jep emrat dhe telefonat e kërkuesve** → **E BLLOKUAR**; optional **Shkarko raportin (.xlsx)** → `Burimi` column | "Personal data is blocked before any model call. And the report carries its sources." |
| 3:00–3:30 | **Product** | `/trust` (**Besueshmëria**): **AI propozon** / **Kodi vendos dhe llogarit**, mode, **Kufijtë, të thënë hapur** | "What AI does, what code does, what leaves the building, and our limits, on screen." |
| 3:30–4:10 | **Tech A** | Talk only | "FastAPI and DuckDB. Every row keeps its file and row number. Indicators are versioned YAML passports with fixed SQL. The copilot label is decided by code, and the guard allows one read-only SELECT." Next before CP3: *[team to fill from the post-CP2 list]*. |
| 4:10–5:00 | **Domain** | Talk only | The approvals we asked for (section 6) and their status. Two questions for the mentors: "Is the loop the right hero for the pitch?" and "What would make you trust a number on this board?" |

**Q&A owners:**

- Tech A: ingest, personal-data gate, reconciliation, SQL guard, data model.
- Tech B: UI, REPLAY, hosting.
- Product: UX and screens.
- Domain: municipal fit, SMP, approvals, next steps.

## 4. Roles on the day

- **Tech A (backend and data):** pre-flight commands, the terminal during the slot (reset, restart), technical Q&A.
- **Tech B (copilot, web, deploy):** drives the laptop and narrates the demo; owns the fallbacks (REPLAY badge, video, slide 4).
- **Product / Design:** keeps time (hand signals at 2:00, 4:00 and 4:45), watches the screen for anything unlabelled, and writes down feedback verbatim.
- **Domain / Business:** opens and closes, owns the approvals and the desk, and records every approval in Annex E §2.

## 5. Things we do not say at CP2

- "unseen", "real exports", "your questionnaire", "fills itself".
- That any municipal number is wrong, or that a process is manual or broken.
- Any number not on screen right now. Any public figure (SMP counts, grant amounts, UNDP score)
  until request item 3 (section 6) is approved.
- That AI computed anything, or that the product runs on a local model.

## 6. Approvals request to the organisers (research §9.1)

Send it in writing through the organisers' official channel, repeat it at CP2 if there is no
answer yet, and record the approver, channel and time in `docs/annex-e-declaration.md` §2.

> Team FirmatGroup (Track D) asks for written approval under rule 10.3 for:
> (1) using the public SMP 2024 Annex A indicator list, and the indicator passport definitions if public, to build an indicator coverage map;
> (2) Census 2023 population as a denominator, if it is not in our package;
> (3) citing public figures in our pitch (SMP process, PBG assessment dates and pool, UNDP e-readiness score, Kosovo performance grant, Serbian LTI);
> (4) export-shaped files derived from our package files (title row, merged header, TOTALI row), labelled "derived from package file X";
> (5) a passcode-protected hosted demo showing package data and aggregates, and whether an open-data CSV of aggregates may be public under CC BY 4.0;
> (6) committing package files to our private event repository and container image;
> (7) until the package is in use, demonstrating on synthetic department exports that we generated ourselves, labelled "SINTETIKE" on every file and on screen, which contain no real or personal data.
> Could you also confirm the provider of our AI key (Claude or GPT) and the event repository URL? Thank you.

Item 7 is new since the research report. It covers what the demo actually runs on today.

## 7. Municipal desk questions (research §9.3; Domain/Business, with a printed sheet)

1. "How is the SMP return filled today? Who does it, from which exports, and **how many staff-days** does the July cycle take?"
2. "Which indicators are hardest to get, and which directorate is usually last?" Ask neutrally. Never quote the answer on stage as blame.
3. "Which population figure is official for per-capita indicators?"
4. "Can we have the indicator passport document and a blank SMP questionnaire, and the four-monthly monitoring template?"
5. "Are the files in our package typical of what departments actually export?"
6. "Would the Performance Unit review our passports in the mentoring phase?"
7. "How would you like us to describe the 28 May recognition, if we mention it?"

Also confirm the **owner names** for the gap tiles. The app shows role-based placeholders
(*Drejtoria e Shërbimeve Publike*, *Drejtoria e të Ardhurave Vendore*, *Drejtoria e Burimeve
Njerëzore*, and others), configured in `api/app/catalog.py`. Data-use approvals go to the
organisers (section 6), not to the desk.

**Quote (research §9.4):** ask for one sentence attributed by role only. Write it down
verbatim in Albanian, read it back, get a spoken or written OK, and record the date, role and
consent in Annex E §2. Never use a quote that criticises a colleague or a department.

## 8. Feedback capture (Product fills during the slot)

| # | Who said it (role) | Feedback, verbatim | Our action | Owner | Done by |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

After the slot:

- run `curl -fsS -X POST http://localhost:8000/api/v1/demo/reset`;
- sort the feedback into fix now / fix before CP3 at 21:00 / answer in Q&A;
- update Annex E with any approval received.
