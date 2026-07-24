FROM python:3.12-slim

WORKDIR /app

# System dependencies for offline document processing:
#   tesseract-ocr  -> OCR engine for scanned/degraded image pages
#   poppler-utils  -> PDF rendering utilities (pdftoppm) used as an OCR fallback
#   libgl1/libglib -> runtime libs required by opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      poppler-utils \
      libgl1 \
      libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application code (runtime modules only; tests are kept out of the image)
COPY run.sh /app/run.sh
COPY solution.py ingest.py extract.py adjudicate.py trust.py vocab.py /app/
RUN chmod +x /app/run.sh

# Thread caps keep numeric libs from oversubscribing the 4 vCPU budget; the
# pipeline manages its own process pool. Overridable at runtime.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TESSERACT_NUM_THREADS=1 \
    PYTHONHASHSEED=0 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/run.sh"]
