# syntax=docker/dockerfile:1.7
#
# ----------------------------------------------------------------------
# BAIF Bhasha - CPU-only container image
#
# Build from the REPO ROOT (the build context needs backend/, frontend/ and
# fonts/ together), not from inside docker/:
#
#     docker compose build          # normal path
#     docker build -f docker/Dockerfile -t baif-bhasha:cpu .
#
# Three stages:
#   1. frontend  - Node builds frontend/dist, then Node is thrown away.
#   2. pybuild   - compilers + git available, builds /opt/venv.
#   3. runtime   - slim base + ffmpeg only, with /opt/venv copied in.
#
# The split matters: `parler_tts` installs from GitHub (so the build needs
# `git`) and a couple of transitive deps may fall back to an sdist (so it
# needs a compiler), but none of that is needed once the venv exists. Two
# stages keep ~400 MB of toolchain out of the shipped image without the
# `apt-get purge` dance, which on this dependency set risks autoremoving
# libgomp1 -- the OpenMP runtime torch and ctranslate2 both dlopen at
# import time.
#
# Models are NOT copied from the host (backend/data/ is excluded by
# .dockerignore). They arrive one of two ways:
#   - default: downloaded on first container start into a named volume,
#     using the HF_TOKEN from your .env  (see docker/entrypoint.sh)
#   - BAKE_MODELS=1: downloaded at build time into the image itself, so the
#     machine that finally runs it needs no token and no network at all.
# See DOCKER.md.
# ----------------------------------------------------------------------


# ======================================================================
# Stage 1 -- frontend build
# ======================================================================
FROM node:22-bookworm-slim AS frontend

WORKDIR /build

# Copy the manifests alone first so the (slow) dependency install is cached
# and only re-runs when the dependency set actually changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./

# false = talk to the real backend instead of the in-memory mock frontend
# dev server. Vite picks VITE_-prefixed vars up from the process env, same
# as the `VITE_USE_MOCK=false npm run build` line in PACKAGING.md.
ENV VITE_USE_MOCK=false
RUN npm run build


# ======================================================================
# Stage 2 -- Python virtualenv
# ======================================================================
FROM python:3.12-slim-bookworm AS pybuild

# git: parler_tts and its own descript-audiotools dependency install from
#      GitHub rather than PyPI.
# build-essential: insurance for any transitive dep that has no manylinux
#      wheel and falls back to building from an sdist.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        build-essential \
 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /app/backend

COPY backend/requirements.txt backend/requirements-docker-cpu.txt ./

# The cache mount keeps wheels between builds, so a rebuild after editing a
# pin re-downloads only what changed instead of ~2 GB of torch again.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
 && pip install -r requirements-docker-cpu.txt

# Fail the build here, loudly, rather than at the first translation job:
# a CUDA-linked torch in a CPU image would still import but pull in the
# multi-GB NVIDIA stack we deliberately avoid above.
RUN python -c "import torch, torchaudio; \
assert '+cpu' in torch.__version__, f'expected a CPU-only torch build, got {torch.__version__}'; \
print('torch', torch.__version__, '/ torchaudio', torchaudio.__version__)"


# ======================================================================
# Stage 3 -- runtime
# ======================================================================
FROM python:3.12-slim-bookworm AS runtime

# ffmpeg: app/pipelines/video.py shells out to it to extract audio from an
#         uploaded video. Getting this for free is one of the better
#         reasons to run the app in a container on Windows -- the native
#         build needs an ffmpeg.exe copied in by hand (PACKAGING.md step 5).
# libgomp1: OpenMP runtime, dlopen'd by torch and ctranslate2.
# libsndfile1: the C library behind soundfile / librosa.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgomp1 \
        libsndfile1 \
        curl \
 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=pybuild /opt/venv /opt/venv

WORKDIR /app

# Lay the app out exactly like the repo, because app/config.py derives
# REPO_ROOT from the backend package's parent: with backend/ at /app/backend,
# FRONTEND_DIST_DIR resolves to /app/frontend/dist and FONT_DIR to
# /app/fonts, with no env overrides needed.
COPY backend/ /app/backend/
COPY fonts/ /app/fonts/
COPY --from=frontend /build/dist /app/frontend/dist
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

# Belt and braces against a Windows checkout that turned LF into CRLF
# despite .gitattributes (an unzipped source drop, say, rather than a clone).
RUN sed -i 's/\r$//' /app/docker/entrypoint.sh && chmod +x /app/docker/entrypoint.sh

# 0.0.0.0, not config.py's 127.0.0.1 default: inside a container the
# loopback interface is the container's own, so a 127.0.0.1 bind is
# unreachable from the host no matter how the port is published.
ENV BAIF_HOST=0.0.0.0 \
    BAIF_PORT=8000 \
    BAIF_OPEN_BROWSER=0 \
    BAIF_ASR_MODEL=medium \
    BAIF_INCLUDE_TTS=0

# ----------------------------------------------------------------------
# Optional: bake the model weights into the image at build time.
#
#   docker build -f docker/Dockerfile -t baif-bhasha:cpu-models \
#     --build-arg BAKE_MODELS=1 --secret id=hf_env,src=.env .
#
# The token is read from a BuildKit secret mount, which exists only for the
# duration of this one RUN and is never written to a layer -- so the
# resulting image can be shared (docker save / a registry) without the
# token riding along inside it. The image gets several GB larger and needs
# no Hugging Face account on the machine that runs it.
# ----------------------------------------------------------------------
ARG BAKE_MODELS=0
RUN --mount=type=secret,id=hf_env \
    if [ "$BAKE_MODELS" = "1" ]; then \
        set -eu; \
        cd /app/backend; \
        [ "$BAIF_INCLUDE_TTS" = "1" ] || set -- --skip-tts; \
        BAIF_HF_TOKEN_FILE=/run/secrets/hf_env python scripts/download_models.py "$@"; \
        echo "asr=$BAIF_ASR_MODEL;tts=$BAIF_INCLUDE_TTS" > /app/backend/data/.models_ready; \
    else \
        echo "BAKE_MODELS=0 -- models will be downloaded on first container start"; \
    fi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

# Zombie reaping for the ffmpeg subprocesses the video pipeline spawns is
# handled by `init: true` in the compose files (Docker's own bundled init),
# rather than by installing tini here.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["python", "run.py"]
