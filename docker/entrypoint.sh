#!/usr/bin/env bash
#
# Container entrypoint for BAIF Bhasha.
#
# Its whole job is the one step a container can't inherit from the host: the
# ~2-4 GB of gated Hugging Face model weights. The image ships without them
# (see docker/Dockerfile), so on first start this downloads them into the
# `baif-data` volume, where they persist across restarts, rebuilds and image
# upgrades. Every later start finds the marker file and goes straight to the
# server.
#
# Skipped entirely when the image was built with --build-arg BAKE_MODELS=1:
# that build writes the same marker at build time.

set -euo pipefail

BACKEND_DIR=/app/backend
DATA_DIR="${BAIF_DATA_DIR:-$BACKEND_DIR/data}"
MARKER="$DATA_DIR/.models_ready"

ASR_MODEL="${BAIF_ASR_MODEL:-medium}"
INCLUDE_TTS="${BAIF_INCLUDE_TTS:-0}"
WANT="asr=$ASR_MODEL;tts=$INCLUDE_TTS"

log() { printf '[baif] %s\n' "$*"; }

# ----------------------------------------------------------------------
# Resolve the Hugging Face token.
#
# Priority: HF_TOKEN in the environment (compose passes it through from
# .env) -> a mounted file. Both paths end with HF_TOKEN exported, which is
# the variable huggingface_hub reads on its own.
# ----------------------------------------------------------------------
if [[ -z "${HF_TOKEN:-}" ]]; then
    for candidate in "${BAIF_HF_TOKEN_FILE:-}" /run/secrets/hf_token /app/hf_token.txt /app/.env; do
        [[ -n "$candidate" && -s "$candidate" ]] || continue
        # Accepts either a bare token on its own line or a KEY=VALUE .env
        # file; strips surrounding quotes and any stray CR from a file that
        # was last saved on Windows.
        token="$(sed -n 's/^[[:space:]]*HF_TOKEN[[:space:]]*=[[:space:]]*//p' "$candidate" | head -n1)"
        # Bare-token fallback, but only for lines that aren't KEY=VALUE --
        # otherwise a .env with no HF_TOKEN line at all would hand us
        # something like "BAIF_HOST_PORT=8000" and call it a token.
        [[ -n "$token" ]] || token="$(grep -v '^[[:space:]]*#' "$candidate" | grep -v '=' | head -n1)"
        token="$(printf '%s' "$token" | tr -d '\r' | sed -e 's/^["'"'"']//' -e 's/["'"'"']$//' -e 's/[[:space:]]*$//')"
        if [[ -n "$token" ]]; then
            export HF_TOKEN="$token"
            log "using Hugging Face token from $candidate"
            break
        fi
    done
fi

# ----------------------------------------------------------------------
# First-run model download.
# ----------------------------------------------------------------------
if [[ "${BAIF_SKIP_MODEL_SETUP:-0}" == "1" ]]; then
    log "BAIF_SKIP_MODEL_SETUP=1 -- not checking models"
elif [[ -f "$MARKER" ]] && [[ "$(cat "$MARKER")" == "$WANT" ]]; then
    log "models already present ($WANT) -- starting straight up"
else
    if [[ -f "$MARKER" ]]; then
        log "model set changed ($(cat "$MARKER") -> $WANT) -- fetching what's missing"
    else
        log "first start: downloading models into the data volume."
        log "this is a one-time, multi-GB download -- expect 10-40 minutes."
    fi

    if [[ -z "${HF_TOKEN:-}" ]]; then
        cat >&2 <<'MSG'

[baif] ERROR: no Hugging Face token found, and the IndicTrans2 translation
       models are gated repos that cannot be downloaded without one.

       Fix it on the host, in the folder next to docker-compose.yml:

         1. copy .env.example to .env
         2. paste your token into it:   HF_TOKEN=hf_xxxxxxxxxxxxxxxxx
         3. docker compose up

       A token comes from https://huggingface.co/settings/tokens, and the
       account it belongs to must first have accepted access on each model
       page -- see DOCKER.md.

MSG
        exit 1
    fi

    cd "$BACKEND_DIR"
    args=()
    [[ "$INCLUDE_TTS" == "1" ]] || args+=(--skip-tts)

    if ! python scripts/download_models.py "${args[@]}"; then
        cat >&2 <<'MSG'

[baif] ERROR: model download failed (see the messages above).

       The usual cause is a token whose account hasn't accepted the gate on
       each model page yet. Open each of these while logged in, click
       "Agree and access repository", then re-run `docker compose up`:

         https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M
         https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
         https://huggingface.co/ai4bharat/indictrans2-indic-indic-dist-320M

       Nothing already downloaded is lost -- the volume keeps it and the
       next run resumes from there.

MSG
        exit 1
    fi

    printf '%s' "$WANT" > "$MARKER"
    log "models ready."
fi

log "starting server on ${BAIF_HOST:-0.0.0.0}:${BAIF_PORT:-8000}"
cd "$BACKEND_DIR"
exec "$@"
