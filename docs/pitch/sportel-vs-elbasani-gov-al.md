# Sportel and elbasani.gov.al: what is different

## What Elbasan already has

On 24 September 2026, Bashkia Elbasan announced that it is the pilot municipality for using AI in transparency and accountability. A chat window on **elbasani.gov.al** lets **citizens** ask about the municipality's performance results and services and get an answer straight away. It is built by the company Smart Process under the "Bashki të Forta" (Strong Municipalities) project, run by Helvetas and funded by Switzerland and Sweden. It answers from the **published annual Performance Report**.

The website also publishes a lot of documents: budgets, the medium-term budget programme (PBA), budget monitoring reports, council decisions and local statistics. Almost all of them are PDFs, some are scanned images, and the "open data" page has no downloadable datasets.

## The key difference in one sentence

**The website chatbot answers citizens from a report that is already finished. Sportel works before that report exists: it takes the files departments already produce, computes the numbers, and proves where each one came from.**

Sportel is not a second chatbot. It is the back office that the chatbot, the Performance Report and leadership can rely on.

## Side by side

| | elbasani.gov.al chatbot | Sportel |
|---|---|---|
| **Who it serves** | Citizens | Leadership, department heads, planning and reporting staff |
| **Where answers come from** | The finished annual Performance Report (PDF) | Raw department exports (Excel/CSV), loaded and reconciled |
| **How often the data changes** | Once a year, when the report is published | Every time a department uploads its monthly export |
| **Where a number comes from** | Not traceable further back than the report | Each number links to its formula, the SQL, the source file and the exact rows |
| **When data is missing** | Can only answer what the report contains | Says "Pa përgjigje" (no answer), names the missing export and the directorate that owns it, and guesses no number |
| **Who produces the numbers** | People compile the report by hand; the AI reads it | Code computes every number; the AI only suggests which column is which |
| **Combining departments** | Not possible | Joins department exports, e.g. how much of the waste cost the cleaning fee covers (revenue + budget) |
| **Link to the national performance system (SMP)** | No | **Today:** a draft map of the 52 SMP indicators (pending organiser approval), and 5 Sportel indicators already match SMP definitions. **Future plan:** compute every SMP indicator that municipal exports can support |
| **Output** | Chat answers | Dashboard, reports, an Excel file with a source column, an open-data CSV and an API |
| **Who can see what** | Public | **Future plan:** logins and roles per directorate. The prototype has no login, so it runs only on synthetic data |
| **Feeding the city's AI window** | n/a | **Future plan:** the read-only indicator API exists today; agreeing the feed format with the window's team is a pilot step |
| **Where the AI runs** | Not published | **Today:** the AI sees column names and the question only, never values or rows. **Future plan:** a local open model on the municipal server, or an EU-region provider with zero data retention |

## The WOW factors

1. **From gap to proof, live.** The dashboard shows grey tiles for indicators that cannot be computed yet, each naming the missing file and who owns it. Ask about one and the assistant refuses honestly. Load the file and ask again, and the answer comes back **verified**, with its proof. The tile turns green and the counter goes up (e.g. from 6 to 8 of 13).

2. **A receipt for every file.** Real municipal Excel files are messy: title rows, merged cells, amounts in thousands of lekë, total rows. Sportel handles all of this and prints a receipt: rows read = rows loaded + rows excluded, with a reason for each, and a check that the money columns match the file's own total row, down to the lek.

3. **Privacy first.** Columns with names, phone numbers, emails or personal numbers are removed **before** anything reaches the AI. The AI never sees data rows, only column names and a few masked examples.

4. **An assistant that tells you how sure it is.** Every answer carries one of four labels, decided by code, not by the AI: **Verified**, **Exploratory**, **Blocked** (for example a request for personal data) or **Not answerable**. Its accuracy is shown on screen: 24 of 24 on our own set of 24 test questions.

5. **Every number shows its source.** Click any indicator to see its formula in plain Albanian, the SQL, the source files and row ranges, and the owning directorate. The formula is marked "draft — awaiting validation" until the municipality's Performance Unit approves it. The Excel export has a visible **"Burimi"** (source) column.

6. **Speaks the national reporting language.** Five Sportel indicators match official SMP indicators (#13 waste cost covered by the fee, #14 waste per resident, #15 cost per tonne, #23 staff turnover, #25 staff per 1,000 residents). The same approach works for Kosovo's equivalent system, so it scales to Gjakova and other municipalities.

7. **Built for decisions.** A leadership panel shows which directorate to ask for data this month, which indicators are off target, and neutral warnings such as "check the quantity or unit". It never says a number is wrong.

8. **Transparent about the AI itself.** A trust page lists what the AI does and what the code does, logs every AI call and what was sent, and shows spending against the budget. Without an AI key, the app still works in a clearly labelled "RREGULLA" (Rules) mode.

9. **Ready for the stage.** Albanian and English, light and dark themes, works on phones, and an offline "REPLAY" fallback that is always labelled.

## How to say it to the jury

- Start with credit: Elbasan is a national good-practice model for validating performance indicators, and it is already piloting AI for transparency.
- Then: "The chatbot answers citizens from the finished report. Sportel produces and proves the numbers underneath it, every month instead of once a year, and it could feed that chatbot verified numbers."
- Present the chatbot as a **partner**, never as a competitor, and never say the municipality's numbers or process are wrong.

## Honesty notes

- Today Sportel runs on **synthetic** department files, clearly labelled "SINTETIKE". The organisers' data package goes through the same pipeline.
- Directorate names in Sportel are placeholders until they are confirmed with the municipality.
- The chatbot description comes from the municipality's public announcement of 24 September 2026. We have not tested the chatbot itself.
