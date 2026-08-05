"""Orquestração do fluxo: MP3 + roteiro -> alinhamento -> regras -> exportação."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .aligner import AlignmentReport, ProgressFn, WhisperXAligner
from .engine import Cue, LegendEngine
from .settings import Settings
from .subtitle import export
from .utils import strip_special_characters

log = logging.getLogger("legendai")


@dataclass
class PipelineResult:
    cues: list[Cue]
    files: list[Path]
    audio_duration: float
    confidence: float | None = None


class AlignmentMismatchError(ValueError):
    """O áudio não corresponde ao roteiro informado."""


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

    if settings.strip_special_chars:
        script = strip_special_characters(script, settings.keep_characters)
        if not script.strip():
            raise ValueError("O roteiro ficou vazio após remover os caracteres especiais.")

    aligner = aligner or WhisperXAligner(language=settings.language)
    log.info("Iniciando alinhamento de %s", audio_path.name)
    report = aligner.align(audio_path, script, progress)
    words, duration = report.words, report.duration

    if settings.check_alignment:
        _verify_alignment(report, settings)

    progress("Aplicando regras do Legend Engine...", 0.75)
    engine = LegendEngine(settings)
    cues = engine.build(words, total_duration=duration)
    log.info("%d palavras -> %d legendas", len(words), len(cues))

    progress("Exportando legendas...", 0.90)
    files = export(cues, audio_path, settings)
    for file in files:
        log.info("Arquivo gerado: %s", file)

    progress("Concluído.", 1.0)
    return PipelineResult(
        cues=cues, files=files, audio_duration=duration, confidence=report.score
    )


def _verify_alignment(report: AlignmentReport, settings: Settings) -> None:
    """Interrompe a geração quando o áudio não corresponde ao roteiro.

    O alinhamento forçado sempre produz tempos — mesmo para um áudio sem
    relação com o texto —, então antes disso a geração seguia até o fim e
    entregava legendas sem sentido. Aqui usamos a confiança média do modelo
    (e, como apoio, a cobertura dos tokens) para recusar o resultado.
    """
    if report.score is None:
        log.info("Alinhamento sem pontuação disponível; verificação ignorada.")
        return

    log.info(
        "Confiança do alinhamento: %.3f (cobertura %.0f%%)",
        report.score, report.coverage * 100,
    )
    if report.score >= settings.min_alignment_score:
        return

    raise AlignmentMismatchError(
        "O áudio não parece corresponder ao roteiro "
        f"(confiança de {report.score:.0%}). Confira se o arquivo de áudio e o "
        "texto são do mesmo vídeo e se o idioma está correto nas configurações."
    )
