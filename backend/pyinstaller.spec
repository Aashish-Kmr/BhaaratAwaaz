# -*- mode: python ; coding: utf-8 -*-
#
# Builds a --onedir distribution: a folder containing the `baif-bhasha`
# launcher plus everything it needs, INCLUDING the ML model weights already
# downloaded into ./data on this machine (run scripts/download_models.py
# before building -- see ../PACKAGING.md). Bundling them avoids requiring
# internet access (and the IndicTrans2 gated-repo click-through) on whatever
# machine ends up running the built app.
#
# Build with:
#   pyinstaller pyinstaller.spec

import os

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# These packages rely on dynamic imports / bundled data files that
# PyInstaller's static analysis won't find on its own.
for pkg in (
    "torch",
    "torchaudio",
    "transformers",
    "ctranslate2",
    "faster_whisper",
    "fitz",  # PyMuPDF
    "av",
    "IndicTransToolkit",
    # IndicTransToolkit.processor is a compiled Cython extension (.pyx ->
    # .pyd); PyInstaller's static analysis can't read imports written inside
    # a compiled binary, so it silently drops everything processor.pyx
    # imports that isn't already pulled in via some other, traceable path
    # elsewhere -- confirmed by running the built exe and hitting
    # `ImportError: cannot import name indic_detokenize` at startup.
    # indicnlp (indic-nlp-library-itt) and sacremoses are both used only
    # from inside that file, so both need collecting explicitly; regex
    # (imported there as `import regex as re` -- the third-party package,
    # not stdlib re) likely already rides in via transformers' own traced
    # import of it, but costs nothing to collect explicitly too rather than
    # trust that.
    "indicnlp",
    "sacremoses",
    "regex",
    "tqdm",
    "parler_tts",
    "soundfile",
    "librosa",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        # Package not installed in this build env (e.g. building without the
        # optional TTS dubbing stack) -- skip rather than fail the build.
        pass

datas += [
    ("../frontend/dist", "frontend/dist"),
    ("../fonts", "fonts"),
]

# Bundle whatever's already been downloaded into ./data (IndicTrans2 under
# data/models, faster-whisper + Parler-TTS under data/hf_cache -- see
# app/config.py's HF_HOME redirect). Skipped gracefully if a folder is
# empty/missing so a partial build (e.g. --skip-tts) still works.
#
# Set BAIF_PACKAGE_SKIP_TTS=1 to leave the Parler-TTS weights (several GB,
# by far the single largest model) out of this particular build -- e.g. to
# stay under Inno Setup's ~4.2GB single-file installer cap. The parler_tts
# Python package itself still gets bundled (via collect_all above), so
# nothing crashes; a job with dubbing checked on a machine built this way
# will just fail (no cached weights, no internet) instead of producing a
# dubbed track -- same tradeoff as skipping the model at download time (see
# scripts/download_models.py --skip-tts).
SKIP_TTS_MODEL = os.environ.get("BAIF_PACKAGE_SKIP_TTS") == "1"
TTS_MODEL_DIRNAME = "models--ai4bharat--indic-parler-tts"


def _walk_datas(local_dir, bundled_root, exclude_dirnames=()):
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirnames]
        rel_root = os.path.relpath(root, local_dir)
        dest_dir = bundled_root if rel_root == "." else os.path.join(bundled_root, rel_root)
        for name in files:
            yield (os.path.join(root, name), dest_dir)


for local_dir, bundled_path in (("data/models", "data/models"), ("data/hf_cache", "data/hf_cache")):
    if not (os.path.isdir(local_dir) and os.listdir(local_dir)):
        continue
    if SKIP_TTS_MODEL and local_dir == "data/hf_cache":
        datas += list(_walk_datas(local_dir, bundled_path, exclude_dirnames={TTS_MODEL_DIRNAME}))
    else:
        datas.append((local_dir, bundled_path))

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tensorboard", "sphinx", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="baif-bhasha",
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="baif-bhasha",
)
