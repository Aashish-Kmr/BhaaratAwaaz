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
for local_dir, bundled_path in (("data/models", "data/models"), ("data/hf_cache", "data/hf_cache")):
    if os.path.isdir(local_dir) and os.listdir(local_dir):
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
