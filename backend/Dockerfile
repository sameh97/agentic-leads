# ─────────────────────────────────────────────────────────────
# Stage 1: dependency builder
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────────────────────
# Stage 2: runtime image
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /install /usr/local

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 curl \
 && rm -rf /var/lib/apt/lists/*

COPY . .

# Create output dir and set permissions BEFORE switching to non-root user.
# The named Docker volume is mounted at /app/output — we need appuser (1001)
# to own it. The 'chmod 777' ensures the volume mount point stays writable
# even after Docker overwrites directory ownership on volume attach.
RUN mkdir -p /app/output \
 && useradd -m -u 1001 appuser \
 && chown -R appuser:appuser /app \
 && chmod 777 /app/output

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]