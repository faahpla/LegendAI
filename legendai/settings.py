"""Configurações persistentes do LegendAI (JSON em %APPDATA%/LegendAI)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

# Palavras de ligação: artigos, preposições, contrações e as conjunções que
# puxam o que vem depois. São as palavras que não se leem sozinhas — "o" pede
# o substantivo, "de" pede o complemento —, então elas abrem a legenda da
# palavra que introduzem em vez de fechar a anterior.
DEFAULT_LINKING_WORDS = [
    # artigos
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    # preposições
    "de", "em", "por", "com", "sem", "para", "pra", "pro", "pras", "pros",
    "até", "sob", "sobre", "entre", "após", "desde", "contra", "perante",
    # contrações de preposição com artigo
    "do", "da", "dos", "das", "no", "na", "nos", "nas",
    "ao", "aos", "à", "às", "num", "numa", "nuns", "numas",
    "dum", "duma", "duns", "dumas", "pelo", "pela", "pelos", "pelas",
    # conjunções
    "e", "ou",
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
    # Renomeado de `small_words`: a regra deixou de ser o tamanho da palavra e
    # passou a ser a função dela na frase. Um settings.json antigo simplesmente
    # não traz esta chave e recebe a lista nova, que é o desejável.
    linking_words: list[str] = field(default_factory=lambda: list(DEFAULT_LINKING_WORDS))

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
