# -*- coding: utf-8 -*-
"""Testes das trajetórias dos projetos (aba Trajetórias do painel)."""
import unittest

from painel.trajetorias import (DESCONHECIDA, FAIXAS, FASES, SEM_RELATOR, catalogo, desfecho, dia, faixa_fora, fases,
                                montar, primeiros_autores, trechos)

F = {f: i for i, f in enumerate(FAIXAS)}
FIM = dia("2026-10-03")


def pas(comissao, desde, ate=None, destino="", rotulo="PL 1/2025"):
    return {"comissao": comissao, "rotulo": rotulo, "desde": desde, "ate": ate, "destino": destino}


def enc(data, motivo):
    return {"encerramento": data, "motivo": motivo}


class TestDesfecho(unittest.TestCase):

    def test_agrupa_motivos(self):
        self.assertEqual(desfecho("Encerrado-PROMULGADO"), "Virou norma")
        self.assertEqual(desfecho("Encerrado-VETO PARCIAL ACEITO"), "Virou norma")
        self.assertEqual(desfecho("Encerrado-VETO TOTAL ACEITO"), "Vetado")
        self.assertEqual(desfecho("Encerrado-TERMINO DE LEGISLATURA (ART. 275 REG. INT.)"), "Fim de legislatura")
        self.assertEqual(desfecho("APENSADO"), "Outro encerramento")

    def test_destino_fora_das_faixas_cai_em_outras(self):
        self.assertEqual(faixa_fora("SGP21"), F["SGP21"])
        self.assertEqual(faixa_fora("FIN"), F["FIN"])
        self.assertEqual(faixa_fora("?"), F["OUTRAS"])
        self.assertEqual(faixa_fora("SGP22"), F["OUTRAS"])


class TestTrechos(unittest.TestCase):

    def test_entre_comissoes_fica_na_area_de_destino(self):
        segs, terminal, _ = trechos([pas("CCJ", "2025-03-01T10:00:00", "2025-05-01T10:00:00", "SGP12"),
                                     pas("FIN", "2025-05-10T10:00:00")], None, FIM)
        self.assertEqual([s[0] for s in segs], [F["CCJ"], F["SGP12"], F["FIN"]])
        self.assertEqual(segs[1][1:], [dia("2025-05-01"), dia("2025-05-10")])
        self.assertEqual(segs[2][2], FIM)  # ainda na FIN
        self.assertEqual(terminal, -1)

    def test_envio_direto_nao_cria_trecho_fora(self):
        segs, _, _ = trechos([pas("CCJ", "2025-03-01", "2025-05-01", "FIN"), pas("FIN", "2025-05-03")], None, FIM)
        self.assertEqual([s[0] for s in segs], [F["CCJ"], F["FIN"]])

    def test_desfecho_depois_da_ultima_saida(self):
        segs, terminal, quando = trechos([pas("CCJ", "2025-03-01", "2025-05-01", "SGP21")],
                                         enc("2025-08-01T00:00:00", "Encerrado-PROMULGADO"), FIM)
        self.assertEqual(terminal, F["Virou norma"])
        self.assertEqual(quando, dia("2025-08-01"))
        self.assertEqual(segs[-1], [F["SGP21"], dia("2025-05-01"), dia("2025-08-01")])

    def test_encerramento_anterior_a_saida_e_ignorado(self):
        # arquivado no fim da legislatura, desarquivado e enviado de novo: o encerramento antigo não vale
        segs, terminal, _ = trechos([pas("CCJ", "2025-03-01", "2025-05-01", "SGP21")],
                                    enc("2024-12-20T00:00:00", "Encerrado-TERMINO DE LEGISLATURA"), FIM)
        self.assertEqual(terminal, -1)
        self.assertEqual(segs[-1], [F["SGP21"], dia("2025-05-01"), FIM])

    def test_inicio_desconhecido_comeca_no_feed(self):
        segs, _, _ = trechos([pas("CCJ", None, "2019-02-01", "SGP12")], None, FIM)
        self.assertEqual(segs[0][1], 0)


class TestFases(unittest.TestCase):

    def test_comeca_sem_relator_e_segue_os_passos(self):
        segs = [[F["CCJ"], dia("2025-03-01"), dia("2025-06-01")], [F["SGP21"], dia("2025-06-01"), FIM]]
        passos = {("CCJ", "PL 1/2025"): [("2025-03-05T10:00:00", "etapa_sem_relator"),
                                         ("2025-03-10T10:00:00", "etapa_estudo"),
                                         ("2025-04-01T10:00:00", "etapa_pauta"),
                                         ("2025-04-01T15:00:00", "etapa_votado"),  # mesmo dia: vale o último
                                         ("2026-01-01T10:00:00", "etapa_estudo")]}  # depois da saída: fora
        f = fases("PL 1/2025", segs, passos)
        self.assertEqual(f, [0, dia("2025-03-01"), SEM_RELATOR,
                             0, dia("2025-03-10"), FASES.index("estudo"),
                             0, dia("2025-04-01"), FASES.index("votado")])

    def test_ja_estava_quando_o_feed_comeca(self):
        f = fases("PL 1/2025", [[F["CCJ"], 0, 100]], {})
        self.assertEqual(f, [0, 0, DESCONHECIDA])


class TestMontar(unittest.TestCase):

    def test_colunas_e_ordem(self):
        passagens = [pas("CCJ", "2025-03-01", rotulo="PL 2/2025"), pas("CCJ", "2024-03-01", rotulo="PDL 7/2024"),
                     pas("CCJ", "2024-01-01", rotulo="DOCREC 3/2024")]  # não é projeto: fica de fora
        cat = catalogo([{"rotulo": "PL 2/2025", "materia_id": "10", "ementa": '"Dispõe   sobre X."'}], [])
        autores = primeiros_autores([{"rotulo": "PL 2/2025", "ordem": "1", "autor": "FULANA"}], [], [])
        d = montar(passagens, [], {}, cat, autores, "2026-10-03", "2026-10-03T21:47:00-03:00", {"CCJ": "Justiça"})
        p = d["projetos"]
        self.assertEqual(p["rotulo"], ["PDL 7/2024", "PL 2/2025"])
        self.assertEqual(p["tipo"], [1, 0])
        self.assertEqual(p["id"], [None, 10])
        self.assertEqual(p["ementa"][1], "Dispõe sobre X.")
        self.assertEqual(p["autor"], ["", "FULANA"])
        self.assertEqual(d["fim"], FIM)
        self.assertEqual((d["nomes"]["CCJ"], d["nomes"]["SGP21"]), ("Justiça", ""))


if __name__ == "__main__":
    unittest.main()
