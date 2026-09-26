.PHONY: install dev api web test lint seed seed-all demo-reset eval samples

API_URL ?= http://localhost:8000
EVAL_MODE ?= auto

install:
	cd api && uv sync
	cd web && pnpm install

api:
	cd api && uv run uvicorn app.main:app --reload --port 8000

web:
	cd web && pnpm dev

dev:
	$(MAKE) -j2 api web

test:
	cd api && uv run pytest -q
	cd web && pnpm test

lint:
	cd api && uv run ruff check . && uv run ruff format --check .
	cd web && pnpm lint

# Reset the demo database offline (stop the API first: DuckDB allows one writer process).
# Loads the preload exports (requests, budget, population): 6 of 13 indicators computable.
seed:
	cd api && uv run python scripts/seed_demo.py

# Same, plus envelopes 1-3 (waste, revenue, staff): 13 of 13.
seed-all:
	cd api && uv run python scripts/seed_demo.py --all

# Reset a running API to the demo start state (6/13).
demo-reset:
	curl -fsS -X POST $(API_URL)/api/v1/demo/reset

# Golden-set evaluation (24 questions) -> api/eval_result.json. EVAL_MODE=rules ignores any key.
eval:
	cd api && uv run python scripts/run_eval.py --mode $(EVAL_MODE)

# Regenerate the synthetic department exports in api/samples/ (fixed seed).
samples:
	cd api && uv run python scripts/generate_samples.py
