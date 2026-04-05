# ─────────────────────────────────────────────────────────────
# Stage 1: dependency builder
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile dnspython / lxml
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

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Runtime system deps (lxml needs libxml2 at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 curl \
 && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY . .

# Create output directory for CSV/XLSX exports
RUN mkdir -p /tmp/leads

# Non-root user for security
RUN useradd -m -u 1001 appuser \
 && chown -R appuser:appuser /app /tmp/leads
USER appuser

EXPOSE 8000

# Health check — FastAPI /api/health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]