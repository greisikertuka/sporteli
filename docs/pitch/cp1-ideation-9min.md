# CP1: Ideation (9 minutes, no slides)

**Team:** FirmatGroup · **Track D:** Municipal Data Integration & Decision-Support Dashboard

## Format check (read first)

| Source | When | Length |
|---|---|---|
| Event Agenda (newer) | Fri 15:45-17:00 | **9 minutes per team, no slides** |
| Participants' Guide (provisional times) | Fri 18:30 | 1 minute per team, no slides |

Prepare the 9-minute version below. If the organisers announce 1 minute, use [cp1-problem-lock.md](cp1-problem-lock.md).

**What mentors decide at CP1:** whether the scope is *buildable in 30 hours*. They cut oversized scopes on the spot.
So the talk must end with a small, concrete must-have list and an explicit "not doing" list.

## Talk plan

| Time | Section | Speaker | Judging criterion it serves |
|---|---|---|---|
| 0:00-1:00 | Problem, in Elbasan's own words | Domain / business | Municipal relevance (20%) |
| 1:00-2:00 | Users and one real task each | Product | User logic (15%) |
| 2:00-3:30 | Solution hypothesis: integration is the product | Product | Innovation (10%) |
| 3:30-5:00 | The core user journey, step by step | Technical | User logic, Feasibility (20%) |
| 5:00-6:15 | Where AI helps, and where it does not | Technical | Use of AI (15%) |
| 6:15-7:30 | Scope for 30 hours: must-have, stretch, not doing | Technical | Feasibility |
| 7:30-8:15 | Data, privacy, honesty | Data | Rules §10.3 |
| 8:15-9:00 | Scale and next steps | Business | Scalability (10%), Next steps (10%) |

## Script (about 1,150 words; roughly 130 words per minute)

> Fill the `[brackets]` after reading the data package README (handed out 14:50-15:45).

### 1. Problem (0:00-1:00)

"Mirëdita. We are FirmatGroup, and we chose Track D.

The Municipality of Elbasan told the organisers something very simple: its information sits in separate department systems, so nobody gets one view of services, operations and citizen requests. Planning and performance monitoring suffer because of it.

In practice that means a department head exports a spreadsheet, someone in the Mayor's office copies numbers into another spreadsheet, and by the time a report reaches leadership it is late, and no one can check where a number came from. In the data package we see this already: `[e.g. N files from N departments, each with different column names and formats]`."

### 2. Users (1:00-2:00)

"We design for three users, exactly the ones in the brief.

First, **leadership**: the Mayor's cabinet wants to know in one glance how the municipality is doing, and to ask a question without waiting for an analyst.

Second, **department heads**: they want their own performance against a target, and to see whether the backlog is growing.

Third, **planning and reporting staff**: they do the integration work today by hand. For them the task is: 'a new export arrived; get it into the shared picture'."

### 3. Solution hypothesis (2:00-3:30)

"Most dashboards assume the data is already clean and unified. In a municipality, that assumption is the problem.

So **Elbasan Pulse makes integration the product.** Any department export, CSV or Excel, is onboarded in minutes: the system profiles the columns, AI proposes how each one maps to one shared data model, and a person confirms it. The mapping is saved, so next month's export from the same department loads with one click.

Once the data is unified, everything else becomes cheap: KPIs, department scorecards, trends, a monthly briefing, and an open API for other systems.

Our hypothesis: *if onboarding a new data source takes minutes instead of an IT project, the municipality will actually keep one shared view up to date.*"

### 4. Core user journey (3:30-5:00)

"Here is the one flow we will have working end to end at Checkpoint 2.

One. A reporting clerk uploads `[a real file name from the package]`.

Two. Pulse shows each column with a sample value, and the AI suggestion: 'drejtoria' means department, 'data_krijimit' means created date. The clerk corrects anything wrong and confirms.

Three. The rows land in one database, and every row remembers which file it came from.

Four. The dashboard updates: requests received, resolved on time, overdue, by department and by month, against a target.

Five. The department head asks: 'Which department has the most overdue requests?' Pulse answers, and shows the SQL query and the source file behind the answer, so anyone can check it.

That is the demo: upload, confirm, see, ask, verify."

### 5. AI: value and limits (5:00-6:15)

"AI does two jobs where it saves real time.

First, **column mapping**. A small, cheap model suggests mappings. It only sees column names, types and a few non-personal sample values, never personal data. A person always confirms.

Second, **questions in Albanian or English**. A stronger model turns the question into SQL. That SQL is checked before it runs: read-only, one statement, only approved tables, limited rows. If the check fails, we say 'I can't answer that' instead of guessing.

What AI does *not* do: the KPIs and trend alerts are plain calculations and statistics. If the AI budget runs out or the connection fails, the dashboard, the alerts and the API keep working. We track spending against the team's API budget, `[USD 25-50]`."

### 6. Scope for 30 hours (6:15-7:30)

"We want to be precise about what we build this weekend.

**Must-have by Checkpoint 2, Saturday 15:00:** the upload-and-map flow, the shared data model built on the organisers' data package, the KPI dashboard with filters, and the question box that shows its SQL.

**Stretch by Checkpoint 3, Saturday 21:00:** automatic trend and anomaly alerts, the AI-written monthly briefing, and a map if the data has locations.

**Not doing:** user accounts and logins, live connections to municipal systems, writing back into their systems, and a mobile app. Those are next steps with the municipality.

The technical base is ready: a Python API with an embedded analytics database, and a web app in Albanian and English. So the 30 hours go into the integration logic, not setup."

### 7. Data, privacy, honesty (7:30-8:15)

"We use only the data the organisers gave us. Personal fields are detected and never sent to the AI. Questions can only read, never change data.

We also want to be transparent now, not on Sunday. Before the event we prepared a generic project skeleton and a visual mockup of the screens on clearly labelled fake numbers. That is declared in our Annex E. Everything that makes it work, the ingest, the data model, the metrics, the copilot, gets built here on the real package."

### 8. Scale and next steps (8:15-9:00)

"Why this scales: the shared model and the saved mappings are reusable. Gjakova, or any municipality, uploads its own exports and gets the same dashboard. The API lets other systems, for example a citizen-reporting app from Track A, send data in.

After the hackathon, in the four-week mentoring phase, we would test it with two Elbasan departments on their real monthly exports, measure onboarding time and data freshness, and prepare a pilot.

Faleminderit. We'd love your feedback on the scope."

## Scope card (for the mentors' "buildable in 30 hours" check)

| Tier | Deadline | Items | Owner |
|---|---|---|---|
| Must-have | CP2, Sat 15:00 | Upload CSV/XLSX → profile → AI mapping proposal → confirm → load into DuckDB with lineage | `[name]` |
| | | Canonical model adapted to the data package | `[name]` |
| | | Metrics API + dashboard switched from sample data to real data | `[name]` |
| | | Ask box: question → guarded SQL → answer + SQL + source | `[name]` |
| Stretch | CP3, Sat 21:00 | Signals (z-score / rolling baseline), AI briefing, map | `[name]` |
| Not doing | n/a | Accounts/SSO, live connectors, write-back, mobile app | n/a |

**Cut order if mentors say it is too big:** map → AI briefing (keep the template briefing) → signals → XLSX (CSV only).

## Why this answers the scorecard

| Criterion | Weight | Our evidence |
|---|---|---|
| Municipal relevance | 20% | Uses the brief's own words and users; built on Elbasan's data package |
| Feasibility | 20% | Small end-to-end flow; scaffold ready; LLM failures never break the app |
| Use of AI | 15% | AI where it saves hours (mapping, questions); a person confirms; SQL shown; limits stated |
| User logic | 15% | One flow per user: clerk uploads, head monitors, leadership asks |
| Innovation | 10% | Integration-first, auditable answers; not another static dashboard |
| Scalability | 10% | Reusable model and mappings; open API; works for any municipality |
| Next steps | 10% | 4-week mentoring plan: two departments, measure onboarding time, pilot |

Tie-breakers: municipal relevance first, then challenge-owner preference. So keep every sentence tied to Elbasan.

## Rules we must keep (from the Guide)

- **§10.2** The core must be built during the event. Pre-existing, non-core parts are allowed only if disclosed. Our UI mockup is pre-event: say so openly at CP1 and keep Annex E up to date.
- **§10.3** Use only organiser-provided or approved data. Replace the synthetic sample data with the data package as early as possible, and ask a mentor to confirm the placeholders are acceptable until then.
- **§10.5** Sunday 11:00: deck (max 8 slides, their template), demo link or localhost, **tagged release**, Annex E. If you submit late, you pitch last and lose the next-steps points.
- AI use must be declared in the submission *and* in the presentation.

## Questions to ask

**Mentors (during CP1 feedback):**
1. Is this must-have list right for 30 hours, or should we cut further?
2. Which data package files best represent "fragmented systems" for the demo?
3. Is it acceptable to show the pre-event UI mockup, as long as it is disclosed?

**Municipal Q&A desk (Sat 10:00-13:00) and the ICT presentation (Sat 09:30):**
1. Which systems do departments export from today (Excel, a custom system, paper)?
2. Which three numbers does leadership ask for most often?
3. How often do departments report: weekly or monthly? Who compiles it?
4. Are there official service targets (for example, days to resolve a request)?

## Likely mentor questions

| Question | Answer |
|---|---|
| "What if the AI maps a column wrong?" | A person confirms every mapping; required fields are validated; wrong types are reported per column with row counts. |
| "What if it generates bad SQL?" | The SQL guard allows only read-only, single, allowlisted queries with a row limit and timeout; otherwise it answers "can't answer". The SQL is always shown. |
| "How is this different from Power BI?" | Power BI assumes clean, modelled data and an analyst. Pulse does the integration step with AI and lets non-analysts ask questions with verifiable answers, in Albanian. |
| "What did you build before the event?" | A generic scaffold and a UI mockup on fake data, declared in Annex E. No Track D logic. |
| "What does it cost to run?" | Open-source stack; one small server; AI cost is a few cents per mapping or question, with a hard budget cap. |
| "What happens after the hackathon?" | Four-week mentoring: two departments, real monthly exports, measure onboarding time and freshness, then a pilot. |
