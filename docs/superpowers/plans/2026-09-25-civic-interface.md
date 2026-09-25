# Civic Interface Implementation Plan

> Execute inline with superpowers:executing-plans; the user explicitly approved implementation of the reviewed direction.

**Goal:** Replace the empty municipal app shell with the approved usable, responsive Civic workspace.
**Architecture:** Keep Next.js route boundaries and next-intl. Small client feature components consume shared synthetic aggregates and CSV utilities. Existing Radix primitives supply accessible overlays. Preserve the health API integration.
**Tech stack:** Next.js 16, React 19, TypeScript, Tailwind 4, next-intl, Radix, Lucide.
**Spec:** ../specs/2026-09-25-civic-interface.md

## Global constraints

- Sample data and local previews remain explicitly labeled; no unsupported backend claims.
- Albanian/English parity, light/dark appearance, keyboard accessibility, reduced motion.
- No new product dependencies; use Node's native test runner.
- The requested work remains reviewable on codex/civic-interface in the existing checkout.

## Review focus

CSV quoting/empty/large input; filtered calculations and zero denominators; translation/theme parity; mobile overflow and sheet focus; sample-state honesty and downloaded content.

## Tasks

- [x] 1. Add failing aggregate and CSV tests, implement shared data and validation, verify with `node --test tests/*.test.mjs`.
- [x] 2. Implement palette, typography, civic mark, navigation, responsive shell, and localized labels.
- [x] 3. Implement overview filters, chart, department details, and source lineage.
- [x] 4. Implement local import preview, supported sample questions, and monthly report export/print.
- [x] 5. Run unit tests, API suite, lint, production build, and browser checks; request a fresh code review and address material findings.

## Execution notes

The user's “ok do it” authorizes execution of the already reviewed visual direction. Work stays in the current checkout on a feature branch so the existing development server and the user's project show the result. The backend has only a health endpoint; this pass delivers an honest interactive frontend demonstration, not new ingestion or LLM services.

## Verification and review

- `make test`: 7 API tests and 9 frontend tests pass. The root target now runs both suites.
- `make lint`: Ruff checks/format and ESLint pass.
- `pnpm build`: production compilation, TypeScript, and all routes pass, including the report download.
- HTTP checks verified localized English/Albanian Markdown report content and attachment headers.
- Browser checks covered both locales, light/dark themes, 320/390/650/1280 px layouts, filters, chart data, details sheets, Escape/focus restoration, CSV sample mapping errors and completion, sample answers, and unsupported questions.
- No browser errors or warnings in the final reload. Fixed server/browser Albanian formatting differences with deterministic formatting.
- Independent code review completed; addressed file-read supersession, overlay focus restoration, historical aggregate rounding, malformed empty CSV rows, long filenames, print colors, and sample-state clarity.
- Small-screen checks caught and fixed the source diagram and long Albanian header overflow. Report source details remain accessible on mobile.
- Print styling is implemented; the operating-system print dialog was not exercised. Download response was verified over HTTP; an OS file-save confirmation is not claimed.
