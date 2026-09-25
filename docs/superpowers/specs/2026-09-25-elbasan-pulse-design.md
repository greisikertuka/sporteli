# Elbasan Pulse — Design Spec

- **Event:** AI4Society Youth Innovation Hackathon, Tirana, 25–27 Sept 2026
- **Track:** D — Municipal Data Integration & Decision-Support Dashboard (Municipality of Elbasan)
- **Status:** Approved design, 2026-09-25

## 1. Problem

Municipal information in Elbasan is fragmented across multiple department systems. Leadership, department heads and planning/reporting staff cannot get a unified view of services, operations and citizen requests, which limits planning, performance monitoring and evidence-based decision-making.

## 2. Users

| User | Primary need |
|---|---|
| Municipal leadership (Mayor, cabinet) | One-glance health of the municipality; monthly briefing; ask questions without an analyst |
| Department heads | Their department's performance vs. targets; backlog and resolution trends |
| Planning & reporting staff | Integrate new department exports quickly; produce reports; export data via API |

## 3. Solution: integration-first AI decision copilot

Most dashboards assume data is already unified. Elbasan Pulse treats **integration as the product**: any department export can be onboarded in minutes with AI-assisted schema mapping, and decision support is layered on top.

### 3.1 Brief-to-feature traceability

| Track D brief | Feature |
|---|---|
| Data fragmented across multiple systems | **Smart Ingest** — AI-assisted mapping of CSV/XLSX exports into a canonical model |
| Unified dashboard | **Unified KPI dashboard** |
| Performance monitoring | **Department scorecards** vs. KPI targets |
| Reporting and analytics | **Monthly briefing** generator (sq/en) |
| Interactive visualizations, trend analysis | Interactive charts, map, trends, **Signals** (anomaly/trend alerts) |
| Decision-support tools | **Ask-the-data copilot** with visible SQL + source |
| APIs for future interoperability | **Open REST API** `/api/v1` with OpenAPI docs |

### 3.2 Innovation claims (for the pitch)

1. Onboarding a new department's data is a guided, minutes-long task, not an IT project.
2. Every AI answer is auditable: the generated SQL and source tables are shown.
3. Transferable: any municipality plugs in its own exports; the canonical model and mappings are reusable.

## 4. Architecture

```
[Dept exports: CSV/XLSX] ──► Smart Ingest (FastAPI)
                               │ Haiku proposes column→canonical mapping
                               │ human confirms → mapping saved per source
                               ▼
                 DuckDB warehouse (raw tables + canonical tables + lineage)
                               │
        ┌──────────────────────┼──────────────────────┐
   Metrics layer          Copilot (Sonnet)        Signals engine
   (SQL views)            NL→SQL, read-only,      (statistical, no LLM)
                          validated, cited
        └──────────────────────┼──────────────────────┘
                   REST API /api/v1 + OpenAPI
                               ▼
           Next.js dashboard (Albanian/English, role views)
```

### 4.1 Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `web/` (Next.js 16, TS, Tailwind, shadcn/ui, ECharts) | UI: dashboard, ingest wizard, copilot, briefing; i18n sq/en | API only |
| `api/app/ingest` | Parse CSV/XLSX, profile columns, request mapping proposal, apply confirmed mapping, write lineage | warehouse, llm |
| `api/app/warehouse` | DuckDB connection, canonical schema DDL, metric views | DuckDB |
| `api/app/copilot` | NL question → SQL (Sonnet) → SQL guard → execute → chart spec + answer | warehouse, llm, sqlguard |
| `api/app/sqlguard` | Parse SQL; allow only single read-only `SELECT` over allowlisted views; enforce `LIMIT` and timeout | sqlglot |
| `api/app/signals` | Z-score / rolling-baseline anomaly and trend detection on metric series | warehouse |
| `api/app/briefing` | Assemble KPIs + signals, then LLM-written narrative for leadership | metrics, signals, llm |
| `api/app/llm` | Single Claude client wrapper: model choice, token budget tracking, graceful failure | Anthropic SDK |

### 4.2 Canonical data model (initial; finalized after data package at 16:15 Friday)

- `department(id, name_sq, name_en)`
- `service_category(id, department_id, name_sq, name_en)`
- `request(id, source_id, category_id, department_id, location_id, created_at, closed_at, status, channel)`
- `location(id, name, lat, lon, zone)`
- `budget_line(id, department_id, period, planned, actual)`
- `kpi_target(id, department_id, metric, period, target)`
- `source(id, name, filename, uploaded_at, mapping_json)` — lineage for every row

Adjusting fields to the actual data package is expected; the architecture does not change.

### 4.3 Models

- Column mapping: `claude-haiku-4-5` (cheap, structured JSON output)
- Copilot SQL + briefing: `claude-sonnet-5`
- Budget: organiser cap of USD 25–50; `llm` wrapper logs token usage and fails gracefully.

## 5. Data flow

1. **Ingest:** upload file → profile (types, samples, null %) → Haiku gets column names + profile + a few *non-personal* sample values → returns mapping JSON → user edits/confirms → rows written to canonical tables with `source_id`.
2. **Dashboard:** web calls `/api/v1/metrics/*` → metric views.
3. **Copilot:** question → Sonnet gets schema of allowlisted views only → SQL → `sqlguard` → execute → results (aggregates) → Sonnet writes short answer + chart spec → UI shows answer, chart, SQL, sources.
4. **Briefing:** metrics + signals → Sonnet → markdown briefing (sq/en), exportable.

## 6. Privacy, safety and error handling

- Only organiser-provided/approved data is used (Rules §10.3). No real personal data.
- LLM never receives raw personal fields; ingest samples exclude columns flagged as PII by the profiler (names, phones, emails, ID numbers).
- Copilot SQL is read-only, single statement, allowlisted views, `LIMIT ≤ 1000`, 5 s timeout. Rejected SQL returns a clear message rather than a guess.
- If the LLM is unavailable/over budget: ingest falls back to manual mapping, the copilot shows "AI unavailable", and the dashboard, signals and API keep working.
- Mapping validation: required canonical fields must be mapped; type coercion errors are reported per column with row counts.

## 7. Testing

- `pytest`: sqlguard (allow/deny cases), mapping application and validation, metric queries on a fixture dataset, signals on synthetic series.
- Copilot golden set: ~20 questions with expected results; the accuracy number is reported honestly in the pitch.
- Playwright smoke test of the demo path: ingest → dashboard → ask question.
- CI: lint + tests on push (GitHub Actions).

## 8. Build tiers

| Tier | When | Contents |
|---|---|---|
| Scaffold (pre-event, disclosed in Annex E as non-core) | Fri before 13:00 | Monorepo, Docker Compose, empty Next.js shell with layout/i18n/theme, FastAPI skeleton with health endpoint and DuckDB connection, LLM client wrapper stub, CI. **No Track D logic.** |
| Must-have (CP2) | Sat 15:00 | Smart ingest, canonical model, KPI dashboard, copilot with visible SQL |
| Stretch (CP3) | Sat 21:00 | Signals, monthly briefing, map, OpenAPI polish, role views |
| Freeze | Sat 21:00 → Sun 11:00 | Polish, tests, deck (≤8 slides), Annex E, tagged release |

## 9. Deployment

- Local: `docker compose up` (localhost demo is an allowed fallback).
- Hosted: web on Vercel; API on Render or Hugging Face Spaces (Docker).

## 10. Compliance checklist

- Core built during the event; the pre-event scaffold is declared in Annex E.
- All AI tools used (including Claude Code) declared in Annex E and in the pitch.
- Submission by Sun 11:00: deck, demo link, tagged release, Annex E.

## 11. Out of scope

User accounts/SSO, write-back to source systems, real-time connectors to live municipal systems (named as next steps for the mentoring phase), mobile app.
