"""Exportação de legendas em SRT e ASS (UTF-8).

Compatível com DaVinci Resolve, Premiere e CapCut. O texto das legendas
nunca é alterado aqui — apenas formatado no contêiner do arquivo.
"""

from __future__ import annotations

import re
from pathlib import Path

from .engine import Cue
from .settings import Settings
from .utils import ass_timestamp, srt_time_to_seconds, srt_timestamp

ASS_HEADER = """[Script Info]
; Gerado por LegendAI
Title: LegendAI
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: LegendAI,Arial,110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,8,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def parse_srt(content: str) -> list[Cue]:
    """Lê um SRT em texto e devolve a lista de :class:`Cue`.

    Tolerante: ignora o BOM, aceita CRLF/CR, linha de índice opcional antes
    do tempo, espaços extras ao redor de ``-->`` e texto em múltiplas linhas
    (as quebras internas são preservadas no ``Cue.text``). Blocos sem uma
    linha de tempo válida são descartados.
    """
    normalized = content.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n", normalized.strip())
    cues: list[Cue] = []
    for block in blocks:
        lines = block.split("\n")
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        start_stamp, _, end_stamp = lines[time_index].partition("-->")
        try:
            start = srt_time_to_seconds(start_stamp)
            end = srt_time_to_seconds(end_stamp)
        except ValueError:
            continue
        text = "\n".join(lines[time_index + 1:]).strip()
        cues.append(Cue(text, start, end))
    return cues


def to_srt(cues: list[Cue]) -> str:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n"
            f"{srt_timestamp(cue.start)} --> {srt_timestamp(cue.end)}\n"
            f"{cue.text}\n"
        )
    return "\n".join(blocks) + "\n"


def to_ass(cues: list[Cue]) -> str:
    lines = [ASS_HEADER]
    for cue in cues:
        text = cue.text.replace("{", "(").replace("}", ")")
        lines.append(
            f"Dialogue: 0,{ass_timestamp(cue.start)},{ass_timestamp(cue.end)},"
            f"LegendAI,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def export(cues: list[Cue], audio_path: Path, settings: Settings) -> list[Path]:
    """Grava os arquivos ao lado do áudio, com o mesmo nome-base."""
    written: list[Path] = []
    base = audio_path.with_suffix("")
    if settings.export_srt:
        srt_path = base.with_suffix(".srt")
        srt_path.write_text(to_srt(cues), encoding="utf-8-sig")
        written.append(srt_path)
    if settings.export_ass:
        ass_path = base.with_suffix(".ass")
        ass_path.write_text(to_ass(cues), encoding="utf-8-sig")
        written.append(ass_path)
    return written
