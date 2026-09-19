"""Testes do armazém do modelo de alinhamento.

O que importa aqui não é o download em si — é o que acontece em volta dele:
onde o modelo é procurado, o que é reaproveitado e, principalmente, o que sobra
no disco quando a rede cai no meio. Um modelo pela metade que passa na
verificação da próxima abertura quebraria lá adiante, no alinhamento, longe da
causa.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legendai import model_store


def montar_modelo(pasta: Path, pesos: str = model_store.PESOS_CONVERTIDOS) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "config.json").write_text("{}", encoding="utf-8")
    (pasta / pesos).write_bytes(b"pesos")
    return pasta


class BaseTemporaria(unittest.TestCase):
    def setUp(self):
        temporaria = tempfile.TemporaryDirectory(prefix="legendai-teste-")
        self.addCleanup(temporaria.cleanup)
        self.raiz = Path(temporaria.name)
        self.avisos = []

    def progresso(self, mensagem, fracao):
        self.avisos.append((mensagem, fracao))


class TestModeloInstalado(BaseTemporaria):
    def test_descritor_sozinho_nao_e_modelo(self):
        pasta = self.raiz / "pt"
        pasta.mkdir()
        self.assertFalse(model_store.modelo_instalado(pasta))
        (pasta / "config.json").write_text("{}", encoding="utf-8")
        self.assertFalse(model_store.modelo_instalado(pasta))
        (pasta / model_store.PESOS_CONVERTIDOS).write_bytes(b"x")
        self.assertTrue(model_store.modelo_instalado(pasta))

    def test_pesos_originais_tambem_servem(self):
        # Quem montar uma pasta à mão, ainda em float32, continua atendido.
        pasta = montar_modelo(self.raiz / "pt", model_store.PESOS_ORIGINAIS)
        self.assertTrue(model_store.modelo_instalado(pasta))


class TestOndeProcurar(BaseTemporaria):
    def test_idioma_do_torchaudio_nao_guarda_nada(self):
        with mock.patch.object(model_store, "repositorio", return_value=None):
            self.assertIsNone(model_store.ensure_model("en", self.progresso))

    def test_modelo_embutido_vence(self):
        embutido = montar_modelo(self.raiz / "vendor" / "models" / "pt")
        with mock.patch.object(model_store, "repositorio", return_value="repo/x"),              mock.patch.object(model_store, "resource_path", return_value=embutido),              mock.patch.object(model_store, "_instalar") as instalar:
            self.assertEqual(model_store.ensure_model("pt", self.progresso), embutido)
        instalar.assert_not_called()

    def test_o_que_ja_foi_baixado_nao_baixa_de_novo(self):
        baixado = montar_modelo(self.raiz / "models" / "pt")
        with mock.patch.object(model_store, "repositorio", return_value="repo/x"),              mock.patch.object(model_store, "resource_path", return_value=self.raiz / "ausente"),              mock.patch.object(model_store, "pasta_do_idioma", return_value=baixado),              mock.patch.object(model_store, "_instalar") as instalar:
            self.assertEqual(model_store.ensure_model("pt", self.progresso), baixado)
        instalar.assert_not_called()

    def test_sem_nada_no_disco_instala(self):
        destino = self.raiz / "models" / "pt"
        with mock.patch.object(model_store, "repositorio", return_value="repo/x"),              mock.patch.object(model_store, "resource_path", return_value=self.raiz / "ausente"),              mock.patch.object(model_store, "pasta_do_idioma", return_value=destino),              mock.patch.object(model_store, "_instalar") as instalar:
            self.assertEqual(model_store.ensure_model("pt", self.progresso), destino)
        instalar.assert_called_once()


class TestInstalacao(BaseTemporaria):
    def test_interrupcao_nao_deixa_modelo_pela_metade(self):
        destino = self.raiz / "models" / "pt"

        def baixar(url, arquivo, progresso, faixa):
            arquivo.write_bytes(b"incompleto")
            if arquivo.name == model_store.PESOS_ORIGINAIS:
                raise model_store.ModelDownloadError("a rede caiu")

        with mock.patch.object(model_store, "_baixar", side_effect=baixar):
            with self.assertRaises(model_store.ModelDownloadError):
                model_store._instalar("repo/x", destino, self.progresso)

        self.assertFalse(destino.exists(), "o destino não pode existir pela metade")
        sobras = list((self.raiz / "models").glob("legendai-modelo-*"))
        self.assertEqual(sobras, [], "a pasta temporária deveria ter sido removida")

    def test_so_assume_o_lugar_depois_de_converter(self):
        destino = self.raiz / "models" / "pt"
        ordem = []

        def baixar(url, arquivo, progresso, faixa):
            ordem.append(("baixou", arquivo.name))
            arquivo.write_bytes(b"conteudo")

        def converter(pasta, progresso):
            ordem.append(("converteu", pasta.name))
            self.assertFalse(destino.exists(), "converteu já no lugar definitivo")
            (pasta / model_store.PESOS_CONVERTIDOS).write_bytes(b"meia precisao")
            (pasta / model_store.PESOS_ORIGINAIS).unlink()

        with mock.patch.object(model_store, "_baixar", side_effect=baixar),              mock.patch.object(model_store, "_converter_para_meia_precisao", side_effect=converter),              mock.patch.object(model_store, "_conferir"):
            model_store._instalar("repo/x", destino, self.progresso)

        self.assertTrue(model_store.modelo_instalado(destino))
        self.assertFalse((destino / model_store.PESOS_ORIGINAIS).exists(),
                         "o arquivo em float32 deveria ter sido descartado")
        self.assertEqual(ordem[-1][0], "converteu", "a conversão é o último passo")


    def test_modelo_que_nao_abre_nao_fica_instalado(self):
        """Um modelo quebrado instalado é uma falha sem saída: a verificação de
        arquivos passaria e o download nunca seria refeito."""
        destino = self.raiz / "models" / "pt"

        def baixar(url, arquivo, progresso, faixa):
            arquivo.write_bytes(b"conteudo")

        with mock.patch.object(model_store, "_baixar", side_effect=baixar),              mock.patch.object(model_store, "_converter_para_meia_precisao"),              mock.patch.object(model_store, "_conferir", side_effect=OSError("arquivo truncado")):
            with self.assertRaises(OSError):
                model_store._instalar("repo/x", destino, self.progresso)

        self.assertFalse(destino.exists(), "o modelo que não abre não pode ficar instalado")


class TestDownload(BaseTemporaria):
    def test_grava_em_part_e_so_entao_renomeia(self):
        origem = self.raiz / "origem.bin"
        origem.write_bytes(b"a" * (3 << 20))
        destino = self.raiz / "destino.bin"

        model_store._baixar(origem.as_uri(), destino, self.progresso, (0.0, 1.0))

        self.assertEqual(destino.read_bytes(), b"a" * (3 << 20))
        self.assertFalse(destino.with_name(destino.name + ".part").exists())
        self.assertTrue(self.avisos, "um arquivo grande deveria reportar andamento")
        self.assertTrue(all(0.0 <= fracao <= 1.0 for _, fracao in self.avisos))

    def test_arquivo_pequeno_nao_polui_o_andamento(self):
        origem = self.raiz / "config.json"
        origem.write_bytes(b"{}")
        model_store._baixar(origem.as_uri(), self.raiz / "copia.json", self.progresso, None)
        self.assertEqual(self.avisos, [])

    def test_cancelamento_no_meio_nao_deixa_o_arquivo_final(self):
        class Cancelado(Exception):
            pass

        origem = self.raiz / "origem.bin"
        origem.write_bytes(b"a" * (3 << 20))
        destino = self.raiz / "destino.bin"

        def desistir(mensagem, fracao):
            raise Cancelado()

        with self.assertRaises(Cancelado):
            model_store._baixar(origem.as_uri(), destino, desistir, (0.0, 1.0))
        self.assertFalse(destino.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
