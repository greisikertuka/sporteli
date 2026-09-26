FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
# Container layout: /app/app (code), /app/samples (synthetic demo exports), /app/scripts (seed),
# /app/eval_result.json (last golden-set run, served by GET /api/v1/ask/eval), /data (DuckDB).
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DUCKDB_PATH=/data/pulse.duckdb \
    SAMPLES_DIR=/app/samples
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY samples ./samples
COPY scripts ./scripts
COPY eval_result.json ./eval_result.json
EXPOSE 8000
# Seed the demo (requests + budget + population, 6/13) only when the database is empty, so a
# restart keeps what was uploaded; POST /api/v1/demo/reset restores the start state.
# Hosts such as Render pass the port in $PORT; docker compose uses the 8000 default.
CMD ["sh", "-c", "python scripts/seed_demo.py --if-empty && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
