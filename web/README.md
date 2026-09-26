# Sportel · web

Next.js 16 (App Router, React 19, Tailwind 4, next-intl) front end for Sportel — "Raporto një
herë, provo çdo numër". Albanian by default, English toggle. The screens and JSON contracts are
defined in `docs/superpowers/specs/2026-09-26-gap-to-proof-build.md` (§7 API, §8 screens).

| Route | Screen |
|---|---|
| `/` | Paneli — proof counter, tiles by area, passport drawer, trend, signals, .xlsx export |
| `/ingest` | Integro — dropzone, sample envelopes, step log, mapping, PII gate, Load Receipt, sources |
| `/ask` | Pyet të dhënat — four labels, interpreted-as, SQL, sources, gap card, eval chips |
| `/indicators/[code]` | Full passport page (shareable) |
| `/coverage` | Mbulimi SMP — the 52 Annex A indicators, draft mapping pending approval |
| `/briefing` | Raporti — printable report; every number is a chip that shows its source |
| `/trust` | Besueshmëria — AI vs code, LLM call log, spend, eval, limits |

## Run

```bash
pnpm install
pnpm dev                      # http://localhost:3000, API at NEXT_PUBLIC_API_URL (default http://localhost:8000)
pnpm lint && pnpm test && pnpm build
```

## REPLAY (offline)

If the API cannot be reached, every call is answered by the REPLAY engine in
`src/lib/fixtures/` and the header shows a **REPLAY** badge. `NEXT_PUBLIC_USE_FIXTURES=1` forces it.

REPLAY computes nothing: `src/lib/fixtures/snapshot.ts` holds real API responses over the
synthetic sample exports — passports, lineage, previews, receipts, answers and the SMP
coverage in the start state, after envelope 2 alone (8/13), the full state and with the
civil-registry basis — recorded by `scripts/record-replay.mjs`. The engine only tracks which
exports are loaded and picks the matching response, so offline and live show the same
numbers; a test proves that REPLAY's composed after-envelope-2 state equals the recorded one.
Re-record after changing passports, samples or the ingest pipeline:

```bash
make api                                   # or any running API
pnpm --dir web record-replay               # default http://localhost:8000; pass another URL as an argument
pnpm --dir web test
```

## Live integration check

`scripts/check-live.mjs` walks the whole gap-to-proof loop against a running API exactly as the
screens call it (sample preview and multipart upload, commit, receipt, ask, board, envelopes,
xlsx `Burimi` column, coverage, basis pin, format drift, error bodies) and validates every
JSON response recursively against the types in `src/lib/api.ts`. With a web URL it also
fetches each page. It resets the API's demo database, so use a scratch API:

```bash
pnpm --dir web check-live http://localhost:8100 http://localhost:3100
```

## Conventions

- Every UI string lives in `messages/sq.json` and `messages/en.json` (identical key sets).
- Numbers are formatted by `src/lib/format.ts` (Albanian `1.248,5`, English `1,248.5`).
- Design tokens: `src/app/globals.css` (base, light/dark), `sportel.css` (shell, board,
  passport), `sportel-screens.css` (ingest, ask, coverage, briefing, trust, responsive, print).
