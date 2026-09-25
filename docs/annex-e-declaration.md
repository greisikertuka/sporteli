# Annex E: Declaration of AI Tools & Pre-Existing Components (draft)

**Team name:** FirmatGroup
**Challenge track:** D — Municipal Data Integration & Decision-Support Dashboard

## AI tools used

| Tool | Used for |
|---|---|
| Claude Code (Anthropic) | Code assistant: design discussion, scaffolding, implementation and tests |
| ChatGPT (OpenAI) | Visual/UI design of the civic interface (palette, layout, motion) and front-end code for the pre-event prototype |
| Claude API: `claude-haiku-4-5` | In-product: proposes column mappings during data ingest |
| Claude API: `claude-sonnet-5` | In-product: natural-language questions to SQL, and briefing narratives |

## Open-source libraries/frameworks used

FastAPI, Uvicorn, DuckDB, Pydantic, Anthropic Python SDK, pytest, Ruff; Next.js, React, Tailwind CSS,
shadcn/ui (Radix UI), next-intl, next-themes, Apache ECharts, lucide-react; Source Sans 3 (Google Fonts).

## Pre-existing code or components brought into the hackathon

Everything below was prepared on 25 Sept 2026 **before the event started at 13:00**. The git history
proves it: the last pre-event commit is `a0e1a10`, dated 2026-09-25 13:01 CEST, made at registration.

**1. Generic, non-core project scaffold (Claude Code)**

- Monorepo layout, Makefile, Docker Compose, CI workflow
- FastAPI app with a `/health` endpoint, DuckDB connection helper and a generic Claude client wrapper
  (spend tracking, graceful failure)
- Next.js app shell: sidebar navigation, Albanian/English switching, light/dark theme, API status badge

**2. Front-end UI prototype, "civic interface" (designed with ChatGPT)**

- Visual identity: Elbasan-inspired blue/yellow palette, logo mark, light/dark themes, motion
- Clickable screens for Overview, Sources, Ask the data and Monthly briefing
- Driven only by **synthetic, clearly labelled sample data** (`web/src/lib/pulse-data.ts`). It
  contains no municipal records and no personal data, and no data was sent to any service.
- A browser-only CSV preview, and canned sample answers for the copilot screen. There is no real
  ingest, no warehouse, no AI and no API integration.

**Built during the hackathon:** the shared data model based on the organisers' data package; real
ingest with AI-assisted mapping into DuckDB; the KPI and metrics API, which replaces the synthetic
data; the copilot (natural-language questions to guarded SQL); signals; and the AI-generated briefing.
All numbers shown in the final demo come from the organisers' data.
