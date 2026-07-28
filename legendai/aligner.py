"""Alinhador temporal baseado em WhisperX (alinhamento forçado).

O WhisperX NÃO transcreve aqui: recebemos o roteiro pronto e usamos apenas
o modelo de alinhamento (wav2vec2) para descobrir início e fim de cada
palavra do roteiro dentro do áudio. O texto retornado é sempre o token
original do roteiro.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .engine import Word
from .utils import normalize_word, prepare_runtime_environment, resource_path, strip_accents

ProgressFn = Callable[[str, float], None]

_SAMPLE_RATE = 16_000


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
        progress("Carregando WhisperX (modelo de alinhamento)...", 0.10)
        prepare_runtime_environment()
        import whisperx

        bundled_model = resource_path("vendor", "models", self.language)
        if (bundled_model / "config.json").exists():
            self._model, self._metadata = whisperx.load_align_model(
                language_code=self.language,
                device=self.device,
                model_name=str(bundled_model),
                model_cache_only=True,
            )
        else:
            self._model, self._metadata = whisperx.load_align_model(
                language_code=self.language, device=self.device
            )

    def align(
        self, audio_path: Path, script: str, progress: ProgressFn
    ) -> tuple[list[Word], float]:
        """Retorna (tokens do roteiro com tempos, duração do áudio em s)."""
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
        return self._map_to_tokens(tokens, aligned), duration

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
