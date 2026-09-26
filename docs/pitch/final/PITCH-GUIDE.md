# Sportel final pitch: guide (5 min + 3 min Q&A)

The deck is `Firmat_Final.pptx` (8 slides, in the Pitch Craft order). After mentor feedback it carries **minimal text in big type** (20pt+, numbers at 80–96pt). Everything you say is in each slide's **speaker notes** (about 720 words). To rebuild after an edit, change `src/build.js` or `src/notes.js` and run `node src/build.js Firmat_Final.pptx` in a folder with `pptxgenjs sharp react react-dom react-icons` installed.

## 1. The selling point in one line

> **"A head of department can defend every number in the meeting: Sportel builds the indicators from the Excel files departments already have, shows where each number came from, and names who to ask when data is missing."**

Why this wins on the scorecard:

| Criterion | What earns the points |
|---|---|
| Relevance 20 | It answers the Track D brief directly (a unified view for performance monitoring) for the people named in it: leadership and department heads. |
| Feasibility 20 | No connectors and no new data entry: it works from the exports departments already make. It runs on one small server, and without an AI key it still works in rules mode. |
| AI 15 | The AI does real work (it reads messy columns and Albanian questions), is honest about its limits, and never writes a number. |
| User logic 15 | One loop: gap → owner → upload → receipt → verified → Excel with a "Burimi" (source) column. |
| Scalability 10 | 61 Albanian municipalities report the same 52 indicators, plus Kosovo's 38 on the same model. |

## 2. The workflows in plain words (for the team)

1. **Paneli (the board):** 13 indicator tiles. **Green** means computed, with proof. **Grey** means *"MUNGON EKSPORTI · Përgjegjës: Drejtoria X"*: that directorate has not sent its file. The box *"Për drejtuesit, këtë muaj"* shows the head of department **whom to ask** and **which indicators are off target**. These are the decisions.
2. **Pyet të dhënat (ask):** a question gets one of 4 stamps, and **code** decides which:
   - **E VERIFIKUAR:** an official formula ran; the answer shows it in plain words (*Si u llogarit*) and the source files and rows.
   - **EKSPLORUESE:** a quick look at the data, not a defined indicator; read it with care.
   - **E BLLOKUAR:** for example, a request for names or phones is refused.
   - **PA PËRGJIGJE:** the data is missing; Sportel names the missing file and its owner and guesses nothing.
3. **Integro të dhëna (upload):** drop an Excel or CSV file. Code finds the header, the units (`000 lekë` ×1,000) and the TOTAL row, and **removes personal columns before the AI**. The AI (or the rules, without a key) proposes which column means what: green means sure, amber needs a click. A person confirms. A "recipe" is saved, so next month the same file loads in one click. If the layout changes, Sportel stops and asks.
4. **Fatura (load receipt):** rows read = loaded + excluded, and the sums match the file's own total row. This proves nothing was lost.
5. **Pasaporta (passport):** click a tile to see its formula, SQL, source files and rows, owner and checks. It stays marked "Draft" until the Performance Unit validates it.
6. **Shkarko raportin (.xlsx):** an Excel report with a **Burimi** (source) column next to every value.
7. **Header badges:** *Të dhëna sintetike* (synthetic data), and *AI LIVE* / *RREGULLA* / *REPLAY*. Always say the mode that is on screen.

## 3. The demo video (recorded: `demo/sportel-demo.mp4`; script in `VIDEO-SCRIPT.md`)

The video below was recorded from the running app with a hand-built waste CSV. The shot list that follows is for a manual re-take with the envelope file, if you want one.

**Tool:** OBS Studio (free), or Windows **Win+G** (Game Bar) or **Win+Shift+R** (Snipping Tool video). Record at 1920×1080, browser at 110–125 % zoom, notifications off, synthetic badge visible.

**Before recording:**

```bash
make api
```

```bash
make web
```

```bash
make demo-reset
```

**Switch the app to English:** click the language button (`SQ`/`EN`) at the top right of the header, so it shows **EN**. The whole UI, the answers and the step log switch to English. The data files themselves keep their Albanian column names; that is real municipal-style data, so leave it.

Open every route once so it has compiled: `/`, `/ask`, `/ingest`, `/indicators/REV-02`. Copy `api/samples/zarfi-2_SINTETIKE_taksat_tarifat_arketimi_2026.xlsx` to the desktop.

**Shot list (envelope 2, target 75–90 s after cutting):**

| # | Screen | Action (English UI) | Voice-over (head-of-department voice) |
|---|---|---|---|
| 1 | **Board** `/` | Hover the counter **6/13 indicators with proof**, then a grey **Missing export** tile, then the box **For leadership, this month** | "I'm the head of Public Services. 6 of 13 indicators have proof. Grey tiles tell me which directorate owes data." |
| 2 | **Ask the data** `/ask` | Click the example *How much of the waste management cost does the cleaning fee cover?* | "The deputy mayor's question. Sportel doesn't guess…" |
| 3 | Answer | Hold on **NOT ANSWERABLE** + *Owner: Local Revenue Directorate* + *No number was guessed* | "…it tells me the revenue export is missing and who owns it." |
| 4 | **Integrate data** `/ingest` | Drag the zarfi-2 file onto **Drag the file here** (backup: the **Envelope 2** card); let the steps under **What the code did** appear | "My colleague drops the Excel file they already have. Code finds the units and the total row and removes personal columns." |
| 5 | Column mapping | Show the confidence bars; if any row needs it, **Confirm** / **Confirm all**, then **Confirm and load** | "The AI suggests what each column means, from the column names only. A person confirms." |
| 6 | **Load receipt** | Hold on **Rows read 100 = 96 + 4** and the file-total check | "The receipt: every row counted, totals match the file's own total." |
| 7 | **Ask the data** | Click the **same example** → **VERIFIED**, **55.0%**, **Sources** with 2 files | "Same question, now verified, with its source rows." |
| 8 | **Board** | **8/13**; click the REV-02 row → indicator passport (formula, rows, chart) | "Now I can show exactly where this number came from." |
| 9 | Excel | **Download the report (.xlsx)** → open it and show the source column | "This is what I take into the council meeting." |

- Cut out waiting time. Keep "Synthetic data" visible (it is in the header) and add a small caption "Synthetic demo data".
- In PowerPoint, add the video to **slide 3**: Insert → Video → This Device, resize it over the two screenshots, then Playback → Start: *When Clicked*. Alternatively, play it from a separate player. Keep slide 3 as the fallback if the video fails.
- Also record one backup take each for envelopes 1 and 3.

## 4. Delivery

- Aim for one or two speakers. Suggested split: slides 1–2 and 4–8 by the Domain person, slide 3 (demo) by Tech B.
- Rehearse three times with a timer. Target: 4:45.
- **Say:** "AI proposes, code computes, a person confirms." "Synthetic files." "The Excel files departments already have."
- **Never say:** that Elbasan's numbers or process are wrong, manual or broken; "real exports"; "the AI calculated"; any criticism of the city's new AI window. Present it as a partner Sportel could feed.

## 5. Q&A: answer first, explain second

| Question | Answer |
|---|---|
| Data privacy? | No values leave the server. The AI sees column names and the question only. Personal columns are removed first, code computes every number, and every AI call is logged. In the pilot, Sportel runs on the municipality's server; for the AI, it uses a local model or an EU provider with zero data retention. |
| No IT capacity? | No integration and no new data entry: staff upload the exports they already make, and the format is remembered. It runs on one small server and works without an AI key. Training takes two half-days. |
| Maintenance cost? | €4–6k a year, plus under €100 a month to run. These are estimates, not quotes. |
| What if the AI hallucinates? | It can't put a number on screen. Code computes every value with a fixed formula. Missing data gives "no answer" plus the owner. On our own 24 test questions (rules mode) it got 24 of 24; indicative only. |
| Why not Excel or Power BI? | They show numbers; they don't prove them or say who owes missing data. Excel remains our output, with a source column. |
| Elbasan already has an AI window? | It explains the finished annual report to citizens. Sportel builds and proves the numbers underneath, every month, and could feed that window. |
| No internet or no key? | It keeps working in labelled rules mode, on localhost. |
| Is this our real data? | No. Every file is synthetic and labelled; the organisers' data goes through the same pipeline. |

## 6. Data safety (the mentor's point)

**What changed in the code:** AI column mapping now sends **column names and types only**. No cell values and no rows are sent (`LLM_SEND_SAMPLES=false` is the default; sample values go only if someone switches it on). Personal columns were already removed before anything else runs. The only other thing sent is the question a user types. Tests cover both cases.

**Say on stage (slide 5):** "The AI never sees the numbers. It reads column names only; code computes every number. In the pilot, Sportel runs on the municipality's own server."

**Three deployment levels to offer:**

| Level | How | What leaves the building | Extra cost |
|---|---|---|---|
| 1. Fully local (HR, salaries, taxpayers) | Municipal server plus an open model (gpt-oss-20b, Qwen 7–14B or Mistral Small) through Ollama | Nothing | One 16–24 GB GPU; or rent about €180–250/month (Hetzner GEX44; third-party figure) |
| 2. EU enterprise AI | Azure OpenAI EU Data Zone with abuse-monitoring logging off, or OpenAI EU residency with Zero Data Retention, or Mistral (EU) with ZDR, or AWS Bedrock Frankfurt | Column names and questions only; not stored, not used for training | Per-use; needs the provider's approval |
| 3. Today's demo | Organisers' gateway, gpt-5-mini | Column names and questions only | Budget: $0.009 of $10 spent |

**Facts you can cite in Q&A:**

- **OpenAI:** API data is not used for training. Abuse logs are kept up to 30 days unless the account has Zero Data Retention, which needs OpenAI's approval. EU data residency (`eu.api.openai.com`) exists since Feb 2025. [OpenAI: your data](https://developers.openai.com/api/docs/guides/your-data) · [EU residency](https://openai.com/index/introducing-data-residency-in-europe/)
- **Azure OpenAI:** prompts are not shared with OpenAI and not used for training. An EU Data Zone keeps processing in the EU, and abuse-monitoring logging can be switched off on approval. Albania's Diella (AKSHI) already runs on Azure OpenAI. [Microsoft data privacy](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy)
- **Mistral** (French company): EU hosting by default, ZDR on request, and open-weight models that can be self-hosted. [Mistral ZDR](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention)
- **AWS Bedrock:** does not store or log prompts, and does not share them with model providers. [AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html)
- **Albania, Law 124/2024** on personal data protection (GDPR-aligned, in force since 1 Feb 2025):
  - A public body needs a data protection officer (Art. 33).
  - Transfers abroad need adequate protection (Art. 39–41). EU/EEA states were listed as adequate under Decision 8/2016; check that it still applies.
  - Local or EU processing avoids the question.
  - [Law text (IDP)](https://idp.al/wp-content/uploads/2025/04/Law-no.124-2024-DP.pdf)
- **Open risk:** the organisers' gateway may log requests. That is one more reason the demo sends no values.

## 7. Feature gaps: what we say today, what we call a future plan

| Topic | Today (show or claim) | Future plan (say "next") |
|---|---|---|
| Board, gaps with owner, receipt, verified answers, Excel with source column, open-data CSV, read-only API | ✅ Built | — |
| Combining departments (e.g. fee vs waste cost) | ✅ Built (REV-02) | — |
| National SMP indicators | 5 indicators match SMP definitions; the draft map of all 52 is pending organiser approval | Compute every SMP indicator exports can support |
| Logins and roles per directorate | ❌ No login in the prototype, so it runs on synthetic data only | Logins, roles, audit log (pilot requirement) |
| Feed the city's AI window | The API exists | Agree a feed format with the window's team |
| Local / private AI | Headers-only mapping; rules mode needs no AI at all | Local open model on the municipal server |
| Real municipal data | Synthetic files only | Week 1 of the pilot, under a data agreement |
| Validated formulas | Marked "Draft" | Week 2, with the Performance Unit |
| Reminders to directorates that owe data | The board lists whom to ask | Automatic monthly reminders |

Corrected wording in `docs/pitch/sportel-vs-elbasani-gov-al.md`: the SMP row no longer says "maps all 52" as a finished fact. It now splits today from the future plan. New rows cover logins, the feed to the city's AI window, and where the AI runs.

## 8. Still to do before 11:00 Sunday

- [x] Team names on slide 8. Confirm the contact email and repo link.
- [ ] Confirm the wording of Elbasan's May 2026 recognition before saying it (slide 2 notes).
- [ ] Public figures on slides 2 and 6 (52 indicators, 38 Kosovo municipalities): keep them only if the organisers approved "request 3". Otherwise say "national performance indicators".
- [x] Video recorded (`demo/sportel-demo.mp4`). Insert it on slide 3: Insert → Video → This Device.
- [ ] Submit as `Firmat_Final.pptx` (or export to PDF), with the demo run instructions and the repo link.
