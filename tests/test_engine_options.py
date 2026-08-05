"""Testes das opções que a interface expõe: limite de caracteres, limpeza do
roteiro e a guarda contra áudio que não corresponde ao texto."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legendai.aligner import AlignmentReport
from legendai.engine import LegendEngine, Word
from legendai.pipeline import AlignmentMismatchError, _verify_alignment
from legendai.settings import Settings
from legendai.utils import strip_special_characters


def make_words(spec):
    return [Word(text, start, end) for text, start, end in spec]


class TestMaxChars(unittest.TestCase):
    """max_chars aparecia na tela de configurações sem efeito nenhum."""

    def build(self, max_chars, spec):
        settings = Settings()
        settings.max_chars = max_chars
        settings.min_duration = 0.0
        settings.margin_start = settings.margin_end = 0.0
        return LegendEngine(settings).build(make_words(spec), total_duration=9.0)

    def test_small_words_group_when_they_fit(self):
        cues = self.build(20, [("de", 0.0, 0.2), ("Bleach", 0.3, 0.9)])
        self.assertEqual([c.text for c in cues], ["de Bleach"])

    def test_group_is_split_when_limit_is_tight(self):
        # "de Bleach" tem 9 caracteres; com limite 6 a palavra fica sozinha.
        cues = self.build(6, [
            ("Naruto", 0.0, 0.6), ("de", 0.7, 0.9), ("Bleach", 1.0, 1.6),
        ])
        self.assertEqual([c.text for c in cues], ["Naruto de", "Bleach"])

    def test_no_cue_exceeds_limit_when_possible(self):
        cues = self.build(12, [
            ("um", 0.0, 0.2), ("dois", 0.3, 0.7), ("tres", 0.8, 1.2),
            ("quatro", 1.3, 1.9), ("cinco", 2.0, 2.6),
        ])
        for cue in cues:
            self.assertLessEqual(len(cue.text), 12, cue.text)

    def test_single_long_word_stays_alone(self):
        cues = self.build(5, [("automaticamente", 0.0, 1.4)])
        self.assertEqual([c.text for c in cues], ["automaticamente"])


class TestStripSpecialCharacters(unittest.TestCase):
    def test_keeps_quotes_and_colon_by_default(self):
        self.assertEqual(
            strip_special_characters('Ele disse: "vamos" agora!'),
            'Ele disse: "vamos" agora',
        )

    def test_removes_symbols_and_emoji(self):
        self.assertEqual(
            strip_special_characters("Top #1 @canal ~ 100% 🔥"),
            "Top 1 canal 100",
        )

    def test_preserves_accents_and_digits(self):
        self.assertEqual(
            strip_special_characters("Ação épica 2026 — incrível!"),
            "Ação épica 2026 incrível",
        )

    def test_keep_list_is_configurable(self):
        self.assertEqual(
            strip_special_characters("Oi, tudo bem? Sim.", keep='":,.?'),
            "Oi, tudo bem? Sim.",
        )

    def test_preserves_line_breaks(self):
        self.assertEqual(strip_special_characters("linha um!\nlinha dois?"),
                         "linha um\nlinha dois")


class TestAlignmentGuard(unittest.TestCase):
    def report(self, score, coverage=1.0):
        return AlignmentReport(words=[], duration=1.0, coverage=coverage, score=score)

    def test_good_alignment_passes(self):
        _verify_alignment(self.report(0.82), Settings())  # não levanta

    def test_poor_alignment_is_rejected(self):
        with self.assertRaises(AlignmentMismatchError) as ctx:
            _verify_alignment(self.report(0.04), Settings())
        self.assertIn("não parece corresponder", str(ctx.exception))

    def test_missing_score_skips_the_check(self):
        _verify_alignment(self.report(None), Settings())  # não levanta

    def test_threshold_is_configurable(self):
        settings = Settings()
        settings.min_alignment_score = 0.9
        with self.assertRaises(AlignmentMismatchError):
            _verify_alignment(self.report(0.5), settings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
