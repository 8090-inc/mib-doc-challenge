FROM python:3.11-slim-bookworm

# Offline OCR + PDF tooling. No network at runtime; everything pinned.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY solution/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY solution/mib_pipeline /app/mib_pipeline
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh \
    && python3 -m compileall -q /app/mib_pipeline

# Read-only root at runtime: send all scratch writes to /tmp.
ENV HOME=/tmp \
    TMPDIR=/tmp \
    OMP_THREAD_LIMIT=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["/app/run.sh"]
