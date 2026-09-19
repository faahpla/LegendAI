"""Modelo de alinhamento: onde ele mora e como ele chega até aqui.

O wav2vec2 do português pesa 1,2 GB em float32 — sozinho, mais que todo o
resto do instalador. Ele não viaja mais dentro do aplicativo: chega na
primeira geração, é regravado em float16 e fica guardado ao lado das
configurações, ocupando metade.

O float16 aqui é escolha de disco, não de cálculo. O `from_pretrained` monta o
modelo em float32 de qualquer forma, então a conta continua sendo feita na
precisão de sempre — o que importa, porque boa parte das operações do wav2vec2
não existe em meia precisão na CPU, e é em CPU que o aplicativo publicado roda.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .settings import Settings
from .utils import resource_path

log = logging.getLogger("legendai.modelo")

ProgressFn = Callable[[str, float], None]

BASE_HUGGINGFACE = "https://huggingface.co"

# Os quatro descritores são pequenos; os pesos são o download de verdade. O
# repositório traz ainda um modelo de linguagem e logs de avaliação, que só
# servem para transcrever — nada disso é baixado.
DESCRITORES = ("config.json", "preprocessor_config.json", "special_tokens_map.json", "vocab.json")
PESOS_ORIGINAIS = "pytorch_model.bin"
PESOS_CONVERTIDOS = "model.safetensors"

# Espaço reservado à preparação do modelo dentro da barra de progresso. O
# restante do fluxo começa em 0,10.
FAIXA = (0.01, 0.09)


class ModelDownloadError(RuntimeError):
    """O modelo de alinhamento não pôde ser obtido."""


def repositorio(language: str) -> str | None:
    """Repositório do HuggingFace que o whisperx usa para este idioma.

    Devolve `None` para os cinco idiomas atendidos por pacotes do torchaudio
    (inglês, francês, alemão, espanhol e italiano): esses o whisperx baixa
    sozinho, e não há o que guardar aqui.
    """
    from whisperx.alignment import DEFAULT_ALIGN_MODELS_HF

    return DEFAULT_ALIGN_MODELS_HF.get(language)


def pasta_do_idioma(language: str) -> Path:
    """Onde o modelo baixado fica: ao lado de settings.json e history.json.

    Precisa ser uma pasta do usuário, e não a da instalação — esta última fica
    em Arquivos de Programas, onde escrever exige administrador, e seria
    apagada a cada atualização do aplicativo.
    """
    return Settings().path.parent / "models" / language


def modelo_instalado(pasta: Path) -> bool:
    """Um modelo só conta como instalado se tiver descritor e pesos."""
    if not (pasta / "config.json").exists():
        return False
    return (pasta / PESOS_CONVERTIDOS).exists() or (pasta / PESOS_ORIGINAIS).exists()


def ensure_model(language: str, progress: ProgressFn) -> Path | None:
    """Garante o modelo em disco e devolve a pasta dele.

    Procura em três lugares, nesta ordem: um modelo embutido em `vendor`
    (ninguém embute mais, mas quem quiser montar uma versão offline ainda
    pode), o que já foi baixado antes, e por último a rede.
    """
    repo = repositorio(language)
    if repo is None:
        return None

    embutido = resource_path("vendor", "models", language)
    if modelo_instalado(embutido):
        log.info("Modelo embutido encontrado em %s", embutido)
        return embutido

    pasta = pasta_do_idioma(language)
    if modelo_instalado(pasta):
        return pasta

    _instalar(repo, pasta, progress)
    return pasta


def _instalar(repo: str, pasta: Path, progress: ProgressFn) -> None:
    """Baixa e converte numa pasta temporária, e só então assume o lugar.

    Montar direto no destino é o que transforma uma interrupção — queda de
    rede, cancelamento, falta de energia — em um modelo pela metade que passa
    na verificação da próxima abertura e só quebra lá no meio do alinhamento.
    """
    pasta.parent.mkdir(parents=True, exist_ok=True)
    temporaria = Path(tempfile.mkdtemp(prefix="legendai-modelo-", dir=pasta.parent))
    try:
        for nome in DESCRITORES:
            _baixar(f"{BASE_HUGGINGFACE}/{repo}/resolve/main/{nome}", temporaria / nome, progress, None)
        _baixar(
            f"{BASE_HUGGINGFACE}/{repo}/resolve/main/{PESOS_ORIGINAIS}",
            temporaria / PESOS_ORIGINAIS, progress, FAIXA,
        )
        _converter_para_meia_precisao(temporaria, progress)
        _conferir(temporaria)
        if pasta.exists():
            shutil.rmtree(pasta, ignore_errors=True)
        temporaria.replace(pasta)
        log.info("Modelo de alinhamento instalado em %s", pasta)
    except BaseException:
        shutil.rmtree(temporaria, ignore_errors=True)
        raise


def _baixar(url: str, destino: Path, progress: ProgressFn, faixa: tuple[float, float] | None) -> None:
    """Baixa um arquivo, avisando o andamento quando ele é grande.

    Grava em `.part` e renomeia no fim para que nem mesmo um arquivo solto
    sobreviva incompleto com o nome definitivo. `faixa` é o pedaço da barra de
    progresso que este arquivo ocupa; os descritores são pequenos demais para
    merecer um.
    """
    parcial = destino.with_name(destino.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as resposta:
            total = int(resposta.headers.get("Content-Length") or 0)
            baixado, ultimo_mb = 0, -1
            with parcial.open("wb") as arquivo:
                while bloco := resposta.read(1 << 20):
                    arquivo.write(bloco)
                    baixado += len(bloco)
                    if faixa is None:
                        continue
                    megabytes = baixado >> 20
                    if megabytes == ultimo_mb:
                        continue
                    ultimo_mb = megabytes
                    de_quanto = f" de {total >> 20} MB" if total else ""
                    inicio, fim = faixa
                    avanco = baixado / total if total else 0.0
                    progress(
                        f"Baixando o modelo de alinhamento... {megabytes} MB{de_quanto}",
                        inicio + (fim - inicio) * avanco,
                    )
    except urllib.error.URLError as erro:
        raise ModelDownloadError(
            "Não foi possível baixar o modelo de alinhamento. O LegendAI precisa "
            "de internet apenas na primeira geração; depois disso ele trabalha "
            f"offline. Detalhe: {erro.reason}"
        ) from erro
    parcial.replace(destino)


def _conferir(pasta: Path) -> None:
    """Abre o que acabou de ser gravado, antes de dar o modelo por instalado.

    Sem esta conferência, um modelo que não abre fica instalado do mesmo jeito:
    a verificação de arquivos passa, o download nunca é refeito, e o aplicativo
    entra em falha permanente sem caminho de volta — a não ser apagar a pasta
    na mão. Um segundo aqui troca isso por um erro na hora certa, com o
    download pronto para ser tentado de novo.
    """
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    Wav2Vec2Processor.from_pretrained(str(pasta), local_files_only=True)
    Wav2Vec2ForCTC.from_pretrained(str(pasta), local_files_only=True)


def _converter_para_meia_precisao(pasta: Path, progress: ProgressFn) -> None:
    """Regrava os pesos em float16 e descarta o arquivo original.

    São 1,2 GB que viram 600 MB. A precisão do alinhamento não muda: quem
    carrega é o `from_pretrained` sem `torch_dtype`, que monta o modelo em
    float32 e só usa o arquivo para preencher os valores.
    """
    progress("Preparando o modelo (isto acontece só uma vez)...", FAIXA[1])
    from transformers import Wav2Vec2ForCTC

    modelo = Wav2Vec2ForCTC.from_pretrained(str(pasta))
    modelo.half().save_pretrained(str(pasta), safe_serialization=True)
    (pasta / PESOS_ORIGINAIS).unlink(missing_ok=True)
