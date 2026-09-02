# Shipping BAIF Bhasha to another machine, offline

This produces **one folder** that a second Windows machine can set up and run
with no internet at all: no `pip install` from PyPI, no Hugging Face account or
login, no `scripts\download_models.py`, no Node.js, no `git`.

It is a different path from `PACKAGING.md`, which builds a PyInstaller `.exe`.
Use this one when you want the receiving machine to have the actual project
(source, venv, models) rather than a frozen binary.

| | this bundle | `PACKAGING.md` `.exe` |
|---|---|---|
| target needs Python | yes (3.12, installer included) | no |
| target can edit/debug the code | yes | no |
| target-side steps | 2 commands | 1 double-click |
| your build time | ~20 min (mostly `pip wheel`) | ~1 hr + 16 GB of build output |

---

## Build it

From the repo root, with `backend\.venv` already working:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\offline\build-bundle.ps1 -OutDir D:\baif-offline
```

`-OutDir` must be **outside the repo** and on a drive with ~15 GB free.
Your `C:` has ~17 GB free and `D:` has ~223 GB, so use `D:`.

Useful switches:

| switch | effect |
|---|---|
| `-SkipDownloads` | don't fetch ffmpeg / Python / VC++ redist (place them in `bin\` and `installers\` yourself) |
| `-SkipWheelhouse` | reuse an existing `wheelhouse\` — saves the slowest step on a re-run |
| `-SkipFrontendBuild` | reuse the existing `frontend\dist` |
| `-PythonVersion 3.12.11` | bundle a different 3.12 patch release |

The script refuses to finish if verification fails, so a folder that finishes
building is a folder worth transferring.

### What it does, and the three traps it defuses

1. **Rebuilds the frontend with `VITE_USE_MOCK=false`, then proves it.**
   `src/api/index.js` does `String(import.meta.env.VITE_USE_MOCK) !== 'false'`.
   Vite inlines the env var but Rollup can't constant-fold through `String()`,
   so `mock.js` and its sample Devanagari text stay in the bundle *either way* —
   grepping for them tells you nothing. The script asserts on the inlined
   literal instead. Ship the wrong build and the recipient gets a convincing
   fake app that never calls the backend.

2. **Dereferences the Hugging Face cache's symlinks, then drops `blobs\`.**
   `huggingface_hub` stores real bytes in `blobs\` and symlinks them into
   `snapshots\` — NLLB-200 in your cache is stored this way. Most zip tools
   either break those links or silently duplicate 2.3 GB. `robocopy` (without
   `/SL`) follows them, after which `blobs\` is a byte-for-byte duplicate and
   gets emptied. That shape is already proven here: whisper-medium and
   parler-tts in your cache have an empty `blobs\` with real snapshot files,
   and both load fine offline today.

3. **Builds a wheelhouse instead of leaving `pip` to the network.**
   `requirements.txt` pins `parler_tts` to a **git URL**, and its own setup.py
   pulls `descript-audiotools` from git too — so a plain `pip install` on the
   target would need both `git` and internet. `pip wheel` turns them into
   ordinary `.whl` files here, once.

It also leaves out things that shouldn't travel:

- `backend\data\hf_cache\token` — **your Hugging Face token**, in plaintext
- `backend\data\jobs\` — your local test uploads and outputs
- `faster-whisper-small` — cached but unused; both Whisper pipelines are pinned
  to `medium` (0.45 GB saved)
- `backend\dist\` — the Aug 23 PyInstaller build, a week older than the source

`models--google--flan-t5-large` looks like the same kind of leftover and is
**kept on purpose**. `vendor/audio_ba/modules/audio/tts.py:60` builds the
dubbing description tokenizer from
`self.model.config.text_encoder._name_or_path`, which only resolves to
`google/flan-t5-large` at runtime — the string appears nowhere in the source, so
grep says it's unused. Drop it and dubbing dies offline fetching a tokenizer it
can never reach. It's 3.2 MB of tokenizer files (the weights live inside
parler-tts's own safetensors), and `verify_offline.py --full` now loads it
through the same indirection so this can't silently regress.

---

## Verify it

`build-bundle.ps1` runs the fast check automatically. For the real proof:

```powershell
backend\.venv\Scripts\python.exe D:\baif-offline\verify_offline.py --full
```

`--full` **blocks socket creation outright** and then loads all eight models.
Anything that still wants to reach Hugging Face fails here — on the machine
that can fix it — instead of at demo time.

The fast check verifies each weight file against a declared minimum size, not
just its existence. That is deliberate: the classic failure is a transfer that
flattens symlinks into 52-byte text stubs, leaving a cache that looks complete
in a directory listing.

---

## Transfer it

**Don't zip it.** The bundle is ~12.5 GB and almost all of that is
`.safetensors` / `.bin` weights, which are already incompressible — you'd spend
20 minutes to save maybe 3%. Worse, Windows PowerShell 5.1's `Compress-Archive`
fails on archives past ~2 GB.

Copy the folder instead:

```powershell
robocopy D:\baif-offline E:\baif-offline /E /R:2 /W:2 /MT:16
```

The destination drive must be **NTFS or exFAT** — FAT32 caps single files at
4 GB and the parler-tts weights are 3.5 GB, uncomfortably close.

If you genuinely need one file (email, upload portal), use 7-Zip in store mode
with split volumes — never Explorer's "Send to > Compressed folder":

```powershell
& "C:\Program Files\7-Zip\7z.exe" a -tzip -mx0 -v2g D:\baif-offline.zip D:\baif-offline\
```

---

## What the recipient does

Two commands, both in `README-FIRST.txt` inside the bundle:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1   # ~10-25 min, offline
powershell -ExecutionPolicy Bypass -File run.ps1     # opens http://127.0.0.1:8000
```

`setup.ps1` installs Python 3.12 from `installers\` if needed, creates the venv,
installs everything from `wheelhouse\` with `--no-index`, puts `ffmpeg.exe` in
`.venv\Scripts\` (so an activated shell finds it with no PATH change and no
admin rights), and finishes by running `verify_offline.py --full`.

### One thing to tell them out loud

**Python must be 3.12 — not 3.13 or 3.14.** Every wheel is tagged
`cp312-win_amd64` and pip will reject all of them on any other version. Your own
machine has 3.14 as the default `py` target and 3.12 alongside it; theirs may
differ. `setup.ps1` looks for 3.12 specifically and installs it if absent, so
an existing 3.13/3.14 is harmless — it just gets ignored.

Also worth saying: the project `README.md`'s "Run in development" section does
**not** apply to this bundle. In particular `python scripts\download_models.py`
should not be run — there is nothing left to fetch, and it flips `HF_HUB_OFFLINE`
back off, which is exactly what was keeping the app from reaching for a network
that isn't there.
