# Overnight build plan and progress: gap-to-proof (26 Sep 2026)

Contract: `docs/superpowers/specs/2026-09-26-gap-to-proof-build.md`. Strategy: `docs/research/2026-09-26-track-d-wow-research.md`.
Branch: `feat/gap-to-proof` (from `codex/civic-interface`). Commit after every phase with the co-author trailer.

**Status:** IN PROGRESS · heartbeat: 2026-09-26 04:55 CEST

If you are a session resuming this work: read the contract, check which boxes below are ticked, verify with `git log` and the test commands in contract §9, then continue with the first unticked item. Tick boxes and update the heartbeat as you go. If the heartbeat is less than 45 minutes old, another session is still working: do not start parallel edits.

## Phase 1 — foundation (backend) + frontend build against fixtures
- [x] Backend foundation: `catalog.py`, `warehouse/schema.py` + single connection, LLM client (`complete_json`, `llm_call` persistence, spend restore), sample generator + `api/samples/*` + `manifest.json`, `core_kpi.yaml` passports + minimal registry, router stubs wired in `main.py`, health/CORS updates, tests
- [ ] Frontend: Sportel brand, design system extension, all screens of contract §8 against fixture JSON, i18n sq/en, web test script fixed

## Phase 2 — backend modules (parallel)
- [ ] Ingest pipeline + `/ingest/*`, `/samples`, `/sources`, `/demo/reset`, seed
- [ ] Indicators: registry/executor, signals, series, lineage, xlsx export, open-data CSV, `al_smp.yaml` coverage, population basis pin
- [ ] Copilot: sqlguard, sandbox, routing, gaps, examples, `/ask`, eval golden set + runner, `/llm/calls`

## Phase 3 — integration
- [ ] Frontend wired to the live API (fixtures only for REPLAY), end-to-end loop verified, all checks in contract §9 green
- [ ] Commit: "feat: gap-to-proof loop end to end"

## Phase 4 — review and fix
- [ ] Parallel reviews (backend correctness/security, frontend UX/a11y/i18n/design, demo flow vs strategy + honesty rules)
- [ ] Fixes applied, checks green, commit

## Phase 5 — docs and pitch
- [ ] README, Annex E update, demo script (`docs/pitch/demo-script.md`), CP2 checklist
- [ ] 8-slide deck draft (`docs/pitch/sportel-deck-v2.html`)
- [ ] Browser verification with screenshots (desktop + mobile, light + dark)
- [ ] Final commit; status set to DONE

## Log
- 02:40 Usage limit hit mid-run. Foundation complete (98 tests). Ingest, indicators, copilot and frontend were interrupted near completion (425 API tests pass, 1 failing; web typecheck and lint clean).
- 04:52 Resumed in the original session with a continuation workflow (finish backend + frontend → integrate → review/fix → docs).
