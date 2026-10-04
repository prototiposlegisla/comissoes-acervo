# -*- coding: utf-8 -*-
"""Testes das regras da auditoria e da lista acumulada de suspeitas."""
import unittest
from datetime import datetime

from auditoria import regras as R
from auditoria.__main__ import atualizar, chave

HOJE = datetime(2026, 10, 3, 6, 53)


def regras(saida):
    return [s["regra"] for s in saida]


class TestArquivamento(unittest.TestCase):

    def enc(self, leitura, encerramento, motivo="Encerrado-TERMINO DE LEGISLATURA (ART. 275 REG. INT.)"):
        return {"rotulo": "PL 1/2026", "leitura": leitura, "encerramento": encerramento, "motivo": motivo}

    def test_arquivamento(self):
        saida = R.arquivamento_fora_de_fase([
            self.enc("2026-02-05T00:00:00", "2026-10-01T10:04:00"),   # mesma legislatura
            self.enc("2014-04-11T00:00:00", "2021-10-14T14:39:00"),   # fora do lote
            self.enc("2023-01-27T00:00:00", "2025-01-17T15:56:07"),   # lote de janeiro: normal
            self.enc("2026-02-05T00:00:00", "2026-10-01T10:04:00", "Encerrado-PROMULGADO"),
        ])
        self.assertEqual(regras(saida), ["arquivamento-275-mesma-legislatura", "arquivamento-275-fora-do-lote"])


class TestDatas(unittest.TestCase):

    def test_despachos(self):
        despachos = [{"rotulo": "PL 832/2024", "despacho": "2", "despachado_em": "2024-02-17T15:52:59",
                      "ordem": "1", "comissao": "CCJ"},
                     {"rotulo": "PL 911/2013", "despacho": "2", "despachado_em": "0201-08-01T16:24:00",
                      "ordem": "1", "comissao": "CCJ"},
                     {"rotulo": "PL 1/2016", "despacho": "2", "despachado_em": "2016-02-07T00:00:00",
                      "ordem": "1", "comissao": "EDUC"},
                     {"rotulo": "PL 2/2016", "despacho": "1", "despachado_em": "2016-04-01T00:00:00",
                      "ordem": "1", "comissao": "CCJ"}]
        registros = [{"rotulo": "PL 832/2024", "comissao": "CCJ", "enviado_em": "2025-02-17T15:53:00",
                      "recebido_em": ""}]
        autores = [{"rotulo": "PL 1/2016", "leitura": "2016-04-14T00:00:00"},
                   {"rotulo": "PL 2/2016", "leitura": "2016-04-05T00:00:00"}]  # 4 dias antes: normal
        saida = R.datas_de_despacho(despachos, [], autores, registros, [])
        self.assertEqual(regras(saida), ["despacho-antes-da-leitura", "despacho-com-ano-do-projeto",
                                         "data-impossivel"])
        self.assertEqual(saida[1]["comissao"], "CCJ")

    def test_despacho_depois_do_parecer(self):
        despachos = [{"rotulo": "PL 106/2014", "despacho": "1", "despachado_em": "2015-06-27T00:00:00",
                      "ordem": "1", "comissao": "CCJ"}]
        relatorias = [{"rotulo": "PL 106/2014", "despacho": "1", "parecer": "1461/2014",
                       "parecer_em": "2014-10-29T00:00:00"}]
        self.assertEqual(regras(R.datas_de_despacho(despachos, relatorias, [], [], [])),
                         ["despacho-depois-do-parecer"])

    def test_recebimentos(self):
        def reg(envio, receb):
            return {"rotulo": "PL 1/2020", "comissao": "ADM", "enviado_em": envio, "recebido_em": receb}
        saida = R.datas_de_recebimento([
            reg("1995-11-24T16:10:00", "1996-11-24T17:44:00"),  # ano trocado
            reg("2018-05-07T10:46:00", "2018-09-05T17:10:00"),  # 09/05 virou 05/09
            reg("2020-03-10T10:00:00", "2020-03-09T10:00:00"),  # antes do envio
            reg("2020-03-10T10:00:00", "2020-03-11T10:00:00"),  # normal
            reg("2020-03-10T10:00:00", ""),                     # não recebida
        ])
        self.assertEqual(regras(saida), ["recebimento-um-ano-depois", "recebimento-dia-mes-trocados",
                                         "recebimento-antes-do-envio"])

    def test_registros_sem_repeticao(self):
        p = {"rotulo": "PL 1/2020", "comissao": "ADM", "enviado_em": "2020-01-01T10:00:00",
             "recebido_em": "2020-01-02T10:00:00"}
        self.assertEqual(len(R.registros_de_envio([p, dict(p)], [dict(p)])), 1)

    def test_pareceres(self):
        def rel(rotulo, numero, em):
            return {"rotulo": rotulo, "comissao": "CCJ", "relator": "X", "parecer": numero, "parecer_em": em,
                    "conclusao": "LEGALIDADE"}
        saida = R.pareceres([
            rel("PL 577/2013", "9999/2013", "2013-10-02T00:00:00"),
            rel("PL 650/2013", "572/201", "2014-05-21T00:00:00"),
            rel("PL 495/2015", "1835/2014", "2015-10-07T00:00:00"),
            rel("PL 551/2015", "4/2018", "2017-12-14T00:00:00"),
            rel("PL 1/2014", "1115/2014", ""),
            rel("PL 2/2019", "3129/2019", "2020-02-05T00:00:00"),  # votado no ano seguinte: normal
        ])
        self.assertEqual(regras(saida), ["parecer-numero-invalido", "parecer-numero-invalido",
                                         "parecer-ano-impossivel", "parecer-ano-impossivel", "parecer-sem-data"])

    def test_leituras(self):
        autores = [{"rotulo": "PL 644/2018", "leitura": "2018-12-13T00:00:00"},
                   {"rotulo": "PDL 1/2015", "leitura": "2014-12-16T00:00:00"},   # dezembro: normal
                   {"rotulo": "PDL 76/2015", "leitura": "2013-10-07T00:00:00"}]
        encerrados = [{"rotulo": "PL 644/2018", "leitura": "2010-12-11T00:00:00"},
                      {"rotulo": "PDL 1/2015", "leitura": "2014-12-10T00:00:00"}]  # dias de diferença: normal
        self.assertEqual(regras(R.leituras(encerrados, autores)), ["leitura-divergente", "leitura-antes-do-ano"])


class TestCaminho(unittest.TestCase):

    def test_recebida_sem_despacho(self):
        despachos = [{"rotulo": "PL 327/2020", "despacho": "1", "despachado_em": "", "ordem": str(i), "comissao": c}
                     for i, c in enumerate(["CCJ", "ADM"], 1)]

        def pas(comissao, desde, ate, motivo=""):
            return {"comissao": comissao, "rotulo": "PL 327/2020", "desde": desde, "recebido": None, "ate": ate,
                    "origem": "CCJ", "destino": "ADM", "motivo": motivo}
        passos = [{"comissao": "URB", "rotulo": "PL 327/2020", "data": "2021-05-15T10:00:00", "tipo": "interna"}]
        saida = R.recebida_sem_despacho([
            pas("URB", "2021-05-14T15:25:02", "2021-05-20T12:54:00"),   # 6 dias, com passo
            pas("FIN", "2021-05-14T15:25:02", "2021-05-14T15:40:00"),   # desfeito no mesmo dia
            pas("EDUC", "2021-05-14T15:25:02", "2021-08-14T15:40:00", "Obs: Para exclusão da comissão."),
            pas("ADM", "2021-05-20T12:54:00", None),                    # designada
        ], despachos, passos, HOJE)
        self.assertEqual([(s["regra"], s["comissao"]) for s in saida], [("recebida-sem-despacho", "URB")])

    def test_acervo_de_hoje(self):
        def item(**k):
            base = {"comissao": "CCJ", "rotulo": "PL 1/2025", "interna_data": "", "interna_area": "", "interna_tipo": "",
                    "enviado_por": "SGP22", "enviado_em": "", "recebido_em": "", "relator": ""}
            return {**base, **k}
        acervo = [item(interna_tipo="Deliberado", interna_data="2025-11-05T14:00:00", recebido_em="x"),
                  item(interna_tipo="Deliberado", interna_data="2026-09-20T14:00:00", recebido_em="x"),
                  item(enviado_em="2021-02-24T19:10:00"),
                  item(enviado_em="2026-09-25T19:10:00")]
        self.assertEqual(regras(R.votado_e_parado(acervo, HOJE)), ["votado-e-parado"])
        self.assertEqual(regras(R.em_transito(acervo, HOJE)), ["em-transito"])

    def test_tramita_depois_de_encerrada(self):
        encerrados = [{"rotulo": "PL 36/2015", "encerramento": "2015-05-14T00:00:00", "motivo": "Encerrado-PROMULGADO"},
                      {"rotulo": "PL 108/2013", "encerramento": "2015-06-18T09:29:00", "motivo": "Encerrado-PROMULGADO"},
                      {"rotulo": "PL 602/2018", "encerramento": "2019-04-17T00:00:00", "motivo": "APENSADO"}]
        relatorias = [{"rotulo": "PL 36/2015", "comissao": "FIN", "despacho": "1", "despachado_em": "2015-02-12T00:00:00",
                       "parecer": "840/2015", "parecer_em": "2015-05-20T00:00:00"}]
        passagens = [  # enviado do arquivo por engano e devolvido: já corrigido
            {"comissao": "SAUDE", "rotulo": "PL 108/2013", "desde": "2019-01-24T17:08:00", "ate": "2019-01-28T15:18:00",
             "origem": "ARQUIVO", "destino": "ARQUIVO"},
            {"comissao": "CCJ", "rotulo": "PL 602/2018", "desde": "2019-04-24T13:38:00", "ate": None,
             "origem": "SGP22", "destino": ""}]
        saida = R.tramita_depois_de_encerrada(encerrados, passagens, relatorias)
        self.assertEqual([s["rotulo"] for s in saida], ["PL 36/2015"])


class TestLista(unittest.TestCase):

    def suspeita(self, rotulo):
        return {"regra": "em-transito", "rotulo": rotulo, "comissao": "EDUC", "detalhe": "x", "data_fato": "2021-02-24",
                "descricao": "d", "evidencia": "e"}

    def test_atualizar(self):
        a, b, c = self.suspeita("RDP 1/2021"), self.suspeita("RDP 2/2021"), self.suspeita("RDP 3/2021")
        dia1 = atualizar([], [a, b, c, dict(a)], {chave(c)}, "2026-10-03")
        self.assertEqual(len(dia1), 3)
        self.assertEqual({l["rotulo"]: l["situacao"] for l in dia1},
                         {"RDP 1/2021": "aberta", "RDP 2/2021": "aberta", "RDP 3/2021": "descartada"})
        dia2 = {l["rotulo"]: l for l in atualizar(dia1, [a, c], {chave(c)}, "2026-10-04")}
        self.assertEqual((dia2["RDP 1/2021"]["primeira_vez"], dia2["RDP 1/2021"]["ultima_vez"]),
                         ("2026-10-03", "2026-10-04"))
        self.assertEqual((dia2["RDP 2/2021"]["situacao"], dia2["RDP 2/2021"]["resolvida_em"]),
                         ("resolvida", "2026-10-04"))
        dia3 = {l["rotulo"]: l for l in atualizar(list(dia2.values()), [b], set(), "2026-10-05")}
        self.assertEqual((dia3["RDP 2/2021"]["situacao"], dia3["RDP 2/2021"]["primeira_vez"]), ("aberta", "2026-10-03"))
        self.assertEqual(dia3["RDP 1/2021"]["resolvida_em"], "2026-10-05")


if __name__ == "__main__":
    unittest.main()
