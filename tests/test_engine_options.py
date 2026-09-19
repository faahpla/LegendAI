"""Testes das opções que a interface expõe: limite de caracteres, limpeza do
roteiro e a guarda contra áudio que não corresponde ao texto."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legendai.aligner import AlignmentReport
from legendai.engine import LegendEngine, Word
from legendai.pipeline import AlignmentMismatchError, _verify_alignment
from legendai.settings import DEFAULT_LINKING_WORDS, Settings
from legendai.utils import strip_special_characters


def make_words(spec):
    return [Word(text, start, end) for text, start, end in spec]


def words_from(text, step=0.5):
    """Cria palavras sequenciais a partir de uma frase."""
    spec, t = [], 0.0
    for token in text.split():
        spec.append((token, t, t + step * 0.9))
        t += step
    return spec


class TestWordsPerCue(unittest.TestCase):
    """Palavras por legenda combinadas com o limite de caracteres."""

    def build(self, text, max_words, max_chars):
        settings = Settings()
        settings.max_words = max_words
        settings.max_chars = max_chars
        settings.min_duration = 0.0
        settings.margin_start = settings.margin_end = 0.0
        settings.snap_fps = 0
        cues = LegendEngine(settings).build(make_words(words_from(text)), total_duration=60.0)
        return [cue.text for cue in cues]

    def test_long_word_stays_alone_at_the_char_limit(self):
        # "subordinadas" tem 12 caracteres: ocupa a legenda inteira.
        self.assertEqual(
            self.build("as tropas subordinadas voltaram", max_words=2, max_chars=12),
            ["as tropas", "subordinadas", "voltaram"],
        )

    def test_two_short_words_share_the_cue(self):
        # "as tropas" = 9 caracteres com o espaço, cabe em 12.
        self.assertEqual(
            self.build("as tropas voltaram", max_words=2, max_chars=12),
            ["as tropas", "voltaram"],
        )

    def test_article_is_not_stranded_at_the_end(self):
        # "Quatro dos" cabe em 12 caracteres, mas deixaria "dos" pendurado no
        # fim da legenda, longe do substantivo que ele apresenta.
        self.assertEqual(
            self.build("Quatro dos guardas", max_words=2, max_chars=12),
            ["Quatro", "dos guardas"],
        )

    def test_two_long_words_are_broken_apart(self):
        # "demônios primordiais" = 20 caracteres: não cabe, separa.
        self.assertEqual(
            self.build("demônios primordiais atacaram", max_words=2, max_chars=12),
            ["demônios", "primordiais", "atacaram"],
        )

    def test_word_limit_is_respected_even_when_chars_allow(self):
        # Três palavras curtas caberiam em 20 chars, mas o limite é 2 palavras.
        self.assertEqual(
            self.build("um dois tres", max_words=2, max_chars=20),
            ["um dois", "tres"],
        )

    def test_default_keeps_word_by_word(self):
        self.assertEqual(
            self.build("Ichigo despertou Bankai", max_words=1, max_chars=10),
            ["Ichigo", "despertou", "Bankai"],
        )


class TestLinkingWords(unittest.TestCase):
    """Artigos, preposições e contrações mandam no corte.

    O limite de caracteres dizia sozinho onde quebrar, e quebrava no pior
    lugar possível: "Quatro dos | guardas" deixava o artigo pendurado no fim
    de uma legenda e o substantivo na seguinte. Quem lê recebe primeiro um
    "dos" que não apresenta nada, e só depois descobre o quê.
    """

    def build(self, text, max_words=1, max_chars=20):
        settings = Settings()
        settings.max_words = max_words
        settings.max_chars = max_chars
        settings.min_duration = 0.0
        settings.margin_start = settings.margin_end = 0.0
        settings.snap_fps = 0
        cues = LegendEngine(settings).build(make_words(words_from(text)), total_duration=60.0)
        return [cue.text for cue in cues]

    def test_no_cue_ends_with_a_linking_word(self):
        texto = ("Ichigo despertou o Bankai no meio da batalha "
                 "contra os inimigos do Hueco Mundo")
        for max_words in (1, 2, 3):
            cues = self.build(texto, max_words=max_words, max_chars=14)
            # A última pode terminar em ligação: não existe seguinte para levá-la.
            for cue in cues[:-1]:
                final = cue.split()[-1].casefold()
                self.assertNotIn(
                    final, DEFAULT_LINKING_WORDS,
                    f"com {max_words} palavras, '{cue}' termina em ligação",
                )

    def test_article_travels_to_the_noun_it_introduces(self):
        self.assertEqual(
            self.build("Quatro dos guardas caíram", max_words=2, max_chars=12),
            ["Quatro", "dos guardas", "caíram"],
        )

    def test_two_linking_words_travel_together(self):
        # "para a" é uma unidade só: as duas descem com "praia".
        self.assertEqual(
            self.build("ele vai para a praia", max_words=3, max_chars=20),
            ["ele vai", "para a praia"],
        )

    def test_article_goes_forward_even_when_it_busts_the_limit(self):
        # Recuar caberia em 10 caracteres ("viu o"), avançar não ("o
        # extraordinário", 16). Vale avançar mesmo assim: uma legenda comprida
        # incomoda menos que um artigo órfão.
        self.assertEqual(
            self.build("viu o extraordinário", max_chars=10),
            ["viu", "o extraordinário"],
        )

    def test_contractions_and_accents_are_recognized(self):
        self.assertEqual(self.build("Ichigo está no topo"),
                         ["Ichigo", "está", "no topo"])
        self.assertEqual(self.build("Rukia foi à guerra"),
                         ["Rukia", "foi", "à guerra"])
        self.assertEqual(self.build("Renji passou pelo portão"),
                         ["Renji", "passou", "pelo portão"])

    def test_limits_still_apply_between_ordinary_words(self):
        # A regra nova não afrouxa nada onde não há ligação envolvida.
        self.assertEqual(
            self.build("demônios primordiais atacaram", max_words=2, max_chars=12),
            ["demônios", "primordiais", "atacaram"],
        )


class TestMaxChars(unittest.TestCase):
    """max_chars aparecia na tela de configurações sem efeito nenhum."""

    def build(self, max_chars, spec):
        settings = Settings()
        settings.max_chars = max_chars
        settings.min_duration = 0.0
        settings.margin_start = settings.margin_end = 0.0
        return LegendEngine(settings).build(make_words(spec), total_duration=9.0)

    def test_linking_words_group_when_they_fit(self):
        cues = self.build(20, [("de", 0.0, 0.2), ("Bleach", 0.3, 0.9)])
        self.assertEqual([c.text for c in cues], ["de Bleach"])

    def test_linking_word_leads_the_next_when_limit_is_tight(self):
        # Nenhum par cabe em 6 caracteres, e a preposição ainda assim vai
        # para frente: "de Bleach" só se lê como unidade nessa ordem.
        cues = self.build(6, [
            ("Naruto", 0.0, 0.6), ("de", 0.7, 0.9), ("Bleach", 1.0, 1.6),
        ])
        self.assertEqual([c.text for c in cues], ["Naruto", "de Bleach"])

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


class TestFrameSnapping(unittest.TestCase):
    """Editores por quadro abriam um piscado quando o tempo caía no meio de um."""

    def build(self, fps, spec):
        settings = Settings()
        settings.snap_fps = fps
        return LegendEngine(settings).build(make_words(spec), total_duration=6.0)

    SPEC = [
        ("Hoje", 0.121, 0.601), ("Ichigo", 0.7, 1.207),
        ("despertou", 1.3, 1.99), ("Bankai", 2.1, 2.443),
    ]

    def test_times_land_on_the_frame_grid(self):
        # 25 fps (40 ms) é exato em milissegundos, então a grade fica perfeita.
        for cue in self.build(25.0, self.SPEC):
            self.assertAlmostEqual(cue.start * 25, round(cue.start * 25), places=6)
            self.assertAlmostEqual(cue.end * 25, round(cue.end * 25), places=6)

    def test_cues_stay_contiguous(self):
        cues = self.build(25.0, self.SPEC)
        for previous, cue in zip(cues, cues[1:]):
            self.assertAlmostEqual(previous.end, cue.start, places=6)

    def test_no_cue_collapses_to_zero(self):
        cues = self.build(25.0, self.SPEC)
        for cue in cues:
            self.assertGreater(cue.end, cue.start)

    def test_zero_disables_snapping(self):
        cues = self.build(0.0, self.SPEC)
        off_grid = [c for c in cues if abs(c.start * 25 - round(c.start * 25)) > 1e-6]
        self.assertTrue(off_grid, "sem snap algum tempo deveria cair fora da grade")

    def test_snapping_never_reorders_or_overlaps(self):
        cues = self.build(30.0, self.SPEC)
        for previous, cue in zip(cues, cues[1:]):
            self.assertLessEqual(previous.end, cue.start + 1e-9)


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
