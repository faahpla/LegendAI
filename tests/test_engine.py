"""Testes das regras do Legend Engine e da exportação SRT/ASS."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legendai.engine import LegendEngine, Word
from legendai.settings import Settings
from legendai.subtitle import to_ass, to_srt
from legendai.utils import ass_timestamp, srt_timestamp


def make_words(spec):
    """spec: lista de (texto, start, end)."""
    return [Word(text, start, end) for text, start, end in spec]


class TestGrouping(unittest.TestCase):
    def setUp(self):
        self.engine = LegendEngine(Settings())

    def test_word_by_word(self):
        words = make_words([
            ("Ichigo", 0.0, 0.5), ("despertou", 0.6, 1.2),
            ("seu", 1.3, 1.5), ("Bankai", 1.6, 2.2),
        ])
        cues = self.engine.build(words, total_duration=3.0)
        self.assertEqual([c.text for c in cues], ["Ichigo", "despertou", "seu", "Bankai"])

    def test_small_word_groups_with_next(self):
        words = make_words([
            ("de", 0.0, 0.2), ("Bleach", 0.3, 0.9),
            ("e", 1.0, 1.1), ("Naruto", 1.2, 1.9),
        ])
        cues = self.engine.build(words, total_duration=2.5)
        self.assertEqual([c.text for c in cues], ["de Bleach", "e Naruto"])

    def test_small_word_case_insensitive_and_chained(self):
        words = make_words([
            ("E", 0.0, 0.1), ("a", 0.2, 0.3), ("casa", 0.4, 1.0),
        ])
        cues = self.engine.build(words, total_duration=1.5)
        self.assertEqual([c.text for c in cues], ["E a casa"])

    def test_trailing_small_word_attaches_to_previous(self):
        words = make_words([("Fugiu", 0.0, 0.6), ("sem", 0.7, 0.9)])
        cues = self.engine.build(words, total_duration=1.5)
        self.assertEqual([c.text for c in cues], ["Fugiu sem"])

    def test_long_word_stays_alone_and_unbroken(self):
        words = make_words([("automaticamente", 0.0, 1.4)])
        cues = self.engine.build(words, total_duration=2.0)
        self.assertEqual(cues[0].text, "automaticamente")

    def test_script_text_is_never_altered(self):
        words = make_words([("Bankai!", 0.0, 0.6), ("Épico,", 0.7, 1.4)])
        cues = self.engine.build(words, total_duration=2.0)
        self.assertEqual([c.text for c in cues], ["Bankai!", "Épico,"])


class TestTiming(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.engine = LegendEngine(self.settings)

    def test_min_duration_expansion(self):
        words = make_words([
            ("Vai", 0.0, 0.1), ("rápido", 1.0, 1.8),
        ])
        cues = self.engine.build(words, total_duration=3.0)
        for cue in cues:
            self.assertGreaterEqual(cue.duration, self.settings.min_duration - 1e-6)

    def test_min_duration_borrows_from_neighbors(self):
        words = make_words([
            ("um", 0.0, 0.1), ("dois", 0.1, 0.2), ("três", 0.2, 1.9),
        ])
        cues = self.engine.build(words, total_duration=1.9)
        for cue in cues:
            self.assertGreaterEqual(cue.duration, self.settings.min_duration - 1e-6)

    def test_max_duration_cap(self):
        words = make_words([("Silêncio", 0.0, 7.0)])
        cues = self.engine.build(words, total_duration=8.0)
        # O alinhamento à grade de quadros roda por último e arredonda início e
        # fim com a mesma regra (é isso que mantém as legendas encostadas), de
        # modo que o fim pode subir até meio quadro acima do teto.
        tolerance = 0.5 / self.settings.snap_fps if self.settings.snap_fps > 0 else 0.0
        self.assertLessEqual(
            cues[0].duration,
            self.settings.max_duration + self.settings.margin_end + tolerance + 1e-6,
        )

    def test_no_overlap(self):
        words = make_words([
            ("hoje", 0.0, 0.5), ("vamos", 0.4, 0.9), ("falar", 0.8, 1.4),
        ])
        cues = self.engine.build(words, total_duration=2.0)
        for prev, cue in zip(cues, cues[1:]):
            self.assertLessEqual(prev.end, cue.start + 1e-9)

    def test_margins_applied_when_gap_exists(self):
        words = make_words([("Olá", 1.0, 1.6), ("mundo", 3.0, 3.6)])
        cues = self.engine.build(words, total_duration=5.0)
        self.assertLess(cues[0].start, 1.0)
        self.assertGreater(cues[0].end, 1.6)

    def test_missing_timings_are_interpolated(self):
        words = make_words([
            ("ano", 0.0, 0.5), ("2026", None, None), ("fim", 2.0, 2.6),
        ])
        cues = self.engine.build(words, total_duration=3.0)
        self.assertEqual(len(cues), 3)
        self.assertGreater(cues[1].start, 0.0)
        self.assertGreater(cues[1].duration, 0.0)

    def test_all_timings_missing_still_works(self):
        words = make_words([("sem", None, None), ("tempo", None, None)])
        cues = self.engine.build(words, total_duration=2.0)
        self.assertEqual(len(cues), 1)
        self.assertGreaterEqual(cues[0].duration, self.settings.min_duration - 1e-6)

    def test_never_negative_start(self):
        words = make_words([("Já!", 0.0, 0.1)])
        cues = self.engine.build(words, total_duration=1.0)
        self.assertGreaterEqual(cues[0].start, 0.0)

    def test_small_gaps_closed_no_flicker(self):
        # Vãos de ~20-30 ms entre palavras devem sumir (fim = início da próxima).
        words = make_words([
            ("palavra", 0.0, 0.5), ("outra", 0.53, 1.1), ("terceira", 1.13, 1.7),
        ])
        cues = self.engine.build(words, total_duration=2.2)
        for prev, cue in zip(cues, cues[1:]):
            self.assertAlmostEqual(prev.end, cue.start, places=3)

    def test_real_pause_preserved(self):
        # Um silêncio maior que max_gap (0.5 s) NÃO é fechado.
        words = make_words([("antes", 0.0, 0.5), ("depois", 2.0, 2.6)])
        cues = self.engine.build(words, total_duration=3.0)
        self.assertLess(cues[0].end, cues[1].start - 0.4)

    def test_close_gaps_disabled(self):
        settings = Settings()
        settings.close_gaps = False
        engine = LegendEngine(settings)
        words = make_words([("gato", 0.0, 0.5), ("dois", 0.6, 1.1)])
        cues = engine.build(words, total_duration=1.5)
        self.assertGreater(cues[1].start, cues[0].end)


class TestExport(unittest.TestCase):
    def test_srt_format(self):
        from legendai.engine import Cue

        srt = to_srt([Cue("de Bleach", 0.0, 0.62), Cue("e Naruto", 0.65, 1.4)])
        self.assertIn("1\n00:00:00,000 --> 00:00:00,620\nde Bleach", srt)
        self.assertIn("2\n00:00:00,650 --> 00:00:01,400\ne Naruto", srt)

    def test_ass_format(self):
        from legendai.engine import Cue

        ass = to_ass([Cue("Bankai", 1.0, 1.5)])
        self.assertIn("[Script Info]", ass)
        self.assertIn("Dialogue: 0,0:00:01.00,0:00:01.50,LegendAI,,0,0,0,,Bankai", ass)

    def test_timestamps(self):
        self.assertEqual(srt_timestamp(3661.007), "01:01:01,007")
        self.assertEqual(ass_timestamp(61.239), "0:01:01.24")


if __name__ == "__main__":
    unittest.main(verbosity=2)
