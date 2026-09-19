# -*- mode: python ; coding: utf-8 -*-
"""Bundle onedir do motor Python utilizado pelo Electron.

Este motor só ALINHA: recebe o roteiro pronto e usa o wav2vec2 para descobrir
o início e o fim de cada palavra. Ele nunca transcreve e nunca separa
locutores — mas o whisperx traz essas duas portas abertas (`asr` e `diarize`),
e um `collect_all` as seguia até o fim. Entravam no instalador, para nada:
faster_whisper, ctranslate2, onnxruntime, pyannote, o lightning inteiro (134 MB)
e as 384 arquiteturas do transformers, das quais usamos uma (88 MB).

Por isso a coleta aqui é nominal, e não por varredura: o que o alinhamento não
importa não viaja junto.
"""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

# Os módulos do whisperx que o alinhamento realmente toca. `asr`, `diarize`,
# `vads` e `transcribe` ficam de fora de propósito.
WHISPERX_USADO = [
    "whisperx.alignment",
    "whisperx.audio",
    "whisperx.utils",
    "whisperx.schema",
    "whisperx.conjunctions",
    "whisperx.log_utils",
]

# As três arquiteturas que o alinhamento realmente carrega, conferidas olhando
# o `sys.modules` depois de abrir o modelo de verdade. `wav2vec2` é o modelo,
# `auto` é o mapa que o resolve pelo nome e `encoder_decoder` entra de carona
# no `AutoTokenizer`, de que o Wav2Vec2Processor depende. Sem esta última o
# processador não abre — e o erro só aparece com um modelo em mãos, não na
# importação.
MODELOS_MANTIDOS = {"wav2vec2", "auto", "encoder_decoder"}

# Pacotes que só existem para transcrever, separar locutores ou treinar.
EXCLUIDOS = [
    "faster_whisper", "ctranslate2", "onnxruntime", "onnxruntime_tools",
    "pyannote", "lightning", "pytorch_lightning", "lightning_fabric",
    "lightning_utilities", "torchmetrics", "asteroid_filterbanks", "julius",
    "optuna", "tensorboardX", "speechbrain",
    "whisperx.asr", "whisperx.diarize", "whisperx.vads", "whisperx.transcribe",
    "matplotlib", "IPython", "jupyter", "notebook", "tensorboard",
    # A interface antiga em CustomTkinter saiu do projeto.
    "tkinter", "customtkinter",
]

datas, binaries, hiddenimports = [], [], []

for meta_pkg in ("torchcodec", "torchaudio", "torch", "transformers", "tokenizers"):
    try:
        datas += copy_metadata(meta_pkg)
    except Exception:  # noqa: BLE001 - metadata opcional no ambiente de build
        pass

for package in ("torch", "torchaudio", "transformers"):
    package_data, package_binaries, package_hidden = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_hidden

# whisperx entra por nome: um collect_all aqui reabriria as portas fechadas
# acima, porque ele varre todos os submódulos do pacote.
datas += collect_data_files("whisperx")
hiddenimports += WHISPERX_USADO

hiddenimports += collect_submodules("transformers.models.wav2vec2")
hiddenimports += collect_submodules("transformers.models.auto")


PACOTES_MORTOS = {
    "onnxruntime", "lightning", "pytorch_lightning", "lightning_fabric",
    "lightning_utilities", "torchmetrics", "ctranslate2", "faster_whisper",
    "pyannote", "asteroid_filterbanks", "julius", "optuna", "speechbrain",
    "matplotlib",
}


def modulo_descartado(nome: str) -> bool:
    """Diz se um módulo fica de fora do arquivo PYZ."""
    partes = nome.split(".")
    if partes[0] in PACOTES_MORTOS:
        return True
    # transformers.models.<arquitetura>
    return (
        len(partes) >= 3
        and tuple(partes[:2]) == ("transformers", "models")
        and partes[2] not in MODELOS_MANTIDOS
    )


def dado_descartado(destino: str) -> bool:
    """Idem para arquivos, mais os cabeçalhos C++ do torch.

    `torch/include` são 36 MB de headers usados para compilar extensões, que
    nenhuma execução lê. O `split("-")` resolve as pastas de metadados, que
    chegam como `onnxruntime-1.29.0.dist-info`.

    O corte das arquiteturas exige quatro níveis, e não três: um arquivo solto
    em `transformers/models/` — o `__init__.py`, que o transformers abre **no
    disco** para montar o mapa preguiçoso — tem exatamente três partes, e
    apagá-lo derruba o `from transformers import Wav2Vec2ForCTC` inteiro. Uma
    arquitetura de verdade sempre tem uma pasta a mais.
    """
    partes = Path(destino).parts
    if not partes:
        return False
    if partes[0].split("-")[0] in PACOTES_MORTOS:
        return True
    if tuple(partes[:2]) == ("torch", "include"):
        return True
    return (
        len(partes) >= 4
        and tuple(partes[:2]) == ("transformers", "models")
        and partes[2] not in MODELOS_MANTIDOS
    )


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
    excludes=EXCLUIDOS,
    noarchive=False,
)
# A poda que vale acontece aqui, e não sobre as listas acima: o PyInstaller
# roda os hooks dele em cima do que passamos, e o hook do transformers faz o
# próprio `collect_all` — devolvendo inteiras as 384 arquiteturas que tínhamos
# acabado de tirar. O resultado da análise é o único ponto onde a decisão se
# sustenta. (Medido: sem isto, 371 das 384 voltavam para dentro do bundle.)
a.datas = [item for item in a.datas if not dado_descartado(item[0])]
a.binaries = [item for item in a.binaries if not dado_descartado(item[0])]
a.pure = [item for item in a.pure if not modulo_descartado(item[0])]

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
