# Elbasan Pulse

**One place for Elbasan's municipal data.** Any department export is onboarded in minutes with
AI-assisted mapping, then turned into KPIs, trends and answers that leadership can trust.

Built by **FirmatGroup** at the AI4Society Youth Innovation Hackathon (Tirana, 25–27 Sept 2026),
**Track D: Municipal Data Integration & Decision-Support Dashboard**, for the Municipality of Elbasan.

## Current demo

The responsive frontend includes a filterable overview, source details, a local CSV preview
with column mapping, supported sample questions, and a printable/downloadable monthly report.
It supports Albanian and English, light and dark themes, keyboard navigation, and reduced motion.
The civic mark, chart transitions, and source-flow animation are built with SVG and CSS.

All dashboard figures are clearly labeled synthetic data. CSV previews stay in the browser and
do not save records. Sample answers use deterministic calculations; their displayed SQL is
illustrative. Live ingestion, warehouse queries, and AI answers are not connected yet. The API
currently provides the health endpoint.

To explore the UI alone: `cd web && pnpm install && pnpm dev`, then open
[localhost:3000](http://localhost:3000). The API status correctly shows offline when it is not running.

## Product roadmap

| Brief | Feature |
|---|---|
| Data fragmented across systems | Smart Ingest: AI-assisted mapping of CSV/XLSX exports into one shared model |
| Unified dashboard, performance monitoring | KPI dashboard and department scorecards |
| Decision-support tools | Ask-the-data copilot, which shows the SQL and source behind every answer |
| Trend analysis | Signals: statistical anomaly and trend alerts |
| Reporting | Monthly leadership briefing (Albanian/English) |
| APIs for interoperability | Open REST API at `/api/v1`, OpenAPI docs at `/docs` |

## Architecture

```
Dept exports (CSV/XLSX) → Smart Ingest (FastAPI + Claude Haiku) → DuckDB warehouse
      → metrics · copilot (Claude Sonnet, read-only guarded SQL) · signals
      → REST API /api/v1 → Next.js dashboard (sq/en)
```

- `api/`: Python 3.12, FastAPI, DuckDB, Anthropic SDK
- `web/`: Next.js 16, TypeScript, Tailwind, shadcn/ui, next-intl, ECharts

If AI is unavailable or over budget, the dashboard, signals and API keep working. Only the copilot
and the briefing depend on the LLM.

## Run locally

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY
cp .env.example api/.env
make install
make dev                    # api :8000, web :3000
```

Or run everything with Docker: `docker compose up --build`.

Tests and lint: `make test`, `make lint`.

## Privacy

We only use data provided by the organisers. Personal fields are never sent to the LLM, and copilot
queries are read-only, allowlisted and row-limited.

## AI & pre-existing components disclosure

See [docs/annex-e-declaration.md](docs/annex-e-declaration.md).
