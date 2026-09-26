# Sportel decision report: the WOW package for CP2 and CP3

*For Team FirmatGroup. Final version, Sat 26 Sep 2026, about 01:00 CEST. Read it once from top to bottom, then work from sections 6 and 7. Anything marked "unverified", "reported" or "pending approval" stays off the slides until it is cleared.*

---

## 1. TL;DR

- **Build "Raporto një herë, provo çdo numër" (Report once, prove every number). The demo WOW is the gap-to-proof loop.** The SMP questionnaire is not the WOW.
  1. The board shows Elbasan KPI tiles. Some are green and three are grey. Each grey tile names the export that is missing and the directorate that owns it.
  2. A juror calls a number (1, 2 or 3). We ask the question that belongs to that gap. The copilot answers **"Pa përgjigje"** (Not answerable): *export X is missing; owner: Directorate Y; no number was guessed.*
  3. We onboard that envelope's file from the organisers' package, live. The AI proposes the column mapping, code cleans and loads the file, and a **Load Receipt** reconciles rows and totals.
  4. We ask the same question again. It comes back **Verified**, with the SQL and the source rows, and the tile turns green.
  5. One click downloads the report as .xlsx. Next to every value, a visible "Burimi" (source) column names the file, the rows and the passport version.
- **Why the loop is the hero and the SMP Autopilot is not.** SMP 2024 Annex A has no citizen-request indicator. Indicators #41-52 (finance) are computed nationally by AMVV from Ministry of Finance data. Most of the rest need sector data (kindergartens, fire service, waste, social services, HR) that a Track D package very likely lacks. The loop works with any package, and it comes almost free from the CP2 core.
- **The passport engine stays at the centre.** Every KPI is an indicator passport: formula, SQL, lineage and owner. The national SMP indicators become the **coverage map** and the scale story: "N computable from today's files, 12 computed nationally by AMVV, the rest with owners named; this is the week-1 pilot data list." We bring back the line "an SMP-shaped draft of the return fills itself" only if Gate 1 finds 5 or more real, non-finance SMP inputs.
- **Supporting features, all on the same layer:**
  - an honest copilot with four labels;
  - one plausibility check, shown as the "signal" promised at CP1, plus one live trend chart;
  - a read-only REST/CSV indicator feed that the municipality's AI window could cite.
- **Open with credit.** On 28 May 2026 Elbasan was recognised as one of three national good-practice models for validating performance indicators. Our line: "Sportel turns that yearly practice into a monthly one, with proof on every number." Never describe Elbasan's process as manual or broken.
- **Name the leadership decision on stage:** which directorate to chase this month, and which indicator is off track.
- **Five things before sleep tonight:**
  1. Inventory the package and run Gate 1.
  2. Send the organisers one written request covering every rule 10.3 approval.
  3. Confirm the organiser key is Anthropic, and that Claude Code runs on a personal plan.
  4. Add the event organisation's repo as a remote and push the full history.
  5. Deploy a passcode-protected `/health` skeleton (by 09:00 at the latest).
- **Honesty wording, used everywhere:** "files from the organisers' package; no code or saved mapping exists for them; the recipe store is empty; this AI call is live." Never say "unseen" and never say "your questionnaire".

---

## 2. What the jury wants, what competitors will build, and how we beat them

### 2.1 Hot buttons and annoyances, by juror

| Juror | Rewards | Loses points on |
|---|---|---|
| **Deputy Mayor of Elbasan** (challenge owner; challenge-owner preference is the second tie-breaker, after the municipal-relevance score) | Their own vocabulary: Raporti Vendor i Performancës, SMP, AMVV, Njësia e Performancës, the July deadline. Credit for Elbasan's national good-practice recognition (28 May 2026). The link to grant money. A tool that feeds the AI window the municipality announced on 24 Sep. | Anything that reads as "your numbers are wrong", "your process is manual" or "your AI pilot is weak", especially in front of Kosovo and Serbian partners. A "broken promises" framing. Elbasan documents shown on screen disagreeing with each other. |
| **Elbasan planning / IT** (the daily user) | Messy real exports handled. Totals that reconcile. Recipes that remember a format. Named owners for missing data. Runs on a server they already have. | Format drift with no answer. No on-prem story. Multi-sheet `.xls`. Nobody named to maintain the passports. |
| **Reputeo** (AI and technical mentor; sovereign AI, ISO 42001) | Code computes the numbers; the LLM only maps and phrases. Accuracy measured per label. A log of exactly what leaves the building. Honest disclosure of caches and replays. One LLM client with a no-model fallback. | "AI swarm" theatre on seed data. Self-graded accuracy presented as a benchmark. A green "Verified" badge on the wrong filter. Claiming local or sovereign model support the code does not have. |
| **OSFWB** (donor) | Published, open-licensed verified indicators. OGP Local fit. A public history of pinned definitions. Digital rights (no personal data sent to the model). | Purely internal compliance tooling. Rebuilding financatvendore.al, which OSF already funded. |
| **NALED / BONEVET / Belgrade Open School** | Standards, indicator packs, transfer to Serbia and Kosovo, hours saved, cost per municipality. | Albania-only claims presented as "scalable". No price model. No onboarding estimate. |
| **Build Green / EIT** | A credible pilot-to-product path through the MVP Validation Lab, with preferential pricing. | No commercial path. |

Things that annoy every juror:

- a generic chat-with-data bot (it duplicates the Smart Process pilot);
- unapproved external data used as the demo dataset (rule 10.3);
- claims of live connectors to municipal systems;
- English-only screens;
- illustrative numbers passed off as real;
- problem stories about the host municipality that nobody verified.

The name "Sportel" also sounds like "sport" in the same week Elbasan was named European City of Sport 2027 (announced 24 Sep). Always pair it with the Albanian tagline.

### 2.2 What competitors will build

- **The predicted Track D baseline** (about 80% of teams): KPI cards, ECharts trends, a map and a chat-with-CSV bot running on synthetic or hardcoded data. Simulated score: about 53-56/100.
- **A visible Tirana competitor** (Track A, Gjakova) uses our exact stack (Next.js 16, shadcn). It shows an "AI swarm" dashboard with six named agents running on a hardcoded `seedIssues` array. https://github.com/gjergjquni/ai4society-gjakova-hackathon
- **The Belgrade quality bar is NaSalter** (The Merge Conflicts). It has a hosted demo, 84 commits, a "no chatbot" scope, an LLM that never writes addresses, declared synthetic data and an explicit risk list. A team that polished scores about 68/100. https://github.com/damnilo/AI4Society-Hackathon
- **The Belgrade/Pirot leg had the same challenge** ("dashboards for management reporting and decision support") and ran 18-20 Sep. It is over, so its submissions are fixed. Winners are picked across both events on one scorecard, and part of that comparison may rest on submitted artifacts rather than live theatre. That is why a 60-90 s narrated demo video goes in the README and on deck slide 4.

### 2.3 How we beat them

1. **"Is it real?"** The juror picks the gap. The file comes from the organisers' package, with no hardcoded path. The recipe store is visibly empty. The latency and cost of the AI call are shown on screen.
2. **"Is it honest?"** Before the file arrives, the copilot refuses: it names the missing export and its owner and does not guess. After the load, the same question is Verified. No other team will show its assistant saying "I can't" on purpose.
3. **"Is it ours?"** The output lands in Elbasan's own KPI pack. The coverage map shows how the same engine reaches the national SMP indicators, which covers municipal relevance (20%).
4. **"Can I trust it?"** Every number comes from fixed SQL and traces back to its source rows. The LLM never types a digit.
5. **"Does it help decide?"** The grey tiles tell leadership which directorate to chase this month. The signal tells them which indicator is off track.
6. **"Does it fit what we already have?"** Sportel sits upstream of the city's AI window and of the AMVV submission channel. It replaces neither.
7. **"Does it scale?"** The same passport mechanism applies to Albania's 61 municipalities, and a Kosovo MPMS pack uses the same format.

Scores: the jury simulation gave the SMP Autopilot framing 71/100 and the envelope alone 70/100. The recombined gap-to-proof loop was **not** re-simulated. The 74-78/100 target is an estimate, not a measurement.

---

## 3. The real, unsolved Western Balkan problems we address

Status key:
- **Verified** means re-checked against the source during the review pass.
- **Reported** means it comes from team research and was not re-checked. Do not put it on a slide until someone has re-read the source.
- **Dropped** means do not use it.

| # | Problem | Evidence | Status | Why no one has solved it |
|---|---|---|---|---|
| 1 | **National performance reporting is annual, and collection is manual.** | SMP 2024 covers 52 indicators. Collection runs through an Excel questionnaire, then a Google Form, then an official letter. Deadline 31 Jul 2025; 332 staff trained; report published Nov 2025. https://qeverisjavendore.gov.al/wp-content/uploads/2025/11/SMP-2024.pdf | Verified. *The report's admission of inaccuracies and post-submission corrections: Reported; re-read the page before quoting.* | AMVV and Bashki te Forta built the methodology and the training, but no pipeline from department exports. Smart Processes' PMS digitises data entry (64 data points and 40 KPIs: Reported). Kosovo's SEMPK is electronic entry with mayoral sign-off (Reported). We found no tool that computes indicators from exports. https://smartprocesses.eu/projects/ |
| 2 | **The grant assessment is running right now.** | The KVA assesses 2025 data for the 2026 Performance-Based Grant from 8 Sep to 27 Oct 2026. 60 municipalities reported 2025 data. Pool: EUR 2.5 M (EUR 2 M from the state, EUR 0.5 M from Swiss and Swedish partners; RTSH). https://bashkiteforta.al/nis-procesi-i-vleresimit-per-grantin-e-bazuar-ne-performance-2026/ · https://rtsh.al/grant-performance-ministri-demo-2-5-milione-euro-per-bashkite-qe-ofrojne-sherbime-me-te-mira/ | Verified. *"Complete, good-quality reporting is a PBG criterion (Joint Instruction No.1, 11.07.2025)": Reported; re-check before saying it. "200 M lek": search summary only; Dropped.* | Nobody gives a municipality a view of completeness and consistency before submission. |
| 3 | **Elbasan leads on good practice, but the practice is yearly and ends in a PDF.** | On 28 May 2026 Elbasan was recognised, with Shkodra and Pogradec, as one of three national good practices for validating and enriching performance indicators and for evidence-based decisions. A July 2026 validation meeting on the 2025 report was presented as a model (kohajone, 14 Jul 2026). The 2025 Performance Report is 107 scanned pages with no text layer. The AI window the municipality announced on 24 Sep 2026 (Bashki te Forta, Helvetas, Smart Process) answers citizens from that report. https://kohajone.com/aktualitet/qeverisje-e-hapur-dhe-vendimmarrje-me-evidence-praktika-e-bashkise-se-elbasanit-merr-vleresim-kombetar/ · https://kohajone.com/aktualitet/bashkia-elbasan-mat-performancen-e-saj-per-vitin-2025-nis-procesi-i-validimit-te-raportit-vendor/ · https://elbasani.gov.al/bashkia-elbasan-pilot-per-perdorimin-e-inteligjences-artificiale-ne-transparence-dhe-llogaridhenie/ | Verified. *How Elbasan fills its own SMP return (who copies what, how many staff-days) is **unverified**; confirm it at the desk before describing it.* | Publishing ends with the report. The AI pilot reads the finished report; it does not produce it. **On stage, give credit only.** Never say "locked away" or "done by hand". |
| 4 | **Donor systems die because nothing feeds them.** | UNDP: average municipal digital readiness is 31/100, and donor-built systems are discontinued once the project ends. The same report says maintenance budgets are not prohibitively high and that the real issue is adoption. https://www.undp.org/sites/g/files/zskgke326/files/2024-09/dra_national_report_final_eng.pdf | Verified. *Elbasan's own score: Reported. "EUR 7-30k a year to keep systems": not in this report; Dropped.* | Tools were built around new data entry, not around the exports departments already produce. That is an adoption problem, which is exactly what "exports only" answers. |
| 5 | **There is no single official figure.** | Population: Census 2023 gives 115,101; the civil registry and PBA give 217,578; SMP computes on the census. Every per-capita KPI swings by about 1.9x. Own revenue for 2024 is 1,571.5 M lek in the Performance Report and 1,190.0 M in the budget monitoring report; the gap is the 381.5 M carried over from 2023. https://elbasani.gov.al/wp-content/uploads/2026/03/Statistika-vendore-2025-Elbasan.pdf · https://elbasani.gov.al/wp-content/uploads/2025/05/RAPORT-MONITORIMI-BUXHETI-2024.pdf | Reported. These are Elbasan documents, so showing them needs approval. **Use in Q&A only.** | Dashboards silently pick one number. Passports define formulas on paper, but nothing enforces the definition or stamps which base was used. |
| 6 | **Problems only become visible after the fact** (roadmap context only). | Elbasan's 2024 budget execution was 72%, investment 51%, construction fines 3% of plan. A KLSH audit press headline says "820 milione" in old lek (about 82 M new lek) of obligations that were never recorded. National municipal investment execution in H1 2026 was 14.4%. https://www.voxnews.al/biznes/zhduken-820-milione-leke-nga-bashkia-e-elbasanit-i113566 · https://www.korcaboom.com/sq/post/tender%C3%AB-me-miliarda-investime-t%C3%AB-bllokuara-bashkit%C3%AB-realizuan-vet%C3%ABm-14-4-t%C3%AB-buxhetit-n%C3%AB-6-muaj | Reported. The KLSH figure is press-only; **keep it off the slides.** | Monitoring arrives as narrative PDFs every four months. |
| 7 | **The same pattern exists across the region** (scalability). | Kosovo: the performance grant paid EUR 33.5 M from 2014 to 2023 to 33 of 38 municipalities, based on 30 criteria. The MPMS has about 93-119 indicators depending on the edition. Serbia: the Local Transparency Index average has been stuck at 52 for the fourth year running. https://helvetas-ks.org/demos3/multimedia-stories/transforming-citizens-lives-kosovos-decade-evolution-of-the-municipal-performance-grant/ · https://srpske.rs/vesti/politika/2026/09/23/indeks-transparentnosti-opstina-prosek-52-cetvrtu-godinu-presevo-poslednje-sa-28 | Verified (grant, criteria, LTI). *MPMS indicator count: Reported.* | Each system was built by a different donor or ministry, with no shared data layer. |

**What SMP Annex A really contains** (verified against the local SMP 2024 text). This is what reshaped the hero:
- No indicator covers citizen requests or complaints.
- #41-52 (finance) come with the note "Burimi: Ministria e Financave, llogaritur nga AMVV" (source: Ministry of Finance, computed by AMVV). They are computed nationally, not filled in by the municipality.
- About 13-14 indicators are "the plan or publication exists" document checks.
- The rest need sector data.

Caveat on novelty: "no Western Balkan municipal tool computes official indicators from exports with lineage" rests on about 200 multilingual searches, which is absence of evidence. Say "we found none", not "none exists".

---

## 4. Ranked candidates

Composite = jury average × feasibility factor × novelty factor (from the scoring pass).

| # | Candidate | Jury avg /100 | Feas. /5 | Novelty /5 | Wow /5 | Composite | Final verdict |
|---|---|---|---|---|---|---|---|
| **H** | **Gap-to-proof loop** (#7 refusal, then #1 envelope, then Verified on the #2 passport engine) | not re-simulated | 4 | 3-4 | 4 (estimate) | n/a | **HERO.** It works on any package and is almost entirely built from the CP2 core. |
| 1 | Juror envelope: live onboarding | 70.2 | 4 | 3 (mechanism refuted) | 3 | 55.6 | **Step 3 of the hero.** Flatfile, OneSchema and Osmos (now part of Microsoft Fabric) already sell AI column mapping, so the wow comes from what the file unlocks, not from the mapping. Keep the Load Receipt. |
| 2 | SMP Autopilot (passports as code) | 71.0 | 3 | 4 (not refuted) | 4 | 53.4 | **The engine stays; the payoff becomes the coverage map and the scale story.** Demoted after the Annex A check (§3). The "SMP-shaped draft fills itself" beat returns only at 5 or more non-finance inputs. |
| 3 | One number, one definition (population pin) | 65.0 | 4 | 3 | 3 | 51.5 | **Q&A answer and red-tile text only.** Keep it out of the 5-minute pitch: it needs Census approval and shows Elbasan documents disagreeing. |
| 4 | Pre-council PBA check | **73.2** | 3 | 3 | 4 | 51.5 | **Its generic rules become the passport checks.** One rule is the CP1 "signal" in the minimum version. The rule pack on Elbasan's real PBA stays for Q&A and mentoring. |
| 5 | Revenue integrity (KLSH audit replay) | 63.8 | 3 | 4 | 3 | 48.0 | Cut. It needs synthetic registers and is sensitive in front of the Deputy Mayor. One Q&A line only. |
| 6 | Capital lapse radar | 67.8 | 3 | 3 | 4 | 47.7 | Cut; roadmap. It needs three sources the package almost certainly lacks. |
| 7 | Honest copilot | 67.4 | 3 | 3 | 3 | 47.4 | **Steps 2 and 4 of the hero.** The refusal that names the missing export and its owner opens the loop, and Verified closes it. |
| 8 | Certified indicator feed (REST, MCP) | 67.2 | 3 | 3 | 3 | 47.3 | **Support, REST and CSV only.** MCP is a stretch goal. |
| 9 | Number-locked monitoring report | 66.8 | 3 | 3 | 3 | 47.0 | Cut. Reuse its placeholder technique for all AI prose. |
| 10 | Paper-to-data (scanned reports) | 66.8 | 2 | 3 | 4 | 41.1 | Cut. Roadmap line: "turn your 2022-2024 reports into a multi-year series". |

**Why the hero changed after review.** The SMP board can only light up if the package holds SMP inputs, and Annex A says it probably does not. A hero that collapses into its fallback at 01:30 is not a hero. The gap-to-proof loop is built from pieces CP2 needs anyway:
- ingest;
- passports with a "missing (owner)" state;
- the copilot's Not-answerable label, driven by a small `gaps.yaml`.

So its WOW costs almost no extra build time. It also puts the two things jurors distrust most about AI dashboards (made-up answers and demo data) on stage and beats both, in front of them.

**Worth taking from the runners-up:**
- **Pre-council check.** Four generic rules become passport checks:
  - a year-on-year swing above a threshold while spending stays flat;
  - placeholder values (0, 1, repeated constants);
  - parts that do not sum to the total;
  - rates outside 0-100%.

  One of them goes in the minimum as the visible "signal". Add "accept permanently with reason" against alert fatigue, and use the framing "the form never asks; nobody made a mistake".
- **Number-locked report.** The LLM writes `{{fact_id}}` placeholders and code renders every number in Albanian format. Use this for every AI sentence. Pitch line: "the model is not allowed to type a digit."
- **Envelope.**
  - **The Load Receipt:** file hash; rows read = loaded + excluded, with reasons; the sum reconciled against the file's TOTALI row when there is one; personal columns dropped before any model call; model and recipe version.
  - **The format-drift beat:** rename one column, the fingerprint misses, and the recipe stops and asks. It is the fallback when fewer than three envelope files exist.
  - The line: "Flatfile and Fabric do this for companies with a data engineer; this costs about 1 cent per file."
- **Certified feed.** Say "Konfirmuar nga Sektori X" (confirmed by sector X), not "Certifikuar": Albania's KVA already verifies SMP data, and NALED runs a certification brand. Status ladder: draft → sector sign-off → sent to SMP → validated by KVA. The last step is external and only recorded.
- **Paper-to-data.** Claude's Citations API cannot cite scanned PDFs (https://platform.claude.com/docs/en/build-with-claude/citations). That makes it a roadmap item: history as data.

---

## 5. Specification of the recommended package

### 5.1 User stories

**Leadership (Mayor's cabinet, Deputy Mayor)**
- As leadership, I see the municipality's key indicators every month, not once a year, so I can act before the July deadline and before the grant assessment.
- As leadership, I see which indicators we cannot compute yet and which directorate owes the data, so I know whom to chase this month.
- As leadership, I trust a number because I can open its formula and source rows, and the copilot tells me when an answer is only exploratory or when it cannot answer.

**Department head** (e.g. Finance, Urban Services, Social Services)
- As a department head, I upload the export I already produce, and next month it maps itself, so reporting costs me no new data entry.
- As a department head, I see my department's indicators and any plausibility flag before they leave the building, and I can mark a flag "correct, because…".

**Planning and reporting clerk** (Performance Coordinator, Statistics and Performance Sector)
- As the coordinator, I download a report where every value carries its source, so I can check it quickly against the paper and online submissions.
- As the coordinator, I see how the national SMP indicators map to our exports: which are computable, which are document checks, which AMVV computes nationally, and who owes the rest.
- As the coordinator, I pin the official definition when two documents disagree (for example the population base), and that choice is stamped on every screen, export and API response.
- As the coordinator, I publish confirmed indicators through an open endpoint that the city's AI window and the OGP forum could read.

### 5.2 The demo moment, second by second (about 95 s of the pitch)

Numbers are placeholders; on stage we show only real counts from the package. The UI runs in Albanian, the narration is in English (the working language for pitches and Q&A), and key screens carry a one-line English subtitle. Show the EN toggle once.

**Start state after `make demo-reset`:**
- one or two package files already onboarded, each with its receipt on the Sources screen;
- three grey gap tiles, each tied to one envelope file;
- the recipe store at "0 receta";
- the "LIVE AI" badge on.

| t | Screen | Presenter says (short) |
|---|---|---|
| 0:00-0:08 | The board shows the coverage counter "5/12 tregues me provë" (indicators with proof), green tiles and three grey tiles reading "Mungon: eksporti i [X] · Përgjegjës: [Drejtoria Y]" (missing: the [X] export; owner: [Directorate Y]). | "Three gaps. Three files from the organisers' package. Please call a number: one, two or three." |
| 0:08-0:15 | The juror says "two". Click gap 2's question card. The copilot answers **"Pa përgjigje"** (Not answerable): "Mungon eksporti [X] · Përgjegjës: [Drejtoria Y] · Asnjë numër nuk u hamendësua" (no number was guessed). | "Most assistants would guess. Ours names the missing file and who owns it." |
| 0:15-0:35 | Drag file 2 into `/ingest`. The step log streams: header row detected, merged cells split, TOTALI row excluded, units detected, and "Nuk u gjetën kolona personale" (no personal columns found) or "N kolona personale u hoqën para AI" (N personal columns removed before AI), whichever is true. The mapping table shows confidence chips; any amber column needs one click. | "Code cleans the file. The AI only proposes which column means what. When it isn't sure, a person clicks." |
| 0:35-0:45 | **Load Receipt:** rows read = loaded + excluded (with reasons); the sum reconciled against the file's TOTALI row; "Thirrje AI: 3,1 s · $0,009" (AI call); "Receta u ruajt" (recipe saved), if recipes are built. | "Every load has a receipt." |
| 0:45-1:00 | Ask the same question again. **"E verifikuar"** (Verified): the number is rendered by code, an "Interpreted as" chip shows how the question was read, and the SQL and the source file with its row range are visible. The tile turns green and the counter moves to 7/12. | "Same question, now proven, from a file you chose a minute ago." **(WOW 1)** |
| 1:00-1:10 | Click the tile. The passport drawer shows the formula in plain Albanian, the SQL, the source rows, the owning directorate and "formula në pritje të validimit" (formula awaiting validation). If a check fires, a signal badge appears ("pjesët nuk mblidhen me totalin", the parts do not add up to the total). | "Every number proves where it came from. And this is what leadership decides on: which directorate to chase, which indicator is off track." |
| 1:10-1:25 | Click "Shkarko raportin (.xlsx)" (download the report). The file is **already open** in Excel or LibreOffice: every value has a visible "Burimi" column (file, rows, passport version, computed at), plus a "Burimet" (sources) sheet. Cell comments are there too, but the column is what the projector shows. | "Each cell carries its proof." **(WOW 2)** |
| 1:25-1:35 | *Only if the methodology is approved:* the SMP coverage map. N computable from today's files; about 13-14 document checks; 12 "llogaritur nga AMVV nga të dhënat e MF" (computed by AMVV from Ministry of Finance data); the rest grey with owners. | "Same engine, national indicators. The grey ones are our week-1 pilot data list." |

**Envelope logistics:**
- The files sit on the desktop as `zarfi-1`, `zarfi-2` and `zarfi-3` ("zarf" means envelope), with copies on a USB stick.
- The juror calls a number; nobody walks over (that saves 10-15 s).
- Physical envelopes are optional props.

### 5.3 What AI does, and its honest limits

**What the AI does:**
- **Mapping:** Haiku 4.5 makes one structured-output call per file. For each column it returns a canonical field (or "ignore"), a confidence, a reason code, a transform, and at most one clarifying question. About USD 0.01 per file.
- **Copilot:** Sonnet 5 turns a free-text question into a structured intent (a passport code, or guarded SQL), and writes prose that contains only fact placeholders. The example-question buttons skip the model and route straight to a passport code.
- **Optional, Q&A only:** Sonnet drafts the SQL for one passport from its Albanian text, a person approves it, and it runs against hand-computed fixtures.

**What code does:**
- header, unit and TOTALI detection;
- the personal-data gate (a regex for the Albanian personal number, +355 phone numbers and emails, applied before any sample reaches the model);
- every indicator value, lineage and reconciliation;
- the rule checks;
- **the label on every copilot answer.** The model does not choose it:
  - **Verified:** a passport code, executed with its fixed SQL.
  - **Exploratory:** guarded SQL that matches no passport, or a passport plus an extra filter.
  - **Blocked:** the guard rejected the query (personal fields, a non-SELECT statement, or a disallowed table).
  - **Not answerable:** the required tables are empty, and the gap and owner come from `gaps.yaml`.

**Limits, stated on screen or in the deck:**
1. Every formula is our reading of the public passports until the Performance Unit or AMVV validates it. Only formulas stated verbatim in SMP 2024 or in the passport document are marked "from source"; all others are "draft".
2. About 13-14 SMP indicators are "plan or publication exists" checks that need a document link and a human tick. Verify the exact list before quoting a number.
3. Indicators #41-52 are computed nationally by AMVV from Ministry of Finance data. Sportel marks them that way and does not compute them.
4. A missing input is marked "not computable" with its owner named. It is never estimated.
5. Sportel proves consistency and lineage, not that a department's file is true.
6. The export is "SMP-shaped" until we receive AMVV's real template.
7. The accuracy figure comes from our own frozen set of 24 questions (12 Albanian, 12 English, including traps). It is indicative, not a benchmark.
8. Low-confidence mappings always need a click.
9. Only headers, profile statistics and masked samples go to the model, never rows.
10. On the hosted link, the example questions may be served from a cache, and those answers are badged "CACHED".
11. Today the product calls Claude through the Anthropic API. Without a model, mapping falls back to rules and the indicators still compute.
12. Sportel predicts no grant points or money and is not an official submission channel.

### 5.4 Data needed, approvals and gates

**We use:** only files from the organisers' package, plus aggregates derived from them. No juror's own files and no scraped external data.

**Who approves:** rule 10.3 approval comes from the **organisers**, not from the municipal Q&A desk. Send one written request tonight to the organisers' data lead or mentor (the draft text is in §9.1), and repeat it at the 09:00 stand-up if there is no answer. Record the approver, channel and time in Annex E. Until an item is approved, label that work "pending approval". The municipal desk is for domain facts, the quote and documents.

**Items to approve:**
1. The **SMP 2024 Annex A indicator list** and, if public, the **passport definitions** ("Pasaportat e treguesve"): public methodology, but still "information" under rule 10.3.
2. **Census 2023 population (115,101)** and the municipality's own **Statistika vendore 2025** figure as denominators, if they are not already in the package.
3. **Citing public figures in the pitch:** the SMP process facts, the PBG assessment dates and pool, the UNDP readiness score, the Kosovo grant and the Serbian LTI.
4. **Export-shaped derivatives of package files** (a title row, a merged header, a computed TOTALI), labelled "derived from package file X", if the package files are too clean.
5. **A passcode-protected hosted demo** that shows package data and aggregates. Ask whether the open-data CSV may be public under CC BY 4.0 or must stay behind the passcode.
6. Whether package files may be committed to the private event repo and baked into the hosted container.
7. Optional: a blank SMP questionnaire and the official monitoring-report template.

**Gate 1 (01:30, all four people): inventory the package and count four things.**

| Count | Rule |
|---|---|
| **A. Envelope-viable files:** tabular, maps to a canonical table, and lights at least one KPI tile | 3 or more: three envelopes. 2: two envelopes. 1: one file plus the format-drift beat (rename a column live; the fingerprint misses and the recipe asks). 0 tabular files: the CP2 core is at risk. Ask the organisers at 09:00 for a tabular sample, and request approval for export-shaped derivatives. |
| **B. KPI passports the package supports** | Target 8-12, spread across at least two departments. Avoid leading with finance, because Financat Vendore (OSF-backed) already covers it. |
| **C. SMP Annex A inputs computable from the package, excluding #41-52** | 5 or more: add the secondary beat "an SMP-shaped draft of the return fills itself" after the loop. 1-4: coverage map with N green. 0: coverage map as a static view of states and owners, shown only if the methodology is approved. |
| **D. Gap candidates:** questions that would need a package file not yet loaded | One gap per envelope file. Owners come from department names in the package or from the desk. Never invent Elbasan directorate names. |

Hypothesis to check at Gate 1: scraped website content may supply evidence links for the transparency "document-check" indicators (publication of council decisions, the PBA, the fiscal package).

**Gate 2 (13:00 latest): the organisers' written answers.**
- **No methodology approval:** no Annex A list or SMP names on screen. The Elbasan KPI pack stands alone, and SMP is mentioned only as the scale path, in speech, and only if citing public facts is approved (otherwise say "national performance indicators").
- **No denominator approval:** per-capita tiles stay red with the text "baza e popullsisë e papërcaktuar" (population base not set).
- **No answer by 13:00:** treat everything as not approved for CP2 and ask again at CP2.

### 5.5 Architecture changes to the current repo

Current state, verified:
- `api/app/main.py` has only `/health`, with CORS limited to `http://localhost:3000` (`api/app/config.py`).
- `api/app/warehouse/db.py` exists.
- `api/app/llm/client.py` has a text-only `complete()` with a `max_tokens=1024` default, and tracks spend in memory only.
- The web app runs on `web/src/lib/pulse-data.ts` (mock data) on Next.js 16.3.6.
- `web/src/components/pulse/trend-chart.tsx` already exists.
- The repo has **no git remote** and one branch, `codex/civic-interface`.

| Area | Files | Change |
|---|---|---|
| Dependencies | `api/pyproject.toml` | Add `openpyxl`, `sqlglot` and `pyyaml` (explicit). Add `mcp>=2.2,<3` only for the stretch goal: `from mcp.server.fastmcp` fails in 2.x, so use `mcp.server.mcpserver.MCPServer`. |
| LLM client | `api/app/llm/client.py` | Add `complete_json()` using `messages.parse` / `output_config.format`. Return `stop_reason` and treat `max_tokens` as an error. Set Sonnet 5 effort to low explicitly (adaptive thinking is on by default and billed as output). Raise `max_tokens`. Count cache tokens in the cost. **Persist an `llm_call` row and restore `spent_usd` from it at startup; this is required before any hosted link.** Keep the provider behind this one client. |
| Warehouse | `api/app/warehouse/schema.py` (new), `db.py` | Canonical DDL (spec §4.2) with `source_id` and `row_no` on every fact row. Add `source(file_hash, header_fingerprint, rows_read, rows_loaded, rows_excluded_json, mapping_json)`, `mapping_recipe`, `reference_value`, `definition_pin`, `audit_log`, `llm_call`, and `indicator_version` (stretch). Use **one process-wide connection plus cursors**: DuckDB refuses a `read_only=True` connection to a file the same process already holds read-write (verified on this machine). |
| Ingest | `api/app/ingest/{reader,pii,profile,mapper,reconcile,recipes,router}.py` | Build CSV first, then XLSX with **openpyxl**, not the DuckDB excel extension (verified: merged title rows collapse its read to one column, and it installs over the network). CSV: try utf-8-sig, then cp1252, with delimiter sniffing. Detect the header row, forward-fill merged cells, exclude TOTALI/Gjithsej rows, detect units, parse Albanian numbers and dates. The PII gate runs before profiling. One Haiku call, with a deterministic synonym fallback (confidence capped at 0.6, so everything turns amber). Reconcile counts are **returned in the commit response** (needed for lineage anyway). Recipes are keyed by header fingerprint, only if the 10:00 gate is green. |
| Indicators (passports) | `api/app/indicators/{models,registry,executor,router,export_xlsx}.py`, `packs/core_kpi.yaml`, `packs/al_smp.yaml` (coverage only), `pins.py` and `packs/xk_mpms.yaml` (stretch) | A passport holds: code, area, name_sq/en, formula_sq, formula_source (verbatim or draft), kind (computed, document, manual or national), SQL, a lineage query, required_fields, owner_department, unit, denominator, framework_ref, status, version, checks and tests. The registry validates required_fields against `information_schema` and returns one state: computable, missing(owner), document or national (AMVV). The xlsx export writes a visible "Burimi" column, a "Burimet" sheet and openpyxl cell comments. |
| Copilot | `api/app/sqlguard/guard.py`, `api/app/copilot/{sandbox,prompt,router,gaps.yaml,answer,proof}.py` | The sqlglot guard allows one statement, SELECT only, with a table allowlist, table functions denied and a LIMIT wrapper. The sandbox is a Parquet snapshot loaded into `:memory:` with `enable_external_access=false` and `lock_configuration=true` (verified working); timeouts use `con.interrupt`. `gaps.yaml` maps each canonical table to its export name (sq/en), owner directorate and example question. Code decides the label (§5.3), an "Interpreted as" chip is shown, and answers are templated from placeholders. |
| Hosting and protection | `api/app/config.py`, `api/app/security/ratelimit.py` (new), `api/scripts/seed_demo.py`, `web/src/proxy.ts` (Next.js 16's renamed middleware) | `CORS_ORIGINS` comes from the environment and includes the Vercel URL. A per-IP rate limit on `/ask` and `/ingest`. A passcode check in `proxy.ts`, or basic auth at the host. The DuckDB demo database is seeded at container start, because Hugging Face Spaces disks are ephemeral. A separate small budget for hosted ingest. |
| Endpoints | `/api/v1/...` | `POST ingest/preview`, `POST ingest/commit` (returns the receipt), `DELETE ingest/recipes` (behind `DEMO_RESET`). `GET indicators?pack=`, `GET indicators/{code}`, `GET indicators/{code}/lineage`, `GET export/{pack}.xlsx`, `GET open-data/indicators.csv`. `POST ask`, `POST sqlguard/check`, `GET llm/calls`. Stretch: `POST indicators/{code}/pin`, `GET ask/eval`. |
| Eval | `api/tests/golden/golden_set.yaml`, `api/scripts/run_eval.py`, `make eval` | Frozen before prompt tuning, with the commit hash recorded in `eval_result.json`. Expected values are hand-computed in Excel from the package files. |
| Web | `web/src/lib/api.ts` | Add `apiPost`, `apiPostForm` and the types. |
| | `components/pulse/csv-import.tsx` | Server upload, a step log built from server step codes, confidence chips, and the LoadReceipt. |
| | New: `indicator-grid.tsx` (gap tiles, states, coverage counter), `passport-sheet.tsx`, `load-receipt.tsx`, `gap-card.tsx`; `app/coverage/page.tsx`; stretch: `accuracy-chip.tsx` | Built by the product person against fixture JSON before CP2 (new files only), then wired by Tech B. |
| | `overview.tsx`, `trend-chart.tsx` | Tiles and one live trend come from `/indicators?pack=core_kpi`. |
| | `ask.tsx` | Four label states, example-question buttons, a gap card naming the owner, and the proof drawer. |
| | `app-sidebar.tsx`, `messages/sq.json`, `messages/en.json` | Navigation entry and strings. |
| | `pulse-data.ts` | Retired, or kept only as a labelled offline snapshot for REPLAY mode. |

### 5.6 Minimum version vs stretch

**Minimum before CP2 (code freeze 14:30):**
- Live ingest: CSV always, XLSX if the 10:00 gate is green. AI mapping with confidence chips, then confirm.
- Receipt counts in the commit response.
- The canonical model with `row_no` lineage.
- 8-12 KPI passports served by `/indicators`, with the states computable and missing(owner).
- Overview tiles plus **one live trend chart** (the existing `trend-chart.tsx`).
- The copilot:
  - example buttons return Verified answers, with SQL and source;
  - the guard produces Exploratory and Blocked;
  - Not answerable names the owner from `gaps.yaml`.
- A hosted skeleton behind a passcode.

**Minimum after CP2 (by 21:00; sized at about 6 developer-hours, see §6):**
1. The gap-to-proof loop end to end: the tile turns green on load, and asking again returns Verified.
2. Load Receipt UI and passport drawer wired.
3. The xlsx export with a visible "Burimi" column, the "Burimet" sheet and cell comments (about 15 minutes for the comments).
4. **One plausibility check shown as a "signal"**, the CP1 continuity.
5. SMP coverage states (only if approved), including "national (AMVV from MoF data)" for #41-52.
6. `GET /indicators/{code}` JSON plus the open-data CSV.
7. REPLAY/snapshot fallback mode (finished before 20:30 and listed on the CP3 sheet).
8. CP2 feedback fixes.

**Stretch, only if the minimum is green at 19:30:**
- Recipe reuse and the format-drift beat, if they were not built before CP2.
- The question card for amber columns.
- The accuracy chip.
- Three more check rules with "accept with reason".
- The population pin UI.
- Confirm/versioning (v1 → v2 with a reason).
- An MCP stdio server with Claude Desktop.
- The Kosovo MPMS pack toggle (only if it computes at least 3 real indicators).
- The passport compiler as a Q&A beat.

**Cut order, first cut first:**
1. MCP / Claude Desktop.
2. The Kosovo pack toggle.
3. Confirm/versioning.
4. The accuracy chip.
5. The population pin UI (keep the red tile text).
6. Check rules beyond the one signal.
7. The question card (keep the chips and the confirm step).
8. Recipe reuse.
9. The SMP coverage page (keep a one-line coverage summary in the deck).
10. XLSX reading (go CSV only).

**Never cut:**
- live ingest with mapping and receipt counts;
- passports with the lineage drawer;
- the board with computable and missing(owner) states;
- the copilot with visible SQL, labels and the refusal that names the owner;
- one trend chart;
- the xlsx with the "Burimi" column.

### 5.7 Hosting, submission and key protection

| Item | Owner | Deadline | Detail |
|---|---|---|---|
| Event repo | Tech A | 01:30, or 10:00 if the invite or URL only arrives at the stand-up | Add the event GitHub organisation's private team repo as a remote and push the **full history**, including the pre-event commits, which are the rule 10.2 evidence. |
| Branch for the tag | Tech A | before 21:00 | Merge `codex/civic-interface` into `main`, or agree with the organisers which branch carries the release tag. |
| Hosted skeleton | Tech B | 09:00 | Vercel (web) plus a Hugging Face Space or Render (API) returning `/health`. Environment variables and CORS set. Passcode on. |
| Key protection | Tech B | before the first hosted LLM call | Keys live server-side only. Persisted spend (`llm_call`). `LLM_BUDGET_USD` at about 60-70% of the real cap. Per-IP rate limits on `/ask` and `/ingest`. A small separate budget for hosted ingest. Example-question answers cached and badged "CACHED". |
| Data on the hosted link | Domain | with the §9.1 request | Ask whether a passcode-protected link may show package data. If not, the hosted link shows the flow on derived or synthetic data labelled SINTETIKE, and the live demo runs on localhost (allowed). |
| Tags | Tech A | 21:00 (`v0.9-cp3`) and Sun 08:30 (`v1.0.0`) | Tag on the agreed branch and push. |
| Demo video (60-90 s, narrated) | Product | Sat 22:30 | Link it in the README and on deck slide 4, for the cross-event comparison. |
| Submission form | Domain | Sun 10:30 | Deck, demo link (with passcode), release tag, Annex E declaration. |

**API key assumptions to confirm at 01:30.** Is the organiser key Anthropic? (The guide says "Claude or GPT".) Does Claude Code run on a personal plan, not on the capped organiser key? If the key turns out to be GPT, decide immediately between using the team's own Claude key (declared) and swapping the model behind `client.py`.

---

## 6. Build plan: Sat 00:30 to Sun 11:00

Rules:
- **No developer time goes to hero-only code before CP2.** The loop is built from the core: lineage (`row_no`), passports with a missing(owner) state, the four-label `/ask` contract with `gaps.yaml`, and the sandbox.
- The product person builds the new UI components against fixtures before CP2, so developers only wire them.
- Developers keep coding through 15:00-17:00, except for the team's CP2 slot.

Realistic developer capacity from 15:00 to 21:00 is about 8 developer-hours if developers code through the CP2 window and skip pitch-craft, and 5-6 if they do not. The post-CP2 minimum is sized at about 6.

| Time | Tech A (backend and data) | Tech B (copilot, web, deploy) | Product / Design | Domain / Business |
|---|---|---|---|---|
| **00:30-01:30** | **All four:** inventory the package (README, files, columns, formats). Run **Gate 1** (counts A-D, §5.4). Fix canonical model v1. Freeze the JSON contracts: ingest preview/commit including the receipt, `/indicators` including state and owner, `/ask` including label and gap. Confirm the API key provider. | | | |
| 01:30-05:00 | Push to the event repo if the URL is known. Reader (CSV, then openpyxl), PII gate, profile, `complete_json`, mapper with fallback, DDL with `row_no`, commit and reconcile counts, `llm_call` persistence. Tests. | sqlguard with about 20 allow/deny tests, Parquet sandbox, `/ask` returning Exploratory, Blocked and Not answerable (from `gaps.yaml`), `apiPost`, `ask.tsx` wired. **04:15-05:00: hosted skeleton** (Vercel plus HF or Render `/health`, CORS environment, passcode). | 01:30-03:30: screen specs (gap tile, step log, receipt, passport drawer, label states); sq/en strings. | 01:30: **send the organisers the §9.1 approval request.** 01:30-03:30: 8-12 KPI passports in `core_kpi.yaml` from package columns; Annex A coverage states (labelled "pending approval"); `gaps.yaml` content; expected values by hand in Excel; 24-question golden set; desk sheet. |
| Sleep | 05:00-08:30 | 05:00-08:45 | 03:30-08:00 | 03:30-08:00 |
| 08:00-09:00 | 08:30: passport registry, `core_kpi.yaml` loaded, `/indicators` with states. | 08:45: pull and run locally. | `indicator-grid.tsx`, `gap-card.tsx`, `passport-sheet.tsx`, `load-receipt.tsx` against fixture JSON (new files only). | Check the organisers' channel for approval answers; print the desk sheet. |
| **09:00-09:30** | **Mandatory stand-up: all four attend.** Ask for the event repo URL if it is still missing, and repeat the approval request if there is no answer yet. | | | |
| 09:30-10:00 | Lineage endpoint. | `overview.tsx` and `trend-chart.tsx` on `/indicators`. | Municipal ICT presentation (with Domain); take notes (§9.2). | Municipal ICT presentation. |
| **10:00 gate** | **One package file ingests end to end into tiles?** If not: drop XLSX, recipes and the question card; go CSV only. | | | |
| 10:00-13:00 | Verified routing through the registry; recipes by fingerprint (only if the gate is green); seed script plus `make demo-reset`; rate limit. | `csv-import.tsx` → server (preview, confirm, commit); example buttons → Verified; free-text intent → passport or guarded SQL; wire `passport-sheet`. | Component polish; wire help for Tech B. | **10:00-13:00 municipal Q&A desk:** domain facts, the SMP workflow and staff-days, the passport document, the blank questionnaire, the quote. Report back at 11:30 and 13:00. |
| **12:00 gate** | **Is free-text copilot routing reliable?** If not: ship Verified answers through the example buttons (deterministic passport code) plus Exploratory/Blocked through the guard. Free text stays Exploratory. | | | |
| 13:00-14:00 | Lunch (eat in shifts if integration is red). | | | **Gate 2:** decide from the organisers' written answers; brief the team. |
| 14:00-14:30 | Integration; seed `api/data/demo.duckdb`. | Localhost end-to-end run; update the hosted build if it is green. | CP2 demo script (5 minutes or less). | Rehearse the CP2 narration. |
| **14:30** | **Code freeze for the CP2 build.** Rehearse twice, then developers continue on feature branches. | | | |
| **15:00-17:00 CP2 window** (per-team slot between 15:00 and about 16:30) | All four at the team's slot. Must show: a package file → AI mapping with confidence → confirm → receipt counts → KPI tiles and trend update → one Verified answer with SQL, source and label → one Not-answerable answer naming the owner. **Outside the slot, developers code the post-CP2 list.** | | | |
| **17:00-17:45** | Codes (skip pitch-craft unless attendance is compulsory for all). | Codes. | **Pitch-craft session.** | **Pitch-craft session.** |
| 15:00-19:30 dev work (about 6 h total) | Coverage states for `al_smp.yaml` (if approved) about 1 h; xlsx with "Burimi" column, "Burimet" sheet and comments about 1.5 h; one check rule as a signal about 1 h; open-data CSV and `GET /indicators/{code}` about 0.3 h. | The gap-to-proof loop end to end about 1 h; Load Receipt UI wiring about 0.75 h; CP2 feedback fixes about 1 h; REPLAY/snapshot mode about 1 h (**done by 20:30**). | Deck v0 on the organisers' template (get it tonight); UX polish. | 19:30: `make eval` run 1; pitch script v1; confirm the quote wording and consent. |
| 19:00-20:00 | Dinner in shifts: Tech A 19:00-19:30, Tech B 19:30-20:00. | | | |
| **19:30 gate** | Kill switch: anything not working end to end gets hidden. Stretch goals only if the whole minimum is green. | | | |
| 20:00-21:00 | Stretch in cut order, or bug fixes. Merge to `main`. | Hosted build updated; REPLAY tested offline. | Screenshots for slide 4. | **20:00: draft the CP3 sheet** (template below); eval run 2 → commit `eval_result.json`. |
| **21:00 CP3** | **Scope freeze. No new features after this.** Submit the CP3 sheet. Tag `v0.9-cp3` and push. | | | |
| 21:00-00:30 | Bug fixes, tests, demo reset script. | Bug fixes; demo link check with the passcode. | **21:00-22:30: record fallback videos** (all envelopes plus the full flow) and the 60-90 s narrated cut. Then deck v1 (8 slides or fewer). | Annex E update (§10); Q&A answers; timed pitch rehearsal ×3 in English. |
| Sleep | 00:30-06:00 | 00:30-06:00 | 01:00-06:30 | 00:30-06:00 |
| **Sun 06:00-08:30** | README (with the video link), final tests, merge, **tag `v1.0.0` and push**. | Demo link check (hosted and localhost); `make demo-reset`; USB copy. | Final deck. | Final Annex E; submission form prepared. |
| **Sun 09:00-11:00** | **Mandatory pitch dry-run with a mentor. Book the earliest slot (09:00)** so there is time to act on feedback. | | Deck fixes from the dry-run. | **Submit by 10:30** (30 min buffer before 11:00). |
| **From 11:00** | Be stage-ready: the agenda allows pitches to start at 11:10. Laptop charged, demo reset done, hotspot on, files on the desktop and on USB. | | | |

**CP3 sheet (Domain drafts it at 20:00; submitted at 21:00):**

| Feature in the final demo | State at 21:00 (green / hidden) | Owner until submission |
|---|---|---|
| Live ingest with AI mapping and Load Receipt | | Tech A |
| Gap-to-proof loop (refusal → load → Verified → tile green) | | Tech B |
| Passport drawer with formula, SQL and source rows | | Tech B |
| KPI board, coverage counter and trend chart | | Tech B |
| Signal (one plausibility check) | | Tech A |
| xlsx export with "Burimi" column and "Burimet" sheet | | Tech A |
| SMP coverage map (if approved) | | Tech A |
| Indicator API and open-data CSV | | Tech A |
| REPLAY fallback | | Tech B |

Who does what until submission:
- Deck: Product.
- Annex E and submission form: Domain.
- Release, README and video link: Tech A.
- Demo link and fallbacks: Tech B.
- Presenters: Domain (problem, scale, next steps) and Tech B (demo driver).
- Technical Q&A: Tech A.

---

## 7. Pitch storyline, deck and demo script

### 7.1 The five minutes (in English, Albanian UI and tagline)

| Time | Beat |
|---|---|
| 0:00-0:25 | **Credit, then the problem.** "Elbasan is one of three national good-practice models for validating performance indicators (28 May 2026). Across Albania, 52 SMP indicators are still collected once a year, through an Excel questionnaire, a Google Form and an official letter, and the grant assessment that uses the 2025 data runs until 27 October. Department data lives in separate exports, and a number on a dashboard rarely shows which file it came from." Then the desk quote, if one was captured with consent (§9.4). *Confirm the recognition wording at the desk before using it.* |
| 0:25-0:45 | **Who we are.** "Sportel, sporteli i të dhënave (the data counter): raporto një herë, provo çdo numër. The municipality's new AI window answers citizens from the published report. Sportel produces and proves the numbers underneath, and can feed it." |
| 0:45-2:20 | **Live demo (§5.2).** WOW 1 at about 1:30 (same question, now Verified, from the file the juror chose). WOW 2 at about 2:05 (the Excel value with its "Burimi" source). State the leadership decision: which directorate to chase, which indicator is off track. |
| 2:20-2:40 | **Honest copilot, the other two labels.** One off-passport question → Exploratory, with its SQL. One request for personal data → Blocked. If eval ran: "Verified answers matched our hand-computed values in X of Y cases." |
| 2:40-2:55 | **Interoperability.** `GET /api/v1/indicators/{code}` returns the value, passport, lineage and basis. "Any AI window or national platform can cite this." |
| 2:55-3:05 | **Spoken AI declaration.** "Built with Claude Code. Claude Haiku maps the columns and Claude Sonnet reads the questions and phrases the answers. ChatGPT designed our pre-event UI prototype. Code computes every number." |
| 3:05-3:40 | **Why it works here.** No connectors, only the exports departments already make. UNDP found municipal digital readiness at 31/100 and donor systems discontinued when projects end: nothing fed them. Mapping costs about 1 cent per file. AI maps, code computes, a person confirms. The limits are on screen. |
| 3:40-4:15 | **Scale.** The same passport mechanism for Albania's 61 municipalities (60 reported 2025 data). A Kosovo MPMS pack for Gjakova, where the performance grant pays on 30 criteria (EUR 33.5 M, 2014-2023). Serbia next: Pirot posed the same challenge. Recipes can be shared between municipalities that use the same software. Price model: a flat annual fee per municipality, preferential for Elbasan, to be tested in the Validation Lab. |
| 4:15-5:00 | **Four weeks (§7.4).** Week 1: data agreement plus three real exports. Week 2: passports validated with the Performance Unit. Week 3: running on a municipal machine. Week 4: reproduce Elbasan's submitted 2025 return from exports, cell by cell. "Then the MVP Validation Lab and the February 2027 presentation to Elbasan. Raporto një herë." |

### 7.2 Deck outline (8 slides maximum, on the organisers' template)

Get the template tonight and map these eight slides onto its required sections; merge a team line into the title slide if the template has no team slide. **Retire the 14-slide `docs/pitch/sportel-deck.src.html`** (keep it only as a source for screenshots).

1. **Title:** "Sportel: Raporto një herë, provo çdo numër"; FirmatGroup with four names and roles; Track D; one line of AI declaration.
2. **Problem:** credit to Elbasan's practice; the national yearly loop (Excel, then Google Form, then letter); 3-4 **verified** numbers from §3 only; the desk quote.
3. **Solution:** one flow line: exports → shared model with lineage → passports → board, report with sources, honest copilot, API.
4. **Demo:** a three-screenshot sequence (refusal naming the owner → receipt → Verified with the green tile), plus a QR code or link to the 60-90 s video. This slide is the fallback if the live demo fails.
5. **AI, honestly:** what the AI does, what code does, the limits, accuracy by label, and what leaves the building.
6. **Scale and sustainability:** 61 municipalities; a Kosovo/Serbia pack table; exports only; one DuckDB file; runs on a municipal machine; open source; one LLM client with a no-model fallback; about 1 cent per file.
7. **Four-week plan and pilot path:** the dated plan with metrics (§7.4), mapped to the five dimensions of the MVP Validation Lab, ending at the Feb 2027 presentation. Relationship with Bashki te Forta / Smart Process: we feed it; we do not compete with it.
8. **Disclosure:**
   - data used (the package, plus approvals with approver names);
   - derived or synthetic data, labelled;
   - external resources;
   - AI tools: Claude Code; Claude Haiku 4.5 and Sonnet 5 in the product; ChatGPT for the pre-event UI prototype; Claude for research assistance; Claude Desktop and the MCP SDK if used;
   - the pre-existing scaffold.

### 7.3 Live demo script and no-network fallback

- **Before going on stage:**
  - run `make demo-reset` (clears recipes and restores the pre-drop state);
  - pre-warm the copilot's example questions;
  - put the envelope files on the desktop and a USB stick;
  - have the xlsx already open in Excel **and** tested in LibreOffice;
  - run on localhost (allowed), with a phone hotspot as a backup network.
- **Say it on stage:** "These are files from the organisers' package. No code or saved mapping exists for them, the recipe store is empty, and this AI call is live." Show the LIVE or REPLAY badge honestly. Never say "unseen" (we tested every file) or "real exports" (unless the organisers confirm they are unmodified department exports).
- **If the LLM is slow or unreachable:** the deterministic mapper takes over with confidence capped at 0.6, so everything turns amber and needs clicks, and the flow still completes. Say: "The AI is unreachable, so it asks more questions."
- **If the app is down:** switch to REPLAY mode (a saved step log and result, visibly badged). If that fails, play the Saturday 21:00-22:30 recording, which covers every envelope, so any choice has footage. The last resort is slide 4.
- **Never accept a juror's own file.** Say "please pick one of the envelopes". It doubles as a trust moment on rule 10.3.

### 7.4 Four-week mentoring plan (for slide 7 and the "next steps" score)

| Week | Deliverable | Success metric |
|---|---|---|
| 1 | A data-processing agreement with the municipality; three real department exports onboarded with receipts; the passport document and blank questionnaire from the Performance Unit; owners confirmed for the gap list. | Agreement signed; 3 receipts that reconcile. |
| 2 | 16 passports reviewed with Performance Unit staff; feed format agreed with the Bashki te Forta / Smart Process AI-window team. | Number of passports marked "validated". |
| 3 | Running on a sandbox VM or a municipal machine (full on-prem deployment is a pilot-phase step subject to municipal IT approval); eval rerun on 50 real staff questions. | Accuracy by label on staff questions. |
| 4 | A parallel run with the Performance Unit: reproduce Elbasan's 2025 SMP return (submitted July 2026) from department exports and compare it cell by cell. This validates the tool, not the municipality. | Share of matching cells; explained differences; estimated staff-days per cycle. |
| After | MVP Validation Lab evidence on its five dimensions: feasibility (week-4 match rate), interoperability (feed and SMP-shaped export), scalability (effort estimate for a Gjakova MPMS pack), usability (staff sessions), commercialisation (preferential-price pilot offer). | Feb 2027 presentation to the Municipality of Elbasan. |

---

## 8. Jury Q&A: the hardest questions

1. **"The municipality is launching its own AI window with Bashki te Forta, Helvetas and Smart Process. Why a second system?"**
   It is not a second chatbot. Your window answers citizens from the published report. Sportel sits upstream: it computes and proves the indicators from department exports, and its API can hand your window verified numbers with their source and date. We would like to agree the feed format in week 2.

2. **"Are you saying our numbers are wrong?"**
   No. Elbasan is a national good-practice model for validating its indicators. Where figures differ, such as the population base, both are correct under different definitions: the census counts residents, and the civil registry also keeps people who emigrated. The gap is only that no screen says which one was used. Sportel lets the Performance Unit pin the definition the SMP uses and stamps it on every output. The week-4 comparison tests our tool against your validated return, not the other way round.

3. **"Clear the cache and run it again. What exactly goes to the model? Can it run locally?"**
   (Clear it and run it.) The `llm_call` log shows what was sent: column headers, profile statistics and at most 5 masked sample values per column, never rows. Personal columns are dropped before that. All LLM calls go through one client, and today that client calls Claude through the Anthropic API. Without any model, mapping falls back to rules and asks more questions, and the indicators, lineage and API keep working. A local or EU-hosted model is an option to evaluate in mentoring; we do not claim it today.

4. **"Were these files really unseen?"**
   No, and we never claim that. We tested every envelope. What is true is that no code or saved mapping exists for them: the recipe store was empty on screen, and the AI call was live with its latency and cost shown.

5. **"What is your accuracy, and against what?"**
   We report it per label. Verified answers use fixed SQL and matched our hand-computed values in X of Y cases; Exploratory answers matched in Y2 of Z. The set is our own 24 questions, frozen before tuning, with the commit hash in the release. It is indicative, not a benchmark. In week 3 we rerun it on 50 real questions from your staff.

6. **"Next year Finance changes its Excel layout. Who fixes the mapping?"**
   The recipe is keyed to the header fingerprint. A changed file does not map silently: it stops and asks, re-maps with AI, and saves a new recipe (a 20-second demo, if the format-drift beat is built).

7. **"Where does it run?"**
   A single DuckDB file and two containers (`docker compose up`) on a municipal server. The hosted demo sits behind a passcode. There are no live connectors to your systems; it reads the exports you already produce.

8. **"Isn't this Power BI, Flatfile or dbt?"**
   The techniques, yes: metrics as code and AI column mapping. Those tools need paid capacity and a data engineer, and none of them knows the SMP passports or ships a report where every value names its source rows. Our running cost is about 1 cent per file.

9. **"AMVV already has a Google Form, and the KVA verifies the data. Why this?"**
   The Google Form collects final numbers typed in by hand. Sportel produces those numbers with evidence, so checking a submission against its sources becomes one click. It fills your existing channel; it does not replace it.

10. **"Smart Processes already has an SMP information system for municipalities. Isn't this the same?"**
    That kind of system is where final values are entered and managed. Sportel works one step earlier: it computes the values from the exports departments already produce and keeps the source rows. Our export is SMP-shaped so it can feed that system or the Google Form. We would rather align with it than compete.

11. **"The finance indicators come from the Ministry of Finance anyway."**
    Correct. Indicators 41-52 are computed nationally by AMVV from Ministry of Finance data, and Sportel marks them that way rather than computing them. Our value lies in the indicators the municipality reports itself and in a monthly internal view between returns.

12. **"Who maintains the passports when the methodology changes?"**
    Passports are versioned YAML with tests. Each one says "awaiting validation" until the Performance Unit approves it, and formulas not stated verbatim in the source are marked "draft". The natural long-term owner of the national pack is AMVV or Bashki te Forta; each municipality owns only its recipes.

13. **"Who else benefits, and what would Pirot or Gjakova cost?"**
    Confirmed indicators are published read-only as CSV/JSON under an open licence, with their version history, for the OGP forum and civil society. For Gjakova, the MPMS pack uses the same mechanism; for Pirot, a pack for the Serbian programme-budget indicators. Onboarding a second municipality mostly means writing recipes for its exports; we will measure that effort in mentoring. The price model is a flat annual fee per municipality, preferential for Elbasan, and we will validate it in the Lab rather than quote a number today.

Also keep ready (one line each):
- **"What decision does this support?"** "Which directorate to chase this month, which indicator is off track, and whether the July return is complete before it leaves the building." Next module: "Dashboards analyse what is in the books; later we can look for what never got there."
- **Scanned reports:** "History as data is on our roadmap. Claude's Citations API cannot cite scanned PDFs, so it needs OCR first."

---

## 9. Requests and questions: organisers tonight, ICT session at 09:30, desk from 10:00 to 13:00

### 9.1 Written request to the organisers (send at 01:30; repeat at the 09:00 stand-up)

> Team FirmatGroup (Track D) asks for written approval under rule 10.3 for:
> (1) using the public SMP 2024 Annex A indicator list, and the indicator passport definitions if public, to build an indicator coverage map;
> (2) Census 2023 population as a denominator, if it is not in our package;
> (3) citing public figures in our pitch (SMP process, PBG assessment dates and pool, UNDP e-readiness score, Kosovo performance grant, Serbian LTI);
> (4) export-shaped files derived from our package files (title row, merged header, TOTALI row), labelled "derived from package file X";
> (5) a passcode-protected hosted demo showing package data and aggregates, and whether an open-data CSV of aggregates may be public under CC BY 4.0;
> (6) committing package files to our private event repository and container image.
> Could you also confirm the provider of our AI key (Claude or GPT) and the event repository URL? Thank you.

### 9.2 At the ICT presentation (09:30), listen for and note

- Which systems produce exports (SIFSHI/AFMIS, the local tax system, the request/complaint register, HR), and in what formats (xls, xlsx, csv, pdf)?
- Who holds the Performance Coordinator role, and which sector compiles the SMP return?
- Does the Smart Process AI window have, or plan, an API? What data does it read?
- Hosting rules: is cloud allowed, or is on-prem required? On which infrastructure? (Do not name AKSHI or anything else unless it is said here.)

### 9.3 At the municipal desk (Domain/Business, with a printed sheet)

1. "How is the SMP return filled today? Who does it, from which exports, and **how many staff-days** does the July cycle take?" (This is what lets us describe Elbasan's workflow at all.)
2. "Which indicators are hardest to get, and which directorate is usually last?" (Ask neutrally, and never quote the answer on stage as blame.)
3. "Which population figure is official for per-capita indicators?"
4. "Can we have the indicator passport document and a blank SMP questionnaire, and the four-monthly monitoring template?"
5. "Are the files in our package typical of what departments actually export?"
6. "Would the Performance Unit review our passports in the mentoring phase?"
7. "How would you like us to describe the 28 May recognition, if we mention it?"

Data-use approvals go to the organisers (§9.1), not to the desk.

### 9.4 Capturing a quote

- Ask: "May we put one sentence from you on our problem slide, attributed by role only (e.g. 'a specialist in the Statistics and Performance Sector')?"
- Prompt with a question that invites a concrete answer: "What happens in the week before 31 July?"
- Write it down verbatim in Albanian, read it back, and get a spoken or written OK.
- Record the date, role and consent in Annex E.
- Never attribute a name without explicit consent, and never use a quote that criticises a colleague or department.

---

## 10. Risks, honesty and rule compliance

**Rule 10.2 (pre-existing work):**
- Annex E already discloses the pre-event scaffold and the ChatGPT-designed UI prototype with synthetic data (commit 5a628d2).
- Mock data (`pulse-data.ts`) must not appear in the final demo except as a labelled REPLAY snapshot.
- All core logic (ingest, passports, copilot, export) is built during the event, and the pushed commit history shows it.

**Annex E updates** (`docs/annex-e-declaration.md`; Domain owns them, final by Sun 08:30):
- **Rewrite "Built during the hackathon" to match the CP3 sheet.** The current text lists "signals; and the AI-generated briefing". Replace it with what was actually built, for example: ingest with AI mapping and load receipts; indicator passports with lineage; the KPI board with trend and one plausibility signal; the honest copilot with four labels; the xlsx report with sources; the indicator API.
- **Keep "All numbers shown in the final demo come from the organisers' data" true, or amend it** (for example: "…or from derived files labelled as such").
- **Add an "External resources and approvals" table** with the columns item | source | approved by | channel | time. Rows: the SMP 2024 methodology, Census 2023, cited public figures, derived files, the hosted link.
- **AI tools:** add Claude for research assistance (pitch evidence), plus Claude Desktop and the MCP SDK if used. Keep Claude Code, Claude Haiku 4.5 and Sonnet 5 in the product, and ChatGPT for the prototype.
- **Pre-existing components:** list the scaffold and any open-source libraries.

**Rule 10.3 (data):**
- Only package data and approved items. No juror files.
- No fabricated personal columns to "show" the PII gate. If there are none, the truthful screen says "no personal columns found".
- Synthetic or derived files are labelled SINTETIKE or "derived from package file X".
- Nothing from the Performance Report, the PBA or the KLSH audit goes on screen without approval.
- Annex A work stays "pending approval" until it is approved.

**Honesty:**
- Real counts only; no "illustrative" numbers on stage.
- Disclose caches and replays with badges.
- Label formulas "awaiting validation", and mark as "draft" any formula not stated verbatim in the source.
- Say "reported" for anything in §3 not marked Verified, and "we found none" rather than "none exists".
- Never say "unseen", "your questionnaire" or "fills itself" unless Gate 1 found 5 or more non-finance inputs, and even then say "SMP-shaped draft".
- Never claim to cut AMVV's lag. Say "monthly internal view; July return ready earlier".
- Do not claim local-model support.

**Political:**
- Open with credit to Elbasan's recognition.
- Say "the municipality announced" the AI window, not the Deputy Mayor, and frame it as a partner.
- Never say "your documents disagree". Say "two correct definitions under one name", and only in Q&A.
- No Diella critique, no "broken promises" framing, no KLSH figures on slides.
- Do not lead with finance tiles: Financat Vendore (OSF-backed) already covers finance, and #41-52 are national.

**Hosting and keys:**
- The demo link is protected by a passcode, rate limits, persisted spend and a budget at 60-70% of the cap.
- The key stays server-side.
- Ask the organisers whether a passcode-protected link may show package data.

**Technical** (verified tonight unless marked otherwise):
- DuckDB refuses a same-file `read_only` connection: use one connection plus cursors and the Parquet sandbox.
- The DuckDB excel extension collapses merged-title sheets and installs over the network: use openpyxl.
- `mcp` 2.x removed `FastMCP`.
- Sonnet 5's adaptive thinking plus the `max_tokens=1024` default truncates output.
- Spend resets on reload until `llm_call` is persisted.
- Stdout pollution breaks MCP over stdio (reported by research, not tested here).
- Hugging Face Spaces disks are ephemeral: seed at startup.
- CORS currently allows only localhost:3000.
- In Next.js 16, `middleware.ts` is renamed `proxy.ts`.
- A research subagent ran `taskkill /F /IM python.exe` during its spike: restart the API dev server if it was running.

**Budget:** the whole package costs about USD 10-20: mapping about $0.01 per file, the copilot $0.01-0.04 per question, an eval run about $0.5. Log spend per feature.

**Schedule:**
- The CP2 core is the long pole, and the hero loop is mostly that core.
- Kill switches at 10:00 (ingest), 12:00 (copilot) and 19:30 (everything).
- The REPLAY fallback is finished before 20:30; videos are recorded after the 21:00 freeze.
- The Sunday dry-run is mandatory: book 09:00.

---

## 11. Sources and fact status

**Dropped or corrected after the review:**
- "Municipalities pay EUR 7-30k a year": not in the cited UNDP report. Dropped.
- "61 municipalities reported": it is 60 for the 2025 data (61 municipalities exist).
- "200 M lek grant pool": search summary only. Dropped.
- "The 14 Jul validation meeting": now "a July 2026 validation meeting (article dated 14 Jul 2026)".
- The KLSH "82 M lek": a press headline ("820 milione", old lek). Press only; off slides.
- "Deputy Mayor announced the AI window": it was the municipality.
- AKSHI: unverified. Removed.
- "Power BI Copilot is off in the region": a Fabric admin can enable it. Removed from Q&A.
- "The model is a config value / runs locally": the code is Anthropic-only. Reworded.
- "2026 SMP draft vs manual" in week 4: the 2026 return is due July 2027. Replaced with the 2025 return.

**URLs used:**
- SMP 2024 report: https://qeverisjavendore.gov.al/wp-content/uploads/2025/11/SMP-2024.pdf
- Bashki te Forta home; PBG 2026 assessment: https://bashkiteforta.al/en/home/ · https://bashkiteforta.al/nis-procesi-i-vleresimit-per-grantin-e-bazuar-ne-performance-2026/
- Performance grant EUR 2.5 M (RTSH): https://rtsh.al/grant-performance-ministri-demo-2-5-milione-euro-per-bashkite-qe-ofrojne-sherbime-me-te-mira/
- Elbasan AI pilot: https://elbasani.gov.al/bashkia-elbasan-pilot-per-perdorimin-e-inteligjences-artificiale-ne-transparence-dhe-llogaridhenie/
- Elbasan national good-practice recognition (28 May 2026): https://kohajone.com/aktualitet/qeverisje-e-hapur-dhe-vendimmarrje-me-evidence-praktika-e-bashkise-se-elbasanit-merr-vleresim-kombetar/
- 2025 report validation (article dated 14 Jul 2026): https://kohajone.com/aktualitet/bashkia-elbasan-mat-performancen-e-saj-per-vitin-2025-nis-procesi-i-validimit-te-raportit-vendor/
- Scanned Performance Report 2025: https://elbasani.gov.al/wp-content/uploads/2026/09/Raporti-i-performances-2025.pdf
- Statistika vendore 2025: https://elbasani.gov.al/wp-content/uploads/2026/03/Statistika-vendore-2025-Elbasan.pdf
- Budget Monitoring 2024: https://elbasani.gov.al/wp-content/uploads/2025/05/RAPORT-MONITORIMI-BUXHETI-2024.pdf
- PBA 2026-2028 final tables: https://elbasani.gov.al/wp-content/uploads/2026/02/Tabelat-e-PBA-2026-2028-Faza-3-Finale-109-Bashkia-Elbasan-26_01_26.pdf
- Elbasan open data page; Monitoring Directorate: https://elbasani.gov.al/open-data-2/ · https://elbasani.gov.al/drejtoria-e-monitorimit/
- Census 2023 (INSTAT): https://www.instat.gov.al/en/themes/censuses/census-of-population-and-housing/publications/2023/main-results-of-the-population-and-housing-census-2023/
- KLSH 2024 audit (press summary, context only): https://www.voxnews.al/biznes/zhduken-820-milione-leke-nga-bashkia-e-elbasanit-i113566
- Municipal investment execution, H1 2026 (press): https://www.korcaboom.com/sq/post/tender%C3%AB-me-miliarda-investime-t%C3%AB-bllokuara-bashkit%C3%AB-realizuan-vet%C3%ABm-14-4-t%C3%AB-buxhetit-n%C3%AB-6-muaj
- UNDP e-readiness: https://www.undp.org/sites/g/files/zskgke326/files/2024-09/dra_national_report_final_eng.pdf
- Investment Council paper: https://www.investment.com.al/wp-content/uploads/2025/10/Investment-Council_On-Digital-Transformation-of-Public-Local-Services-for-Businesses.pdf
- Smart Processes projects: https://smartprocesses.eu/projects/
- Kosovo SMPK: https://mapl.rks-gov.net/wp-content/uploads/2024/02/Dokumenti-kryesor-i-SMPK_2023_Final_Alb_29.02.pdf
- Kosovo performance grant (DEMOS): https://helvetas-ks.org/demos3/multimedia-stories/transforming-citizens-lives-kosovos-decade-evolution-of-the-municipal-performance-grant/
- Serbia LTI 2026: https://srpske.rs/vesti/politika/2026/09/23/indeks-transparentnosti-opstina-prosek-52-cetvrtu-godinu-presevo-poslednje-sa-28
- NALED LEI: https://lei.rs/stranice/o-projektu
- Financat Vendore (OSF): https://osfwb.org/event/prezantohet-platforma-financat-vendore/
- Belgrade AI4Society call (Pirot challenges): https://rc.gradjanske.org/otvoren-poziv-za-hakaton-ai4society-digitalna-resenja-za-lokalne-probleme/
- Competitor repos: https://github.com/gjergjquni/ai4society-gjakova-hackathon · https://github.com/damnilo/AI4Society-Hackathon
- Faktoje monitoring: https://faktoje.al/40-premtime-10-bashki-faktoje-prezanton-raportin-e-monitorimit-ne-elbasan/
- OGP Elbasan action plan: https://www.opengovpartnership.org/documents/action-plan-elbasan-albania-2025-2027/
- Reputeo: https://www.thereputeo.com/
- OSFWB open data project: https://osfwb.org/project/open-data-and-digitalisation-in-the-western-balkans/
- dbt semantic layer vs text-to-SQL 2026: https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026
- Spider 2.0: https://spider2-sql.github.io/
- NYC MyCity failure: https://themarkup.org/news/2024/03/29/nycs-ai-chatbot-tells-businesses-to-break-the-law
- Databricks Genie: https://www.databricks.com/blog/aibi-genie-now-generally-available
- Power BI verified answers: https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-prepare-data-ai-verified-answers
- Flatfile: https://flatfile.com/product/mapping/
- OneSchema: https://docs.oneschema.co/docs/ai-bundle
- Osmos / Fabric: https://www.techzine.eu/news/data-management/137689/with-osmos-acquisition-microsoft-fabric-tackles-messy-data/
- Magneto (VLDB 2025): https://www.vldb.org/pvldb/vol18/p2681-freire.pdf
- DuckDB Excel extension: https://duckdb.org/docs/current/core_extensions/excel.html
- Claude Citations (scanned PDFs): https://platform.claude.com/docs/en/build-with-claude/citations
- Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Behn, PerformanceStat: https://www.hks.harvard.edu/sites/default/files/centers/taubman/files/performancestat.pdf
- JetBrains judging notes: https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/
- data.gouv.fr MCP: https://github.com/datagouv/datagouv-mcp

**Repo files that ground this plan:**
- `C:\Users\greisi\StudioProjects\elbasan-pulse\docs\superpowers\specs\2026-09-25-elbasan-pulse-design.md`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\docs\pitch\cp1-problem-lock.md`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\docs\annex-e-declaration.md`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\api\app\llm\client.py`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\api\app\warehouse\db.py`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\api\app\config.py`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\web\src\components\pulse\csv-import.tsx`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\web\src\components\pulse\trend-chart.tsx`
- `C:\Users\greisi\StudioProjects\elbasan-pulse\docs\pitch\sportel-deck.src.html` (to retire)
