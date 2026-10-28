FROM python:3.14-slim AS build

ENV PYTHONUNBUFFERED=1

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Install dependencies first (cached separately from app code, same
# pattern as ../Dockerfile) -- this package has zero runtime
# dependencies today, but keeps the layering correct if that changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

COPY pyproject.toml uv.lock ./
COPY lora_daemon ./lora_daemon

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

# `hwclock` (clock.py's receive side of SYNC, item 8's last gap --
# writes the system clock through to the physical RTC module) isn't in
# this base image's util-linux package on this Debian release -- it's
# split out into util-linux-extra. `date` (also used by clock.py) is
# already present via coreutils, not installed explicitly here.
RUN apt-get update && apt-get install -y --no-install-recommends util-linux-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/

ENV PATH="/app/.venv/bin:$PATH"

COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/lora_daemon /app/lora_daemon
COPY --from=build /app/pyproject.toml /app/

CMD ["python", "-m", "lora_daemon"]
