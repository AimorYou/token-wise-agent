FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

# Install dependencies (cached layer — only rebuilt when lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy agent code (configs are bundled inside agent/)
COPY run.py ./
COPY agent/ ./agent/

# Task code is mounted at runtime: -v /host/task:/testbed
# API keys are passed via --env-file .env or -e flags

ENTRYPOINT ["uv", "run", "python", "/app/run.py"]
