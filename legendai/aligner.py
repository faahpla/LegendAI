"""Alinhador temporal baseado em WhisperX (alinhamento forçado).

O WhisperX NÃO transcreve aqui: recebemos o roteiro pronto e usamos apenas
o modelo de alinhamento (wav2vec2) para descobrir início e fim de cada
palavra do roteiro dentro do áudio. O texto retornado é sempre o token
original do roteiro.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .engine import Word
from .model_store import ensure_model
from .utils import normalize_word, prepare_runtime_environment, strip_accents

ProgressFn = Callable[[str, float], None]

_SAMPLE_RATE = 16_000


@dataclass
class AlignmentReport:
    """Resultado do alinhamento com os indicadores de qualidade.

    ``score`` é a confiança média que o wav2vec2 atribuiu às palavras — o
    alinhamento forçado sempre devolve tempos, mesmo para um áudio que não
    tem nada a ver com o roteiro, então é a confiança (e não a existência de
    tempos) que denuncia o descasamento. Fica ``None`` quando a versão do
    WhisperX não informa pontuação, caso em que a verificação é ignorada.
    ``coverage`` é a fração de tokens do roteiro que receberam tempo.
    """

    words: list[Word]
    duration: float
    coverage: float
    score: float | None


def tokenize_script(script: str) -> list[str]:
    """Divide o roteiro em tokens por espaço, preservando a pontuação."""
    return [token for token in script.split() if token.strip()]


class WhisperXAligner:
    """Encapsula o carregamento do modelo e o alinhamento forçado."""

    def __init__(self, language: str = "pt", device: str | None = None) -> None:
        self.language = language
        self._device = device
        self._model = None
        self._metadata = None

    @property
    def device(self) -> str:
        if self._device is None:
            import torch

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        return self._device

    def _ensure_model(self, progress: ProgressFn) -> None:
        if self._model is not None:
            return
        # Carregar o torch e o transformers leva uns dez segundos, e sem um
        # aviso antes disso a tela fica parada sem dizer no quê.
        progress("Preparando o alinhamento...", 0.01)
        prepare_runtime_environment()
        # Pode baixar o modelo, se esta for a primeira geração da máquina.
        pasta = ensure_model(self.language, progress)

        progress("Carregando WhisperX (modelo de alinhamento)...", 0.10)
        import whisperx

        if pasta is None:
            # Idioma atendido por um pacote do torchaudio: quem cuida do
            # download é o próprio whisperx.
            self._model, self._metadata = whisperx.load_align_model(
                language_code=self.language, device=self.device
            )
        else:
            self._model, self._metadata = whisperx.load_align_model(
                language_code=self.language,
                device=self.device,
                model_name=str(pasta),
                model_cache_only=True,
            )
        self._model = self._precisao_do_dispositivo(self._model)

    def _precisao_do_dispositivo(self, modelo):
        """Garante float32 quando a conta vai rodar na CPU.

        O modelo fica em meia precisão no disco, e o `from_pretrained` monta
        float32 sem que se peça nada. Se alguma versão do transformers passar a
        respeitar o dtype gravado, a conta cairia em meia precisão na CPU —
        onde parte das operações do wav2vec2 simplesmente não existe. A guarda
        custa duas linhas e evita um erro que só apareceria depois de
        instalado.
        """
        import torch

        if self.device == "cpu" and next(modelo.parameters()).dtype == torch.float16:
            return modelo.float()
        return modelo

    def align(
        self, audio_path: Path, script: str, progress: ProgressFn
    ) -> AlignmentReport:
        """Alinha o roteiro ao áudio e reporta a qualidade do resultado."""
        tokens = tokenize_script(script)
        if not tokens:
            raise ValueError("O roteiro está vazio.")

        prepare_runtime_environment()
        self._ensure_model(progress)

        progress("Extraindo áudio...", 0.25)
        import whisperx

        audio = whisperx.load_audio(str(audio_path))
        duration = len(audio) / _SAMPLE_RATE

        progress("Sincronizando palavras (alinhamento forçado)...", 0.35)
        segments = [{"start": 0.0, "end": duration, "text": " ".join(tokens)}]
        result = whisperx.align(
            segments,
            self._model,
            self._metadata,
            audio,
            self.device,
            return_char_alignments=False,
        )

        aligned = self._collect_aligned_words(result)
        progress("Mapeando tempos para o roteiro...", 0.62)
        words = self._map_to_tokens(tokens, aligned)
        timed = sum(1 for word in words if word.start is not None)
        return AlignmentReport(
            words=words,
            duration=duration,
            coverage=timed / len(words) if words else 0.0,
            score=self._mean_score(aligned),
        )

    @staticmethod
    def _mean_score(aligned: list[dict]) -> float | None:
        """Confiança média das palavras alinhadas (None se indisponível)."""
        scores = [
            float(raw["score"]) for raw in aligned
            if isinstance(raw.get("score"), (int, float))
            # NaN != NaN: descarta pontuações inválidas do alinhador.
            and raw["score"] == raw["score"]
        ]
        return sum(scores) / len(scores) if scores else None

    @staticmethod
    def _collect_aligned_words(result: dict) -> list[dict]:
        words: list[dict] = []
        for segment in result.get("segments", []):
            words.extend(segment.get("words", []))
        if not words:
            words = list(result.get("word_segments", []))
        return words

    @staticmethod
    def _map_to_tokens(tokens: list[str], aligned: list[dict]) -> list[Word]:
        """Casa os tokens do roteiro com as palavras alinhadas, em ordem.

        O texto final vem SEMPRE de `tokens` (o roteiro). O alinhamento só
        fornece tempos; palavras sem tempo ficam como None e o Legend Engine
        interpola depois.
        """

        def key(text: str) -> str:
            return strip_accents(normalize_word(text))

        words: list[Word] = []
        j = 0
        for token in tokens:
            match = None
            for look in range(j, min(j + 3, len(aligned))):
                if key(aligned[look].get("word", "")) == key(token):
                    match = aligned[look]
                    j = look + 1
                    break
            if match is None and j < len(aligned) and len(aligned) == len(tokens):
                match = aligned[j]
                j += 1
            words.append(
                Word(
                    text=token,
                    start=match.get("start") if match else None,
                    end=match.get("end") if match else None,
                )
            )
        return words
