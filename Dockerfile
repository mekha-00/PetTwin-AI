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
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    OMP_NUM_THREADS=1 \
    ORT_NUM_THREADS=1

# libgomp1 is required by onnxruntime for CPU inference.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY backend/requirements.txt ./backend/requirements.txt

# Install runtime deps only. pytest/httpx and uvicorn's "standard" extras
# (uvloop, httptools, watchfiles, websockets) are dev/observability weight we
# cannot afford inside the 512 MB free instance, so uvicorn is pinned plain.
RUN pip install --no-cache-dir \
        fastapi==0.115.6 \
        uvicorn==0.34.0 \
        python-multipart==0.0.20 \
        pydantic==2.10.4 \
        pydantic-settings==2.7.0 \
        email-validator==2.2.0 \
        SQLAlchemy==2.0.36 \
        psycopg2-binary==2.9.10 \
        PyJWT==2.10.1 \
        bcrypt==4.2.1 \
        pymupdf==2.0 \
        numpy==2.4.6 \
        fastembed==0.9.0 \
        onnxruntime==1.31.0 \
        groq==0.37.1 \
        langgraph==1.2.16 \
        langchain-groq==1.1.3 \
    && pip check

# Pre-download the embedding model into the EXACT directory the runtime reads
# (app/rag/embeddings.py honours FASTEMBED_CACHE_DIR). This must match, or the
# baked model is ignored and re-fetched at boot — the bug that caused the OOM.
ENV FASTEMBED_CACHE_DIR=/app/backend/.cache/fastembed \
    FASTEMBED_THREADS=1
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/app/backend/.cache/fastembed', threads=1); print('embedding model cached')"

# Copy the application and the assets it reads at runtime.
COPY backend/ ./backend/
COPY rag/ ./rag/
COPY data/ ./data/

WORKDIR /app/backend

# Build the embedding indexes once, at image build time. At runtime they load
# from disk in milliseconds instead of embedding 840 chunks on the first request
# (which peaked over 512 MB and got the free instance killed). Extra threads are
# safe here: this runs on the build machine, not the 512 MB runtime.
ENV INDEX_CACHE_DIR=/app/backend/.cache/indexes
RUN OMP_NUM_THREADS=4 ORT_NUM_THREADS=4 FASTEMBED_THREADS=4 \
    python -m app.scripts.build_indexes

# Render provides $PORT; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
