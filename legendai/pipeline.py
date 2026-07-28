"""Orquestração do fluxo: MP3 + roteiro -> alinhamento -> regras -> exportação."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .aligner import ProgressFn, WhisperXAligner
from .engine import Cue, LegendEngine
from .settings import Settings
from .subtitle import export

log = logging.getLogger("legendai")


@dataclass
class PipelineResult:
    cues: list[Cue]
    files: list[Path]
    audio_duration: float


def generate_subtitles(
    audio_path: Path,
    script: str,
    settings: Settings,
    progress: ProgressFn,
    aligner: WhisperXAligner | None = None,
) -> PipelineResult:
    """Executa o fluxo completo e retorna as legendas e arquivos gerados."""
    if not audio_path.exists():
        raise FileNotFoundError(f"Áudio não encontrado: {audio_path}")
    if not script.strip():
        raise ValueError("Cole o roteiro antes de gerar a legenda.")

    aligner = aligner or WhisperXAligner(language=settings.language)
    log.info("Iniciando alinhamento de %s", audio_path.name)
    words, duration = aligner.align(audio_path, script, progress)

    progress("Aplicando regras do Legend Engine...", 0.75)
    engine = LegendEngine(settings)
    cues = engine.build(words, total_duration=duration)
    log.info("%d palavras -> %d legendas", len(words), len(cues))

    progress("Exportando legendas...", 0.90)
    files = export(cues, audio_path, settings)
    for file in files:
        log.info("Arquivo gerado: %s", file)

    progress("Concluído.", 1.0)
    return PipelineResult(cues=cues, files=files, audio_duration=duration)
