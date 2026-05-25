FROM python:3.14-slim

# Build deps for psycopg2 + reflex's node runtime; cleaned in the same layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates nodejs npm unzip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

RUN npm install -g opencode-ai@1.15.8 \
    && npm cache clean --force

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY folio/ folio/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY rxconfig.py ./

EXPOSE 3000

CMD ["uv", "run", "reflex", "run", "--env", "prod", "--backend-host", "0.0.0.0"]
