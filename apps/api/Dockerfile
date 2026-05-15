FROM python:3.13-slim AS base

RUN pip install uv

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-dev

FROM base AS dev
RUN uv sync
COPY . .
CMD ["uv", "run", "uvicorn", "digidentity_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
COPY src/ src/
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "digidentity_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
