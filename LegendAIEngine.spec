# -*- mode: python ; coding: utf-8 -*-
"""Bundle onedir do motor Python utilizado pelo Electron."""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    copy_metadata,
)

datas, binaries, hiddenimports = [], [], []

for meta_pkg in ("torchcodec", "torchaudio", "torch", "transformers", "tokenizers"):
    try:
        datas += copy_metadata(meta_pkg)
    except Exception:  # noqa: BLE001 - metadata opcional no ambiente de build
        pass

for package in ("whisperx", "torch", "torchaudio", "transformers", "faster_whisper"):
    package_data, package_binaries, package_hidden = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_hidden

hiddenimports += collect_submodules("transformers.models.wav2vec2")
hiddenimports += collect_submodules("transformers.models.auto")


def add_data_tree(source_root: Path, destination_root: Path) -> None:
    for source in source_root.rglob("*"):
        if source.is_file():
            destination = destination_root / source.parent.relative_to(source_root)
            datas.append((str(source), str(destination)))


add_data_tree(Path("vendor"), Path("vendor"))

a = Analysis(
    ["engine_entry.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "IPython", "jupyter", "tkinter", "customtkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LegendAIEngine",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/legendai.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LegendAIEngine",
)
