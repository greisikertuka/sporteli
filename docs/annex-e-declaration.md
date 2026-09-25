# Annex E: Declaration of AI Tools & Pre-Existing Components (draft)

**Team name:**
**Challenge track:** D — Municipal Data Integration & Decision-Support Dashboard

## AI tools used

| Tool | Used for |
|---|---|
| Claude Code (Anthropic) | Code assistant: design discussion, scaffolding, implementation and tests |
| Claude API: `claude-haiku-4-5` | In-product: proposes column mappings during data ingest |
| Claude API: `claude-sonnet-5` | In-product: natural-language questions to SQL, and briefing narratives |

## Open-source libraries/frameworks used

FastAPI, Uvicorn, DuckDB, Pydantic, Anthropic Python SDK, pytest, Ruff; Next.js, React, Tailwind CSS,
shadcn/ui (Radix UI), next-intl, next-themes, Apache ECharts, lucide-react.

## Pre-existing code or components brought into the hackathon

A generic, **non-core** project scaffold prepared on the morning of 25 Sept 2026, before the event
started. It contains no Track D functionality:

- Monorepo layout, Makefile, Docker Compose, CI workflow
- FastAPI app with a `/health` endpoint, DuckDB connection helper and a generic Claude client wrapper
  (spend tracking, graceful failure)
- Next.js app shell: sidebar navigation, Albanian/English switching, light/dark theme, API status
  badge, empty placeholder pages

These features were all built during the hackathon: data ingest and mapping, the shared data model,
KPIs, the copilot, signals and the briefing. The git history timestamps show this.
