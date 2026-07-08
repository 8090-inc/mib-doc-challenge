ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

# Offline OCR + PDF tooling; everything installed at build time, no network
# access needed at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip \
      tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY solution/requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

COPY solution/mib_pipeline /app/mib_pipeline
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh \
    && /opt/venv/bin/python -m compileall -q /app/mib_pipeline

# Runtime hardening: read-only root, all scratch writes to /tmp.
ENV PATH="/opt/venv/bin:$PATH" \
    HOME=/tmp \
    TMPDIR=/tmp \
    OMP_THREAD_LIMIT=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

ENTRYPOINT ["/app/run.sh"]
