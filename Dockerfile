FROM python:3.14-slim-bookworm AS locale_builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gettext && rm -rf /var/lib/apt/lists/*
COPY locale/ ./locale/
RUN find locale -name '*.po' -exec sh -c 'msgfmt "$1" -o "${1%.po}.mo"' _ {} \;

FROM python:3.14-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt .
RUN python -m pip wheel --wheel-dir=/wheels -r requirements.txt

FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/home/app/.local/bin:$PATH
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
COPY --from=builder /wheels /wheels
COPY --from=builder /build/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /tmp/requirements.txt && rm -rf /wheels /tmp/requirements.txt
COPY --chown=app:app . .
COPY --from=locale_builder --chown=app:app /build/locale /app/locale
RUN mkdir -p /app/media /app/staticfiles && chown -R app:app /app/media /app/staticfiles
COPY --chown=app:app --chmod=0755 docker/start.sh /usr/local/bin/start
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/start"]
