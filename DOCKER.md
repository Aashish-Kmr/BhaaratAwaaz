# Running BAIF Bhasha in Docker (CPU)

The container is the CPU build of the app — the same `requirements-cpu.txt`
dependency set as [PACKAGING.md](PACKAGING.md) step 2, just with the Linux
flavour of the CPU-only torch wheel — wrapped so that a Windows machine
needs exactly two things installed: **Docker Desktop** and nothing else.

What the container removes from the native-install checklist:

| Native install (PACKAGING.md) | In the container |
| --- | --- |
| Install Python 3.12 specifically (3.13 breaks the torch/transformers wheels) | baked into the image |
| Install Node, `npm install`, `npm run build` | done in the image build |
| Install `git` so `parler_tts` can install from GitHub | done in the image build |
| Download `ffmpeg.exe` by hand and drop it next to the launcher | `apt-get install ffmpeg` in the image |
| PowerShell execution-policy fights with `Activate.ps1` | no venv activation at all |
| Hugging Face login on every machine that runs it | one token in one file, or zero with a baked image |

What it doesn't remove: the models are gated on Hugging Face, so **someone**
has to accept the gate once with a real account. Everything below is about
making that "once" actually mean once.

---

## 1. Install Docker Desktop

Download from <https://www.docker.com/products/docker-desktop/> and install
with the **WSL 2 backend** (the default, and the only one worth using here —
the Hyper-V backend is slower and gets less testing).

Give it enough memory. faster-whisper `medium` plus IndicTrans2 wants
comfortably more than Docker Desktop's default share on a 8 GB laptop. Create
or edit `C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
memory=10GB
processors=6
```

then, in PowerShell, `wsl --shutdown` and restart Docker Desktop. If the
machine only has 8 GB total, set `memory=6GB` and use the smaller ASR model
(`BAIF_ASR_MODEL=small` in step 2) — `medium` on 6 GB will OOM mid-job.

Give it disk, too. The image is ~4 GB and the models another ~3 GB, all of
it inside Docker's virtual disk rather than on your C: drive directly, so
budget **20 GB free**. Docker Desktop → Settings → Resources shows the disk
image location and lets you move it to another drive if C: is tight.

Check it's alive before going further:

```powershell
docker version
```

## 2. Get a Hugging Face token into `.env`

Once, on any machine, with a Hugging Face account:

1. Open each page below **while logged in** and click *Agree and access
   repository*. The three IndicTrans2 ones are instant click-throughs:
   - <https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M>
   - <https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M>
   - <https://huggingface.co/ai4bharat/indictrans2-indic-indic-dist-320M>
   - <https://huggingface.co/ai4bharat/indic-parler-tts> — only if you want
     the audio-dubbing bonus. This one is an "authorized list" gate that may
     need manual review, so leave it out unless you specifically need it.
2. Create a token at <https://huggingface.co/settings/tokens>. A
   **fine-grained, read-only** token is the right kind — it only ever needs
   to read public-but-gated repos.
3. In the repo root (the folder holding `docker-compose.yml`):

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Paste the token after `HF_TOKEN=`, with no quotes and no spaces:

   ```ini
   HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

Docker Compose reads `.env` automatically — no flags, no `docker login`, no
`huggingface-cli`. The same file also works for the *native* install: the
`scripts/download_models.py` in step 3 of PACKAGING.md now picks the token up
from `.env` (or from a `hf_token.txt` holding just the token) instead of
requiring `huggingface-cli login`.

> `.env` is gitignored on purpose. Hugging Face and GitHub both scan public
> pushes for tokens and revoke them on sight, so a committed token quietly
> stops working — usually right before a demo. To hand the app to someone
> else, either send them the `.env` out of band, or (better) give them an
> image with the models already inside it, which needs no token at all —
> section 6.

## 3. Start it

```powershell
docker compose up --build
```

Or just double-click **`start-docker.bat`**, which does the same thing, waits
for the app to answer, and opens the browser for you.

The first run does three slow things, once each:

1. builds the image (~10 min: torch and friends are a big download)
2. downloads ~2.5 GB of model weights into a Docker volume named `baif-data`
   (Compose prefixes it with the folder name, so `docker volume ls` shows it
   as something like `baif-integrated_baif-data`) - 10–40 min depending on
   the connection
3. loads the models into memory on the first job

Watch for `[baif] models ready.` followed by uvicorn's startup line. Then
open <http://localhost:8000>.

Every later start skips 1 and 2 entirely — the image is cached and the volume
keeps the weights, so it's up in seconds.

```powershell
docker compose up          # start again later
docker compose down        # stop, keeping the models
docker compose logs -f     # watch what it's doing
```

`docker compose down -v` also deletes the `baif-data` volume — i.e. throws
away the multi-GB download. That's rarely what you want.

## 4. Settings worth knowing

All of these go in `.env`, next to `HF_TOKEN`:

| Variable | Default | What it does |
| --- | --- | --- |
| `BAIF_HOST_PORT` | `8000` | Port on your machine. Change it if something else already owns 8000. |
| `BAIF_ASR_MODEL` | `medium` | faster-whisper size. `small` or `base` are much faster on a CPU-only box and download far less. Changing it makes the next start fetch the new one. |
| `BAIF_INCLUDE_TTS` | `0` | `1` also downloads Indic Parler-TTS (several GB) for the audio-dubbing bonus. |

The image lands around 4 GB. Roughly 600 MB of that is the Parler-TTS
dubbing stack (`descript-audio-codec` drags in matplotlib and tensorboard),
which is dead weight if you never turn on `BAIF_INCLUDE_TTS`. Dropping the
`parler_tts` and `descript-audio-codec` lines from
`backend/requirements.txt` before building removes it — same tradeoff
PACKAGING.md step 2 describes, and only `POST /api/jobs/{id}/dubbed-audio`
stops working.

Everything in `app/config.py` can be set the same way by adding it to the
`environment:` block in `docker-compose.yml` — `BAIF_TRANSLATION_BATCH_SIZE`,
`BAIF_ASR_BEAM_SIZE`, `BAIF_TORCH_THREADS` and so on are all worth
experimenting with if a demo machine turns out to be slow.

## 5. The GPU question

This image is CPU-only, deliberately and unconditionally, and the "Process on
GPU" toggle in the UI will always show as unavailable in it. That's the same
tradeoff as `requirements-cpu.txt` in PACKAGING.md step 6b: a CPU-only torch
build has no CUDA compiled in to turn on, whatever the hardware.

Making the container use an NVIDIA GPU is not just a matter of swapping the
requirements file — it needs the NVIDIA Container Toolkit, a matching driver
inside WSL2, and `deploy.resources.reservations.devices` in the compose file.
If you have a machine with a real GPU, the **native GPU build in PACKAGING.md
step 6b is the better path**; it's the one that's actually been exercised.

## 6. Shipping it to someone with no Hugging Face account

The default setup downloads models at first *run*, which means the target
machine needs the token and internet. To move that requirement to *your*
machine instead, build an image with the weights already inside it:

```powershell
docker compose -f docker/compose.baked.yml build
```

The token is read from `.env` through a BuildKit secret mount, which exists
only for that one build step and is never written into a layer — so the
resulting image is safe to hand around whole. It's several GB bigger, and the
machine that runs it needs no account, no token, and no network:

```powershell
# on your machine
docker save baif-bhasha:cpu-models -o baif-bhasha.tar

# on theirs
docker load -i baif-bhasha.tar
docker compose -f docker/compose.baked.yml up
```

(`docker save` output compresses well — `docker save ... | gzip > x.tar.gz` if
you have to move it over a network.)

## 7. When something goes wrong

**`exec /app/docker/entrypoint.sh: no such file or directory`**
The "missing file" is really the interpreter: a Windows checkout turned the
script's LF line endings into CRLF, so the kernel is looking for
`/usr/bin/env bash\r`. `.gitattributes` prevents this on a fresh clone and the
Dockerfile strips CRs anyway, so if you see it, you're building from a stale
copy — `git checkout -- docker/entrypoint.sh` and rebuild.

**`ERROR: no Hugging Face token found`**
`.env` is missing, is in the wrong folder, or has an empty `HF_TOKEN=`. It
must sit in the same folder as `docker-compose.yml`. To see what Compose
actually picked up: `docker compose config | Select-String HF_TOKEN`
(`docker compose config | grep HF_TOKEN` on macOS/Linux).

**`GatedRepoError` / `401` / `403` during the download**
The token is valid but its account hasn't accepted the gate on that specific
model page. Re-read step 2.1 — it's per-repo, and the error names which one.
Nothing already downloaded is lost; fix the access and `docker compose up`
again to resume.

**The build fails downloading torch**
`requirements-docker-cpu.txt` pulls torch from PyTorch's own wheel index
rather than PyPI. On a corporate network that blocks
`download.pytorch.org`, that's the failure. There's no clean workaround here
beyond an unblocked network — installing plain PyPI torch instead would drag
~4 GB of unusable NVIDIA CUDA libraries into a CPU image, which is exactly
what that file exists to avoid.

**A job dies partway through, or the container restarts on its own**
Almost always memory. Docker Desktop killed it (`docker compose logs` ends
abruptly, or `docker inspect baif-bhasha --format '{{.State.OOMKilled}}'`
says `true`). Raise `memory=` in `.wslconfig`, or drop to
`BAIF_ASR_MODEL=small`.

**Port 8000 is already in use**
Set `BAIF_HOST_PORT=8080` in `.env` and use <http://localhost:8080>.

**Uploads or results seem to vanish between restarts**
They live in the `baif-data` volume, not in the repo folder. That's
intentional (a Windows bind mount would cross the WSL2 filesystem boundary
and make every model read slow). Download results through the UI while the
container is up.

## 8. What's where

| Path | Purpose |
| --- | --- |
| `docker/Dockerfile` | Three-stage build: frontend → Python venv → slim runtime. |
| `docker/entrypoint.sh` | Resolves the token, downloads models on first start, then runs the server. |
| `docker/compose.baked.yml` | Standalone compose for the models-in-the-image variant (section 6). |
| `docker-compose.yml` | The normal one. |
| `.env.example` | Template for `.env`. |
| `.dockerignore` | Keeps `backend/data/` (7-8 GB on a dev machine) out of the build context. |
| `backend/requirements-docker-cpu.txt` | `requirements.txt` + the Linux CPU-only torch wheels. |
| `start-docker.bat` | Double-click launcher for Windows. |
