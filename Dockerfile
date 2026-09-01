FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS base

WORKDIR /app

COPY pyproject.toml uv.lock ./

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=/app/uv.lock \
    --mount=type=bind,source=pyproject.toml,target=/app/pyproject.toml \
    uv sync --frozen --no-dev

COPY src /app/src

FROM python:3.12.14-slim-bookworm AS final

ARG VERSION=1.0.0
ENV APP_VERSION=$VERSION \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 10001 falco \
    && useradd --system --uid 10001 --gid falco --no-create-home --home-dir /nonexistent falco

WORKDIR /app
COPY --from=base --chown=falco:falco /app /app
ENV PATH="/app/.venv/bin:$PATH"

USER falco
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
