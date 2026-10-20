# PetTwin AI backend image.
#
# Built from the REPOSITORY ROOT, not from backend/, because the app reads files
# outside the backend package: the veterinary PDFs under rag/documents/ and the
# case table under data/external/. The build context must therefore be the root.
#
# The fastembed ONNX model is downloaded at BUILD time (not first request) so a
# cold start does not also pay the ~130 MB model download. It lands in a fixed
# cache directory that HF_HOME points at, which is copied into the image.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/models \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

# libgomp1 is required by onnxruntime for CPU inference.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Pre-download the embedding model into HF_HOME so runtime has no network need.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5'); print('embedding model cached')"

# Copy the application and the assets it reads at runtime.
COPY backend/ ./backend/
COPY rag/ ./rag/
COPY data/ ./data/

WORKDIR /app/backend

# Render provides $PORT; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
