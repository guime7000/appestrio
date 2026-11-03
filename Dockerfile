FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build


FROM python:3.14-slim AS backend-build

ENV PYTHONUNBUFFERED=1

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --package app

COPY ./backend/scripts /app/scripts

COPY ./backend/pyproject.toml ./backend/alembic.ini /app/

COPY ./backend/app /app/app

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --package app

# `lgpio` -- the gpiozero backend app/services/relay.py actually drives
# the GPIO relay through -- has no prebuilt wheel for any platform (it's
# a thin SWIG-generated C wrapper around the C library `liblgpio`), so
# it can't go through the normal `uv sync`/uv.lock path without making
# `swig` a hard requirement for every dev machine and CI run that just
# wants to run the test suite (none of which ever construct a real GPIO
# device -- relay.py's tests mock `_make_device`). Installed here
# instead, straight into the already-synced venv, isolated to this one
# build stage where the build tools below are cheap to add and thrown
# away immediately after.
#
# The C library itself (`liblgpio.so`) isn't packaged by Debian at all
# (confirmed: no `liblgpio-dev` in any Debian suite) -- building the
# Python `lgpio` package without it first fails to link
# ("cannot find -llgpio"), the exact error that showed this gap. Built
# from upstream source (joan2937/lg, pinned to v0.2.2 -- the version
# the `lgpio` Python package itself is versioned against) and installed
# to /usr/local/{lib,include} + `ldconfig`, same as its own Makefile
# would do on a real Pi.
RUN apt-get update && apt-get install -y --no-install-recommends \
    swig gcc make python3-dev wget ca-certificates \
    && wget -q https://github.com/joan2937/lg/archive/refs/tags/v0.2.2.tar.gz -O /tmp/lg.tar.gz \
    && tar -xzf /tmp/lg.tar.gz -C /tmp \
    && make -C /tmp/lg-0.2.2 lib \
    && make -C /tmp/lg-0.2.2 install \
    && rm -rf /tmp/lg* \
    && rm -rf /var/lib/apt/lists/* \
    && uv pip install --python /app/.venv/bin/python lgpio


FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

# mpv for the Audio page's playback (app/services/audio_player.py) --
# installed on every device's backend image (same image runs on master
# and every lumestrio) even though only `handles_audio` devices ever
# use it; no sound hardware needed to install the binary itself, only
# to actually produce sound at runtime (see compose.yml's /dev/snd
# comment).
RUN apt-get update && apt-get install -y --no-install-recommends mpv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Runtime only needs the synced venv and app code, not uv itself or the
# build cache, so this stage stays lean.
COPY --from=backend-build /app/.venv /app/.venv
COPY --from=backend-build /app/scripts /app/scripts
COPY --from=backend-build /app/pyproject.toml /app/alembic.ini /app/
COPY --from=backend-build /app/app /app/app

# `liblgpio.so` (see the build stage's own comment) is a shared library
# the Python `lgpio` extension dlopen()s at import time, not just link
# time -- without it here too, `relay.py` would silently fall back to
# "no GPIO backend available" on every real device, not just dev
# machines/CI. `ldconfig` refreshes this stage's own linker cache
# (COPY doesn't trigger it automatically).
COPY --from=backend-build /usr/local/lib/liblgpio.so* /usr/local/lib/
RUN ldconfig

COPY --from=frontend-build /frontend/dist /app/static

# Single worker: init_db() runs Alembic migrations in the FastAPI lifespan,
# and multiple workers each running migrations concurrently against the same
# SQLite file races and can crash on startup.
CMD ["fastapi", "run", "--workers", "1"]
