"""Legend Engine — motor de regras do LegendAI.

O WhisperX informa apenas (palavra, início, fim). Este módulo decide como
as legendas são montadas. O roteiro é a fonte absoluta da verdade: o texto
exibido vem sempre dos tokens do roteiro, nunca da transcrição.
"""

from __future__ import annotations

from dataclasses import dataclass

from .settings import Settings
from .utils import normalize_word


@dataclass
class Word:
    """Um token do roteiro com a janela de tempo informada pelo alinhador."""

    text: str
    start: float | None = None
    end: float | None = None


@dataclass
class Cue:
    """Uma legenda final: texto exato do roteiro + intervalo de exibição."""

    text: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


class LegendEngine:
    """Aplica as regras 1–10 sobre a lista de palavras alinhadas."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._small = {normalize_word(w) for w in settings.small_words}

    def build(self, words: list[Word], total_duration: float | None = None) -> list[Cue]:
        if not words:
            return []
        words = self._fill_missing_timings(words, total_duration)
        groups = self._group_words(words)
        cues = self._groups_to_cues(groups)
        self._fix_overlaps(cues)
        self._enforce_min_duration(cues, total_duration)
        self._enforce_max_duration(cues)
        self._apply_margins(cues, total_duration)
        self._fix_overlaps(cues)
        self._close_gaps(cues)
        return [Cue(c.text, round(c.start, 3), round(c.end, 3)) for c in cues]

    # ------------------------------------------------------------------
    # Tempos ausentes: interpola proporcionalmente ao tamanho da palavra.
    # ------------------------------------------------------------------
    def _fill_missing_timings(
        self, words: list[Word], total_duration: float | None
    ) -> list[Word]:
        filled = [Word(w.text, w.start, w.end) for w in words]
        known = [i for i, w in enumerate(filled) if w.start is not None and w.end is not None]
        if not known:
            end = total_duration or len(filled) * 0.5
            self._spread(filled, 0, len(filled) - 1, 0.0, end)
            return filled
        first, last = known[0], known[-1]
        if first > 0:
            self._spread(filled, 0, first - 1, 0.0, filled[first].start)
        if last < len(filled) - 1:
            tail_end = total_duration or filled[last].end + 0.5 * (len(filled) - 1 - last)
            self._spread(filled, last + 1, len(filled) - 1, filled[last].end, tail_end)
        for a, b in zip(known, known[1:]):
            if b - a > 1:
                self._spread(filled, a + 1, b - 1, filled[a].end, filled[b].start)
        return filled

    @staticmethod
    def _spread(words: list[Word], lo: int, hi: int, start: float, end: float) -> None:
        span = max(end - start, 0.0)
        weights = [max(len(words[i].text), 1) for i in range(lo, hi + 1)]
        total = sum(weights)
        cursor = start
        for offset, weight in enumerate(weights):
            share = span * weight / total
            word = words[lo + offset]
            word.start, word.end = cursor, cursor + share
            cursor += share

    # ------------------------------------------------------------------
    # Regras 2, 3 e 4: uma palavra por legenda; palavras pequenas nunca
    # ficam sozinhas — agrupam com a seguinte (ou com a anterior no fim).
    # Palavras nunca são quebradas (regra 9); uma palavra maior que o
    # limite de caracteres permanece sozinha (exceção da regra 4).
    # ------------------------------------------------------------------
    def _group_words(self, words: list[Word]) -> list[list[Word]]:
        groups: list[list[Word]] = []
        pending: list[Word] = []
        for word in words:
            if normalize_word(word.text) in self._small:
                pending.append(word)
                continue
            groups.append(pending + [word])
            pending = []
        if pending:
            if groups:
                groups[-1].extend(pending)
            else:
                groups.append(pending)
        return groups

    @staticmethod
    def _groups_to_cues(groups: list[list[Word]]) -> list[Cue]:
        cues = []
        for group in groups:
            text = " ".join(w.text for w in group)
            cues.append(Cue(text, group[0].start or 0.0, group[-1].end or 0.0))
        return cues

    # ------------------------------------------------------------------
    # Regra 7: sem sobreposição.
    # ------------------------------------------------------------------
    @staticmethod
    def _fix_overlaps(cues: list[Cue]) -> None:
        for prev, cue in zip(cues, cues[1:]):
            if cue.start < prev.end:
                cue.start = prev.end
            if cue.end < cue.start:
                cue.end = cue.start

    # ------------------------------------------------------------------
    # Regra 5: duração mínima. Expande para os espaços vazios vizinhos e,
    # se necessário, redistribui milissegundos das legendas vizinhas.
    # ------------------------------------------------------------------
    def _enforce_min_duration(self, cues: list[Cue], total_duration: float | None) -> None:
        minimum = self.settings.min_duration
        for _ in range(3):
            changed = False
            for i, cue in enumerate(cues):
                deficit = minimum - cue.duration
                if deficit <= 1e-9:
                    continue
                deficit -= self._extend_into_gaps(cues, i, deficit, total_duration)
                if deficit > 1e-9:
                    deficit -= self._borrow_from_neighbors(cues, i, deficit, minimum)
                changed = True
            if not changed:
                break

    def _extend_into_gaps(
        self, cues: list[Cue], i: int, deficit: float, total_duration: float | None
    ) -> float:
        cue, gained = cues[i], 0.0
        next_start = cues[i + 1].start if i + 1 < len(cues) else (total_duration or cue.end + deficit)
        room_after = max(next_start - cue.end, 0.0)
        take = min(deficit, room_after)
        cue.end += take
        gained += take
        if gained < deficit:
            prev_end = cues[i - 1].end if i > 0 else 0.0
            room_before = max(cue.start - prev_end, 0.0)
            take = min(deficit - gained, room_before)
            cue.start -= take
            gained += take
        return gained

    @staticmethod
    def _borrow_from_neighbors(cues: list[Cue], i: int, deficit: float, minimum: float) -> float:
        cue, gained = cues[i], 0.0
        if i + 1 < len(cues):
            nxt = cues[i + 1]
            spare = max(nxt.duration - minimum, 0.0)
            take = min(deficit, spare)
            nxt.start += take
            cue.end += take
            gained += take
        if gained < deficit and i > 0:
            prev = cues[i - 1]
            spare = max(prev.duration - minimum, 0.0)
            take = min(deficit - gained, spare)
            prev.end -= take
            cue.start -= take
            gained += take
        return gained

    # ------------------------------------------------------------------
    # Fecha vãos pequenos entre legendas consecutivas estendendo o fim da
    # anterior até o início da próxima. Elimina o "flicker" de 1 frame em
    # editores (DaVinci, Premiere). Pausas maiores que max_gap (silêncios
    # reais da narração) são preservadas.
    # ------------------------------------------------------------------
    def _close_gaps(self, cues: list[Cue]) -> None:
        if not self.settings.close_gaps:
            return
        max_gap = self.settings.max_gap
        for prev, cue in zip(cues, cues[1:]):
            gap = cue.start - prev.end
            if 0.0 < gap <= max_gap:
                prev.end = cue.start

    # ------------------------------------------------------------------
    # Regra 6: duração máxima configurável.
    # ------------------------------------------------------------------
    def _enforce_max_duration(self, cues: list[Cue]) -> None:
        maximum = max(self.settings.max_duration, self.settings.min_duration)
        for cue in cues:
            if cue.duration > maximum:
                cue.end = cue.start + maximum

    # ------------------------------------------------------------------
    # Regra 8: margens de conforto (~+30 ms) quando houver espaço livre.
    # ------------------------------------------------------------------
    def _apply_margins(self, cues: list[Cue], total_duration: float | None) -> None:
        lead, tail = self.settings.margin_start, self.settings.margin_end
        for i, cue in enumerate(cues):
            gap_before = cue.start - (cues[i - 1].end if i > 0 else 0.0)
            cue.start -= min(lead, max(gap_before / 2 if i > 0 else gap_before, 0.0))
            if i + 1 < len(cues):
                gap_after = cues[i + 1].start - cue.end
                cue.end += min(tail, max(gap_after / 2, 0.0))
            else:
                limit = total_duration if total_duration is not None else cue.end + tail
                cue.end = min(cue.end + tail, max(limit, cue.end))
        if cues:
            cues[0].start = max(cues[0].start, 0.0)
