"""Testes da lógica de mesclar/dividir legendas (CaptionMergeSplit) e do parser SRT."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legendai.engine import Cue
from legendai.merge_split import CaptionMergeSplit
from legendai.subtitle import parse_srt
from legendai.utils import srt_time_to_seconds


def cues(*spec):
    """spec: (texto, start, end)."""
    return [Cue(text, start, end) for text, start, end in spec]


class TestJoinTexts(unittest.TestCase):
    def test_simple_join(self):
        self.assertEqual(
            CaptionMergeSplit.join_texts(["eu", "vou", "mostrar"]),
            "eu vou mostrar",
        )

    def test_preserves_punctuation_and_no_space_before(self):
        self.assertEqual(
            CaptionMergeSplit.join_texts(["isso", "é", "verdade."]),
            "isso é verdade.",
        )

    def test_no_space_before_all_marks(self):
        self.assertEqual(
            CaptionMergeSplit.join_texts(["ei", "!", "sério", "?"]),
            "ei! sério?",
        )

    def test_collapses_duplicate_and_newline_whitespace(self):
        self.assertEqual(
            CaptionMergeSplit.join_texts(["olá   mundo", "linha1\nlinha2"]),
            "olá mundo linha1 linha2",
        )

    def test_closing_bracket_has_no_leading_space(self):
        self.assertEqual(
            CaptionMergeSplit.join_texts(["(nota", ")"]),
            "(nota)",
        )


class TestMerge(unittest.TestCase):
    def test_merges_consecutive_and_updates_times(self):
        tool = CaptionMergeSplit(cues(
            ("eu", 1.0, 1.4), ("vou", 1.4, 1.8), ("mostrar", 1.8, 2.3),
        ))
        merged = tool.merge([0, 1, 2])
        self.assertEqual(len(tool.cues), 1)
        self.assertEqual(merged.text, "eu vou mostrar")
        self.assertAlmostEqual(merged.start, 1.0)
        self.assertAlmostEqual(merged.end, 2.3)

    def test_merge_partial_selection_keeps_others(self):
        tool = CaptionMergeSplit(cues(
            ("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5), ("d", 1.5, 2.0),
        ))
        tool.merge([1, 2])
        self.assertEqual([c.text for c in tool.cues], ["a", "b c", "d"])
        self.assertAlmostEqual(tool.cues[1].start, 0.5)
        self.assertAlmostEqual(tool.cues[1].end, 1.5)

    def test_merge_requires_two(self):
        tool = CaptionMergeSplit(cues(("a", 0.0, 0.5)))
        with self.assertRaises(ValueError):
            tool.merge([0])

    def test_merge_rejects_non_consecutive(self):
        tool = CaptionMergeSplit(cues(
            ("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5),
        ))
        with self.assertRaises(ValueError):
            tool.merge([0, 2])

    def test_merge_unordered_indices_are_sorted(self):
        tool = CaptionMergeSplit(cues(
            ("um", 0.0, 0.5), ("dois", 0.5, 1.0),
        ))
        merged = tool.merge([1, 0])
        self.assertEqual(merged.text, "um dois")


class TestSplit(unittest.TestCase):
    def test_split_proportional_to_chars(self):
        tool = CaptionMergeSplit(cues(("eu vou mostrar", 10.0, 12.0)))
        parts = tool.split(0, "eu vou | mostrar")
        self.assertEqual([c.text for c in parts], ["eu vou", "mostrar"])
        # "euvou" = 5 chars, "mostrar" = 7 -> primeira recebe 5/12 de 2 s.
        self.assertAlmostEqual(parts[0].start, 10.0)
        self.assertAlmostEqual(parts[0].end, 10.0 + 2.0 * 5 / 12, places=3)
        self.assertAlmostEqual(parts[1].end, 12.0)

    def test_split_is_contiguous(self):
        tool = CaptionMergeSplit(cues(("um dois tres", 0.0, 3.0)))
        parts = tool.split(0, "um | dois | tres")
        self.assertEqual(len(parts), 3)
        for prev, nxt in zip(parts, parts[1:]):
            self.assertEqual(prev.end, nxt.start)
        self.assertAlmostEqual(parts[0].start, 0.0)
        self.assertAlmostEqual(parts[-1].end, 3.0)

    def test_split_replaces_original_in_list(self):
        tool = CaptionMergeSplit(cues(
            ("antes", 0.0, 1.0), ("eu vou mostrar", 1.0, 3.0), ("depois", 3.0, 4.0),
        ))
        tool.split(1, "eu vou | mostrar")
        self.assertEqual(
            [c.text for c in tool.cues], ["antes", "eu vou", "mostrar", "depois"]
        )

    def test_split_requires_marker(self):
        tool = CaptionMergeSplit(cues(("sem marcador", 0.0, 2.0)))
        with self.assertRaises(ValueError):
            tool.split(0, "sem marcador")

    def test_split_ignores_empty_parts(self):
        tool = CaptionMergeSplit(cues(("eu vou", 0.0, 2.0)))
        # marcadores no início/fim não devem gerar legendas vazias
        with self.assertRaises(ValueError):
            tool.split(0, "| eu vou |")  # apenas uma parte não vazia


class TestSplitAtCursor(unittest.TestCase):
    def test_split_at_cursor_position(self):
        tool = CaptionMergeSplit(cues(("eu vou mostrar", 10.0, 12.0)))
        text = "eu vou mostrar"
        cursor = text.index("mostrar")  # cursor logo antes de "mostrar"
        parts = tool.split_at(0, text, cursor)
        self.assertEqual([c.text for c in parts], ["eu vou", "mostrar"])
        self.assertAlmostEqual(parts[0].start, 10.0)
        self.assertAlmostEqual(parts[1].end, 12.0)

    def test_split_at_matches_marker_timing(self):
        by_cursor = CaptionMergeSplit(cues(("eu vou mostrar", 10.0, 12.0)))
        by_marker = CaptionMergeSplit(cues(("eu vou mostrar", 10.0, 12.0)))
        by_cursor.split_at(0, "eu vou mostrar", len("eu vou "))
        by_marker.split(0, "eu vou | mostrar")
        self.assertEqual(
            [(c.text, c.start, c.end) for c in by_cursor.cues],
            [(c.text, c.start, c.end) for c in by_marker.cues],
        )

    def test_split_at_uses_edited_text(self):
        tool = CaptionMergeSplit(cues(("eu vou mostrer", 0.0, 2.0)))
        fixed = "eu vou mostrar"  # usuário corrigiu o texto no campo
        parts = tool.split_at(0, fixed, len("eu vou "))
        self.assertEqual([c.text for c in parts], ["eu vou", "mostrar"])

    def test_split_at_start_raises(self):
        tool = CaptionMergeSplit(cues(("eu vou", 0.0, 2.0)))
        with self.assertRaises(ValueError):
            tool.split_at(0, "eu vou", 0)

    def test_split_at_end_raises(self):
        tool = CaptionMergeSplit(cues(("eu vou", 0.0, 2.0)))
        with self.assertRaises(ValueError):
            tool.split_at(0, "eu vou", len("eu vou"))


class TestSrtRoundTrip(unittest.TestCase):
    SAMPLE = (
        "﻿1\n00:00:01,000 --> 00:00:01,400\neu\n\n"
        "2\n00:00:01,400 --> 00:00:01,800\nvou\n\n"
        "3\n00:00:01,800 --> 00:00:02,300\nmostrar\n"
    )

    def test_parse_srt(self):
        parsed = parse_srt(self.SAMPLE)
        self.assertEqual([c.text for c in parsed], ["eu", "vou", "mostrar"])
        self.assertAlmostEqual(parsed[0].start, 1.0)
        self.assertAlmostEqual(parsed[2].end, 2.3)

    def test_parse_multiline_text(self):
        parsed = parse_srt("1\n00:00:00,000 --> 00:00:02,000\nlinha um\nlinha dois\n")
        self.assertEqual(parsed[0].text, "linha um\nlinha dois")

    def test_merge_after_parse_produces_expected_srt(self):
        tool = CaptionMergeSplit.from_srt(self.SAMPLE)
        tool.merge([0, 1, 2])
        out = tool.to_srt()
        self.assertIn("00:00:01,000 --> 00:00:02,300\neu vou mostrar", out)

    def test_time_to_seconds_inverse(self):
        self.assertAlmostEqual(srt_time_to_seconds("01:01:01,007"), 3661.007)


if __name__ == "__main__":
    unittest.main(verbosity=2)
