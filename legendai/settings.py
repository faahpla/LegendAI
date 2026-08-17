"""Configurações persistentes do LegendAI (JSON em %APPDATA%/LegendAI)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DEFAULT_SMALL_WORDS = [
    "a", "à", "o", "os", "as", "e", "ou",
    "de", "da", "do", "das", "dos",
    "em", "no", "na", "nos", "nas",
    "um", "uma", "uns", "umas",
    "pro", "pra", "com", "por", "sem",
]


def _config_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "LegendAI"


@dataclass
class Settings:
    """Parâmetros do Legend Engine e da exportação."""

    min_duration: float = 0.45
    max_duration: float = 2.0
    max_chars: int = 10
    # Quantas palavras podem dividir a mesma legenda, desde que caibam em
    # max_chars. 1 mantém o estilo palavra-a-palavra (palavras pequenas ainda
    # se juntam à vizinha, porque nunca ficam sozinhas).
    max_words: int = 1
    margin_start: float = 0.030
    margin_end: float = 0.030
    close_gaps: bool = True
    max_gap: float = 0.5
    # Alinha os tempos à grade de quadros do projeto. Editores baseados em
    # quadro (CapCut) arredondam cada tempo por conta própria e podem separar
    # o fim de uma legenda do início da seguinte, criando um piscado de um
    # quadro. Com os tempos já sobre a grade, não há o que arredondar.
    # 0 desliga o alinhamento.
    snap_fps: float = 30.0
    export_srt: bool = True
    export_ass: bool = True
    open_folder: bool = True
    language: str = "pt"
    shortcut_merge: str = "Ctrl+Shift+M"
    shortcut_split: str = "Ctrl+Shift+S"
    # Limpeza opcional do roteiro: remove tudo que não for letra, dígito ou
    # espaço, preservando os caracteres listados em `keep_characters`.
    strip_special_chars: bool = False
    keep_characters: str = '":'
    # Guarda contra áudio que não corresponde ao roteiro: se a confiança do
    # alinhamento ficar abaixo do limite, a geração falha avisando o usuário.
    check_alignment: bool = True
    min_alignment_score: float = 0.35
    small_words: list[str] = field(default_factory=lambda: list(DEFAULT_SMALL_WORDS))

    @property
    def path(self) -> Path:
        return _config_dir() / "settings.json"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(asdict(self), ensure_ascii=False, indent=2)
        self.path.write_text(data, encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        settings = cls()
        try:
            raw = json.loads(settings.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return settings
        known = {f.name for f in fields(cls)}
        for key, value in raw.items():
            if key in known:
                setattr(settings, key, value)
        return settings
