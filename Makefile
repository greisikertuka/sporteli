.PHONY: install dev api web test lint

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
