# Stellwerk im Container: Python 3.13, Node für Puppeteer, Chromium aus Debian.
# Chromium kommt aus apt statt aus dem Puppeteer-Download, weil Puppeteer für
# linux-arm64 kein Chrome liefert. So baut dasselbe Image auf amd64 und arm64.
# Node kommt aus dem offiziellen Image, nicht aus apt: Puppeteer 25 verlangt
# Node >= 22.12, Debian bookworm liefert 18 (Smoke-Lauf 27.10. daran gescheitert).
FROM node:22-bookworm-slim AS node

FROM python:3.13-slim-bookworm

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-liberation fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    STELLWERK_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt package.json package-lock.json ./
RUN pip install --no-cache-dir -r requirements.txt && npm ci --omit=dev

COPY . .
# data/ bleibt per .dockerignore draußen, damit keine Datenbank ins Image wandert.
# SQLite legt die Datei an, aber nicht den Ordner.
RUN chmod +x docker-entrypoint.sh && mkdir -p data uploads backups

EXPOSE 5000 5001
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["demo"]
