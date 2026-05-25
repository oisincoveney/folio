# syntax=docker/dockerfile:1.7
#
# Four stages:
#
#   syscommon  - Debian-slim + apt deps + uv + opencode-ai. Built once;
#                inherited by both `base` and `runtime` so the same APT and
#                npm installs aren't repeated.
#   base       - adds the Python venv (uv sync --frozen) and the source.
#                Tilt builds `--target base` and runs `reflex run --env prod`
#                via the default CMD; live_update syncs folio/ into /app.
#   builder    - extends base; prebuilds the Next.js frontend with
#                REFLEX_API_URL baked into web/env.json. Production builds
#                must pass --build-arg REFLEX_API_URL=https://folio.momokaya.ee.
#   runtime    - final prod image. Inherits the system layer; copies the
#                venv + source from `base` and the prebuilt frontend from
#                `builder`. Runs as a non-root user, calls granian directly
#                (no `uv run` wrapper), and skips `reflex run` entirely so
#                cold start = just import + bind port.

# --- syscommon --------------------------------------------------------------
FROM python:3.14-slim AS syscommon

# Build deps for psycopg2 + reflex's node runtime; cleaned in the same layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates nodejs npm unzip \
    && rm -rf /var/lib/apt/lists/*

# uv binary from the official distroless image; avoids the `pip install uv`
# layer and keeps the version pinned.
COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /usr/local/bin/

# opencode-ai is invoked as a subprocess by folio.services.parser at runtime.
# Installed here once; both base (Tilt local) and runtime inherit it.
RUN npm install -g opencode-ai@1.15.8 \
    && npm cache clean --force

COPY docker-entrypoint.sh /usr/local/bin/folio-entrypoint
RUN chmod 0755 /usr/local/bin/folio-entrypoint

# uv tunables: copy mode (cross-FS in BuildKit layers) + bytecode-compile so
# imports at runtime are cold-cache-friendly.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

ENTRYPOINT ["folio-entrypoint"]

# --- base (Tilt target) -----------------------------------------------------
FROM syscommon AS base

# Install Python deps first so source changes don't invalidate this layer.
# `--frozen` enforces the lockfile (deterministic builds); `--no-dev`
# excludes pyright/ruff/pytest etc.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY folio/ folio/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY rxconfig.py ./

# Re-run sync to install the project itself now that the source is in place.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 3000

# Local Tilt CMD. `reflex run --env prod` runs setup_frontend_prod at
# startup; slow on the first cold start, fine for iterative dev via
# live_update.
CMD ["reflex", "run", "--env", "prod", "--backend-host", "0.0.0.0"]

# --- builder (prebuilds frontend) -------------------------------------------
FROM base AS builder

# The frontend's api_url is read from REFLEX_API_URL at build time and baked
# into web/env.json by `reflex export`. Production builds must pass the public
# URL explicitly; docker-compose supplies the localhost value for local images.
ARG REFLEX_API_URL
RUN test -n "$REFLEX_API_URL" || ( \
        echo "ERROR: REFLEX_API_URL build arg is required for the runtime image. Example: docker build --target runtime --build-arg REFLEX_API_URL=https://folio.momokaya.ee ." >&2; \
        exit 1 \
    )
ENV REFLEX_API_URL=${REFLEX_API_URL}

RUN --mount=type=cache,target=/root/.npm \
    reflex init && reflex export --frontend-only --no-zip

# --- runtime (final prod image) ---------------------------------------------
FROM syscommon AS runtime

# Drop privileges. The app reads/writes /app/.web/_states at runtime (Reflex
# on-disk state manager) so /app must be writable by `folio`.
RUN useradd --create-home --uid 1000 --shell /bin/sh folio \
    && chown folio:folio /app

COPY --from=base --chown=folio:folio /app/.venv /app/.venv
COPY --from=base --chown=folio:folio /app/folio /app/folio
COPY --from=base --chown=folio:folio /app/alembic /app/alembic
COPY --from=base --chown=folio:folio /app/alembic.ini /app/rxconfig.py ./
COPY --from=base --chown=folio:folio /app/pyproject.toml /app/uv.lock ./

# Only the artifacts the runtime needs:
#   .web/build/     compiled static frontend (served by the ASGI app)
#   .web/backend/   stateful_pages.json marker that lets compile_app take its
#                   skip-compile early-return path instead of trying to npm
#                   install at startup
# Not carried: .web/node_modules (~hundreds of MB), .web/{app,components,
# styles,...} (Next.js source is already baked into build/).
COPY --from=builder --chown=folio:folio /app/.web/build   /app/.web/build
COPY --from=builder --chown=folio:folio /app/.web/backend /app/.web/backend

# `internal=True` EnvVar entries in reflex_base/environment.py prepend `__`
# to the real env-var name (see env_var factory at line ~495). Both flags
# below are internal, so the OS env var names are `__REFLEX_*` even though
# the Python attribute names are `REFLEX_*`. Setting `REFLEX_*` directly
# leaves the EnvVar bound to its False default and the app re-runs compile
# (npm install) on every cold start.
ENV __REFLEX_MOUNT_FRONTEND_COMPILED_APP=true \
    __REFLEX_SKIP_COMPILE=true \
    PATH="/app/.venv/bin:${PATH}"

USER folio

EXPOSE 3000

# Skip `reflex run --env prod` (would re-run `next build` and undo the
# prebake). granian invokes the rx.App ASGI factory directly, the same server
# Reflex uses internally in prod (reflex/utils/exec.py:run_granian_backend_prod;
# Reflex ships granian as the prod default).
CMD ["granian", \
     "--interface", "asgi", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "3000", \
     "folio.folio:app"]
