"""CaptionMergeSplit — lógica de mesclar e dividir legendas (sem interface).

Toda a manipulação opera sobre uma lista de :class:`~legendai.engine.Cue`
(texto + início/fim em segundos). Nenhuma dependência de GUI vive aqui, de
modo que a mesma lógica possa ser testada isoladamente e reaproveitada por
recursos futuros. A ideia é que cada novo recurso entre como um método desta
classe, reutilizando os utilitários puros já existentes
(:meth:`join_texts`, :meth:`distribute`):

    * Smart Merge           — mesclar por heurística (pausas/pontuação)
    * Auto Split            — dividir legendas longas automaticamente
    * Join Small Words      — juntar palavras pequenas órfãs
    * Smart Reflow          — rebalancear quebras de linha
    * Remove Flash Captions — remover legendas curtas demais
    * Balanceamento         — equilibrar duração/caracteres entre legendas

Fluxo típico de uso::

    tool = CaptionMergeSplit.from_srt(Path("legenda.srt").read_text("utf-8-sig"))
    tool.merge([0, 1, 2])                 # mescla as três primeiras
    tool.split(0, "eu vou | mostrar")     # divide a legenda 0 em duas
    Path("legenda.srt").write_text(tool.to_srt(), encoding="utf-8-sig")
"""

from __future__ import annotations

import re

from .engine import Cue
from .subtitle import parse_srt, to_srt

# Pontuação que nunca deve ser precedida por espaço ao concatenar textos.
NO_SPACE_BEFORE = ".,!?:;)]}"
_NO_SPACE_RE = re.compile(r"\s+([" + re.escape(NO_SPACE_BEFORE) + r"])")
_MULTISPACE_RE = re.compile(r"\s+")
_NON_SPACE_RE = re.compile(r"\S")

DEFAULT_SPLIT_MARKER = "|"


class CaptionMergeSplit:
    """Editor não-visual de legendas: mescla e divide sobre ``list[Cue]``."""

    def __init__(self, cues: list[Cue] | None = None) -> None:
        self.cues: list[Cue] = list(cues) if cues else []

    # ------------------------------------------------------------------
    # Entrada / saída
    # ------------------------------------------------------------------
    @classmethod
    def from_srt(cls, content: str) -> "CaptionMergeSplit":
        """Cria a partir do conteúdo textual de um arquivo SRT."""
        return cls(parse_srt(content))

    def to_srt(self) -> str:
        """Serializa o estado atual de volta para SRT."""
        return to_srt(self.cues)

    # ------------------------------------------------------------------
    # MERGE
    # ------------------------------------------------------------------
    def merge(self, indices: list[int]) -> Cue:
        """Mescla duas ou mais legendas *consecutivas* em uma só.

        Mantém o início da primeira e o fim da última, concatena os textos
        (ver :meth:`join_texts`) e substitui as legendas selecionadas pela
        legenda resultante. Devolve a legenda mesclada.

        Levanta ``ValueError`` se houver menos de duas legendas ou se a
        seleção não for contígua.
        """
        ordered = sorted(set(indices))
        if len(ordered) < 2:
            raise ValueError("Selecione duas ou mais legendas para mesclar.")
        if not (0 <= ordered[0] and ordered[-1] < len(self.cues)):
            raise IndexError("Seleção fora do intervalo de legendas.")
        if ordered != list(range(ordered[0], ordered[-1] + 1)):
            raise ValueError("Só é possível mesclar legendas consecutivas.")

        group = [self.cues[i] for i in ordered]
        merged = Cue(
            text=self.join_texts([cue.text for cue in group]),
            start=group[0].start,
            end=group[-1].end,
        )
        self.cues[ordered[0]: ordered[-1] + 1] = [merged]
        return merged

    # ------------------------------------------------------------------
    # SPLIT
    # ------------------------------------------------------------------
    def split_at(self, index: int, text: str, position: int) -> list[Cue]:
        """Divide uma legenda na posição do cursor dentro de ``text``.

        ``position`` é o deslocamento de caractere (0..len) onde o texto deve
        ser cortado — normalmente a posição do cursor no campo de edição, ou
        seja, entre duas palavras. Espaços nas bordas de cada metade são
        removidos. O tempo é repartido como em :meth:`split`.

        Levanta ``ValueError`` se o corte deixar alguma metade vazia (cursor
        no início/fim ou fora de uma fronteira entre palavras).
        """
        pieces = [text[:position], text[position:]]
        return self._split_into(
            index, pieces,
            error="Posicione o cursor entre duas palavras para dividir.",
        )

    def split(
        self, index: int, marked_text: str, marker: str = DEFAULT_SPLIT_MARKER
    ) -> list[Cue]:
        """Divide uma legenda nos pontos marcados por ``marker`` (padrão ``|``).

        ``marked_text`` é o texto da legenda com um ou mais marcadores
        indicando onde quebrar, por exemplo ``"eu vou | mostrar tudo"``. O
        tempo da legenda original é repartido proporcionalmente ao número de
        caracteres (ignorando espaços) de cada parte. Substitui a legenda
        original pelas novas e as devolve.

        Levanta ``ValueError`` se nenhum ponto de quebra válido for informado
        (menos de duas partes não vazias).
        """
        return self._split_into(
            index, marked_text.split(marker),
            error=f"Marque com '{marker}' ao menos um ponto de quebra válido.",
        )

    def _split_into(self, index: int, pieces: list[str], error: str) -> list[Cue]:
        """Núcleo comum das divisões: normaliza, valida e reparte o tempo."""
        if not 0 <= index < len(self.cues):
            raise IndexError("Legenda inexistente.")

        parts = [self.join_texts([piece]) for piece in pieces]
        parts = [part for part in parts if part]
        if len(parts) < 2:
            raise ValueError(error)

        original = self.cues[index]
        new_cues = self.distribute(parts, original.start, original.end)
        self.cues[index: index + 1] = new_cues
        return new_cues

    # ------------------------------------------------------------------
    # Utilitários puros (sem estado) — reaproveitáveis por recursos futuros.
    # ------------------------------------------------------------------
    @staticmethod
    def join_texts(texts: list[str]) -> str:
        """Concatena textos com espaço único, respeitando a pontuação.

        Regras:
          * separa as partes por um único espaço;
          * colapsa espaços duplicados (incluindo quebras de linha internas);
          * remove o espaço imediatamente antes de ``. , ! ? : ; ) ] }``;
          * preserva os espaços corretos depois da pontuação.
        """
        combined = " ".join(text.strip() for text in texts if text and text.strip())
        combined = _MULTISPACE_RE.sub(" ", combined)
        combined = _NO_SPACE_RE.sub(r"\1", combined)
        return combined.strip()

    @staticmethod
    def distribute(parts: list[str], start: float, end: float) -> list[Cue]:
        """Reparte o intervalo ``[start, end]`` entre ``parts``.

        A duração de cada parte é proporcional ao seu número de caracteres
        que não são espaço. As legendas resultantes são contíguas (o fim de
        uma é exatamente o início da próxima) e a última termina em ``end``.
        """
        weights = [max(len(_NON_SPACE_RE.findall(part)), 1) for part in parts]
        total = sum(weights)
        span = max(end - start, 0.0)

        cues: list[Cue] = []
        cursor = round(start, 3)
        for position, (part, weight) in enumerate(zip(parts, weights)):
            if position == len(parts) - 1:
                cue_end = round(end, 3)
            else:
                cue_end = round(cursor + span * weight / total, 3)
            cues.append(Cue(part, cursor, cue_end))
            cursor = cue_end
        return cues
