# Combined image: API + compiled dashboard + migrations (run at start).
# Single-container alternative to the separate api and dashboard images.
# Build from the repository root: docker build -f aio/Dockerfile -t honeywatch-aio .

FROM node:26-alpine@sha256:ef24c5053d50fdc3e4e56eb4e7ddb7861874ab0fdc797046ba897581deb8e868 AS dashboard

# Node 25+ alpine no longer ships corepack.
RUN npm install -g pnpm@10.33.0

WORKDIR /app

COPY dashboard/package.json dashboard/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY dashboard/ .
RUN pnpm build

FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

COPY --from=ghcr.io/astral-sh/uv:0.11.12@sha256:3a59a3cdd5f7c217faa36e32dbc7fddbb0412889c2a0a5229f6d790e5a019dd7 /uv /uvx /bin/

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

RUN groupadd -r honeywatch && useradd -r -g honeywatch -d /home/honeywatch -m honeywatch

WORKDIR /app

COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY api/ .
RUN uv sync --frozen --no-dev

# Keeping Rust uv deps out of scans
RUN rm -f /bin/uv /bin/uvx && rm -rf /root/.cache/uv

# The venv is prebuilt and nothing installs at runtime.
# Images bundled stuff contribute to CVE scan.
RUN rm -rf /usr/local/lib/python3.*/site-packages/pip \
    /usr/local/lib/python3.*/site-packages/pip-* \
    /usr/local/lib/python3.*/site-packages/setuptools \
    /usr/local/lib/python3.*/site-packages/setuptools-* \
    /usr/local/lib/python3.*/site-packages/pkg_resources \
    /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*

COPY --from=dashboard /app/dist /app/dashboard
COPY aio/docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chown -R honeywatch:honeywatch /app

USER honeywatch

# Use the prebuilt venv directly at runtime; avoids uv cache init at start.
ENV PATH="/app/.venv/bin:$PATH"
ENV DASHBOARD_DIST=/app/dashboard

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health').read()" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
