# Overnight build plan and progress: gap-to-proof (26 Sep 2026)

Contract: `docs/superpowers/specs/2026-09-26-gap-to-proof-build.md`. Strategy: `docs/research/2026-09-26-track-d-wow-research.md`.
Branch: `feat/gap-to-proof` (from `codex/civic-interface`). Commit after every phase with the co-author trailer.

**Status:** DONE · 2026-09-26 07:48 CEST

If you are a session resuming this work: read the contract, check which boxes below are ticked, verify with `git log` and the test commands in contract §9, then continue with the first unticked item. Tick boxes and update the heartbeat as you go. If the heartbeat is less than 45 minutes old, another session is still working: do not start parallel edits.

## Phase 1 — foundation (backend) + frontend build against fixtures
- [x] Backend foundation: `catalog.py`, `warehouse/schema.py` + single connection, LLM client (`complete_json`, `llm_call` persistence, spend restore), sample generator + `api/samples/*` + `manifest.json`, `core_kpi.yaml` passports + minimal registry, router stubs wired in `main.py`, health/CORS updates, tests
- [x] Frontend: Sportel brand, design system extension, all screens of contract §8 against fixture JSON, i18n sq/en, web test script fixed

## Phase 2 — backend modules (parallel)
- [x] Ingest pipeline + `/ingest/*`, `/samples`, `/sources`, `/demo/reset`, seed
- [x] Indicators: registry/executor, signals, series, lineage, xlsx export, open-data CSV, `al_smp.yaml` coverage, population basis pin
- [x] Copilot: sqlguard, sandbox, routing, gaps, examples, `/ask`, eval golden set + runner, `/llm/calls`

## Phase 3 — integration
- [x] Frontend wired to the live API (fixtures only for REPLAY), end-to-end loop verified, all checks in contract §9 green
- [x] Commit: "feat: gap-to-proof loop end to end"

## Phase 4 — review and fix
- [x] Parallel reviews (backend correctness/security, frontend UX/a11y/i18n/design, demo flow vs strategy + honesty rules)
- [x] Fixes applied, checks green, commit

## Phase 5 — docs and pitch
- [x] README, Annex E update, demo script (`docs/pitch/demo-script.md`), CP2 checklist
- [x] 8-slide deck draft (`docs/pitch/sportel-deck-v2.html`)
- [x] Browser verification with screenshots (desktop + mobile, light + dark)
- [x] Final commit; status set to DONE

## Log
- 02:40 Usage limit hit mid-run. Foundation complete (98 tests). Ingest, indicators, copilot and frontend were interrupted near completion (425 API tests pass, 1 failing; web typecheck and lint clean).
- 04:52 Resumed in the original session with a continuation workflow (finish backend + frontend → integrate → review/fix → docs).
- 2026-09-26 05:49: commit "feat: complete Sportel backend endpoints and frontend screens (gap-to-proof)"; golden test, ruff, error shape, ambiguity margin, Docker/seed/Makefile; frontend REPLAY recording, screen polish, i18n parity, 20 web tests.
- 2026-09-26 06:19 — Phase 3 commit: loop verified end to end against the live API (check-live 21 shapes/0 issues, 432 pytest, 20/20 web tests, build ok); YTD periods, ask-again link, REPLAY snapshots re-recorded incl. after-zarfi-2 state.
- 2026-09-26 07:20 — Phase 4 commit "fix: review findings (security, UX, demo flow, honesty)": supersede keys, reconciliation tolerance, atomic demo reset, JSON 500 handler, sandbox size caps, PII masking, ask scroll/focus, series_kind labels, REPLAY visibility, plus minor fixes; REPLAY snapshot re-recorded; new tests.
- 2026-09-26 07:39 — Phase 5 docs commit: README, Annex E update, demo script, CP2 checklist, 8-slide deck draft (docker compose untested; envelopes 1/3 and REPLAY not browser-walked; team placeholders remain)
- 2026-09-26 08:10 Browser verification in the preview pane against the live API (port 8000, rules mode): Board 6/13 with gap tiles naming export + owner; Ask → "Pa përgjigje" for REV-02 with gap card; "Ngarko eksportin" → Integro with the envelope preselected; zarfi-2 step log, mapping confirm, load receipt (100 = 96 + 4, both totals reconciled, "E BARAZUAR"), header 8/13; "Pyet sërish" → "E verifikuar" 55,0% with SQL and two source files; Board REV-01/REV-02 with proof; passport drawer; SMP coverage (pending-approval banner); report; trust page; dark mode; 375px without horizontal scroll; English toggle. Final checks: API 457 passed / 1 skipped, ruff clean; web lint, tsc, 25/25 tests green. Demo left at the start state (6/13), Albanian, light theme.

## Summary
Built overnight on `feat/gap-to-proof`: synthetic department exports, ingest with load receipts and PII gate, 13 indicator passports (5 mapped to SMP 2024 Annex A), signals, xlsx/CSV export with provenance, SMP coverage map, honest copilot with four code-decided labels and a 24/24 rules-mode eval, redesigned bilingual frontend with REPLAY fallback, README, Annex E, demo script, CP2 checklist and an 8-slide deck draft. Open items for the team: organisers' data package, API key, rule 10.3 approvals, event repo remote + push + tag, hosting, desk quote and real owner names, demo video, mapping the deck onto the organisers' template.
