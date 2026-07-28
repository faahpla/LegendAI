# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller para o LegendAI.

Build em modo onedir (pasta): com WhisperX + PyTorch embutidos o pacote é
grande, e onedir inicia muito mais rápido que onefile nesse cenário.
"""

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)
from pathlib import Path
import sys

datas, binaries, hiddenimports = [], [], []

# O transformers lê importlib.metadata.version("torchcodec") ao importar o
# audio_utils (cadeia do Wav2Vec2ForCTC). Sem o .dist-info no bundle isso dá
# PackageNotFoundError. Copiamos os metadados dos pacotes consultados assim.
for meta_pkg in ("torchcodec", "torchaudio", "torch", "transformers", "tokenizers"):
    try:
        datas += copy_metadata(meta_pkg)
    except Exception:  # noqa: BLE001 - pacote ausente é ignorado
        pass
for package in ("whisperx", "torch", "torchaudio", "transformers", "faster_whisper"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# O transformers resolve os modelos por importação preguiçosa; o PyInstaller
# não os detecta sozinho. Coletamos explicitamente o wav2vec2 (usado pelo
# alinhamento forçado do WhisperX: Wav2Vec2ForCTC / Wav2Vec2Processor).
hiddenimports += collect_submodules("transformers.models.wav2vec2")
hiddenimports += collect_submodules("transformers.models.auto")

# tkinterdnd2 traz a extensão Tcl tkdnd (binários) usada no drag-and-drop.
tkdnd_datas, tkdnd_binaries, tkdnd_hidden = collect_all("tkinterdnd2")
datas += tkdnd_datas
binaries += tkdnd_binaries
hiddenimports += tkdnd_hidden

# O hook automático do PyInstaller não reconhece o Tcl/Tk desta instalação
# local do Python. Incluímos o pacote Python explicitamente; as DLLs e dados
# Tcl/Tk são adicionados mais abaixo.
hiddenimports += collect_submodules("tkinter")
hiddenimports += ["_tkinter", "tkinter.filedialog", "tkinter.ttk"]

datas += collect_data_files("customtkinter")
datas += [("assets/legendai.ico", "assets"), ("assets/legendai.png", "assets")]


def add_data_tree(source_root: Path, destination_root: Path) -> None:
    """Adiciona uma pasta inteira ao bundle, mantendo a hierarquia."""
    for source in source_root.rglob("*"):
        if source.is_file():
            destination = destination_root / source.parent.relative_to(source_root)
            datas.append((str(source), str(destination)))


# Recursos que tornam o instalador independente: FFmpeg, modelo pt-BR e NLTK.
add_data_tree(Path("vendor"), Path("vendor"))

# O ambiente atual do Python não deixa o hook automático detectar o Tk.
# Empacotamos explicitamente Tcl/Tk para que a interface abra em qualquer PC.
python_root = Path(sys.base_prefix)
add_data_tree(python_root / "Lib" / "tkinter", Path("tkinter"))
add_data_tree(python_root / "tcl" / "tcl8.6", Path("_tcl_data"))
add_data_tree(python_root / "tcl" / "tk8.6", Path("_tk_data"))
binaries += [
    (str(python_root / "DLLs" / "_tkinter.pyd"), "."),
    (str(python_root / "DLLs" / "tcl86t.dll"), "."),
    (str(python_root / "DLLs" / "tk86t.dll"), "."),
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "IPython", "jupyter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LegendAI",
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
    name="LegendAI",
)
