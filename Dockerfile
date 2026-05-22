FROM python:3.14-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY folio/ folio/
COPY rxconfig.py .

EXPOSE 3000 8000

CMD ["uv", "run", "reflex", "run", "--env", "prod"]
