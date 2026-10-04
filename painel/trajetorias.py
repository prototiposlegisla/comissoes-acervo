# -*- coding: utf-8 -*-
"""
Trajetória de cada projeto pelas comissões, para a aba Trajetórias do painel.

Cada projeto (PL, PDL, PR e PLO) que passou por alguma comissão desde o início do feed vira
uma sequência de trechos, cada um numa faixa e num intervalo de dias:

- nas comissões, as passagens de fluxos.py;
- fora delas, a área para onde o projeto foi enviado ao sair de uma comissão (SGP12, SGP21,
  SGP23, Arquivo ou outras), até chegar à comissão seguinte, até o encerramento ou até hoje.
  É o último envio conhecido: o que acontece dentro dessas áreas não aparece;
- no fim, o desfecho do cadastro de encerrados (dados/encerrados.csv), quando há.

Dentro de cada trecho numa comissão, a fase vem do último passo interno, agrupado nas
etapas do painel (reconstrucao/serie.py): o trecho começa sem relator (ainda sem passo),
ou em fase desconhecida se o projeto já estava lá quando o feed começa.

O arquivo do painel (trajetorias.json) traz os projetos em colunas, ordenados pela chegada
à primeira comissão, com os dias contados desde o início do feed e as faixas e fases como
índices de listas.
"""
from __future__ import annotations

import re
from datetime import date

from painel.fluxos import INICIO_FEED
from reconstrucao.serie import ETAPAS, PROJETOS

TIPOS = ["PL", "PDL", "PR", "PLO"]
COMISSOES = ["CCJ", "ADM", "URB", "ECON", "EDUC", "SAUDE", "FIN"]  # ordem do processo: CCJ, mérito, FIN
FORA = ["SGP12", "SGP21", "SGP23", "ARQUIVO", "OUTRAS"]
DESFECHOS = ["Virou norma", "Vetado", "Retirado", "Ilegalidade", "Fim de legislatura", "Outro encerramento"]
FAIXAS = COMISSOES + FORA + DESFECHOS
_FAIXA = {f: i for i, f in enumerate(FAIXAS)}
FASES = [e.removeprefix("etapa_") for e in ETAPAS] + ["desconhecida"]
SEM_RELATOR, DESCONHECIDA = FASES.index("sem_relator"), len(FASES) - 1
EMENTA_MAX = 220


def dia(v: str | None) -> int | None:
    """Dias desde o início do feed (None = data desconhecida)."""
    return None if not v else (date.fromisoformat(v[:10]) - INICIO_FEED).days


def faixa_fora(area: str) -> int:
    """Faixa da área para onde o projeto foi enviado ao sair de uma comissão."""
    if area in COMISSOES or area in FORA:
        return _FAIXA[area]
    return _FAIXA["OUTRAS"]  # inclui o destino desconhecido ("?")


def desfecho(motivo: str) -> str:
    """Agrupa o motivo do encerramento ("Encerrado-PROMULGADO", "Encerrado-VETO TOTAL ACEITO"...)."""
    m = motivo.upper()
    if "PROMULGADO" in m or "VETO PARCIAL" in m:
        return "Virou norma"
    if "VETO TOTAL" in m:
        return "Vetado"
    if "RETIRADO" in m:
        return "Retirado"
    if "ILEGALIDADE" in m:
        return "Ilegalidade"
    if "TERMINO DE LEGISLATURA" in m:
        return "Fim de legislatura"
    return "Outro encerramento"


def trechos(passagens: list[dict], encerramento: dict | None, fim: int) -> tuple[list[list[int]], int, int | None]:
    """([[faixa, dia0, dia1], ...], faixa do desfecho ou -1, dia do desfecho) das passagens de
    um projeto. O encerramento só vale se não for anterior à última saída (os anteriores são
    de um arquivamento que foi desfeito)."""
    ps = sorted(passagens, key=lambda p: (p["desde"] or "", p["ate"] or "9"))
    segs: list[list[int]] = []
    cursor = 0
    for k, p in enumerate(ps):
        d0 = max(dia(p["desde"]) if p["desde"] else 0, cursor)
        d1 = max(dia(p["ate"]) if p["ate"] else fim, d0)
        segs.append([_FAIXA[p["comissao"]], d0, d1])
        cursor = d1
        if p["ate"] is None:  # ainda na comissão
            break
        if k + 1 < len(ps):
            prox = ps[k + 1]
            chegada = dia(prox["desde"]) if prox["desde"] else d1
            if chegada > d1 and prox["comissao"] != p["destino"]:
                segs.append([faixa_fora(p["destino"]), d1, chegada])
                cursor = chegada
    terminal, dia_terminal = -1, None
    aberta = ps[-1]["ate"] is None
    if not aberta:
        ultimo = segs[-1][2]
        de = dia(encerramento["encerramento"]) if encerramento else None
        if de is not None and de >= ultimo - 1:
            terminal, dia_terminal = _FAIXA[desfecho(encerramento["motivo"])], max(de, ultimo)
            if ps[-1]["destino"] and dia_terminal > ultimo:
                segs.append([faixa_fora(ps[-1]["destino"]), ultimo, dia_terminal])
        else:  # saiu das comissões e não tem desfecho: fica onde foi até hoje
            segs.append([faixa_fora(ps[-1]["destino"]), ultimo, fim])
    juntos: list[list[int]] = []  # trechos seguidos na mesma faixa viram um só
    for s in segs:
        if juntos and juntos[-1][0] == s[0] and juntos[-1][2] >= s[1]:
            juntos[-1][2] = max(juntos[-1][2], s[2])
        else:
            juntos.append(s)
    return juntos, terminal, dia_terminal


def fases(rotulo: str, segs: list[list[int]], passos: dict) -> list[int]:
    """Mudanças de fase nos trechos em comissões: [trecho, dia, fase, ...]. `passos` é o de
    etapas.passos_por_materia: {(comissão, rótulo): [(data, etapa ou None)]}."""
    saida: list[int] = []
    for k, (faixa, d0, d1) in enumerate(segs):
        if faixa >= len(COMISSOES):
            continue
        muda = [[d0, DESCONHECIDA if d0 == 0 else SEM_RELATOR]]
        for data, etapa in passos.get((COMISSOES[faixa], rotulo), []):
            d = dia(data)
            if d is None or d < d0 or d > d1:
                continue
            f = ETAPAS.index(etapa) if etapa else DESCONHECIDA
            if muda[-1][0] == d:  # vários passos no mesmo dia: vale o último
                muda[-1][1] = f
            else:
                muda.append([d, f])
        anterior = None
        for d, f in muda:
            if f != anterior:
                saida += [k, d, f]
                anterior = f
    return saida


def catalogo(reconstruidas: list[dict], coletadas: list[dict]) -> dict[str, tuple[str, str]]:
    """{rótulo: (materia_id, ementa)}; o catálogo da coleta diária prevalece."""
    saida = {}
    for m in [*reconstruidas, *coletadas]:
        ementa = re.sub(r"\s+", " ", m["ementa"].strip().strip('"')).strip()
        antes = saida.get(m["rotulo"], ("", ""))
        saida[m["rotulo"]] = (m["materia_id"] or antes[0], ementa or antes[1])
    return saida


def primeiros_autores(reconstruidas: list[dict], coletadas: list[dict], materias: list[dict]) -> dict[str, str]:
    """{rótulo: primeiro autor}; o relatório da coleta diária prevalece (como em composicao.py)."""
    rotulos = {m["materia_id"]: m["rotulo"] for m in materias}
    saida: dict[str, str] = {}
    for a in sorted(reconstruidas, key=lambda a: int(a["ordem"] or 0)):
        saida.setdefault(a["rotulo"], a["autor"])
    do_relatorio: dict[str, str] = {}
    for a in sorted(coletadas, key=lambda a: int(a["ordem"] or 0)):
        if rotulo := rotulos.get(a["materia_id"]):
            do_relatorio.setdefault(rotulo, a["autor"])
    saida.update(do_relatorio)
    return saida


def montar(passagens: list[dict], encerrados: list[dict], passos: dict, catalogo_: dict[str, tuple[str, str]],
           autores: dict[str, str], fim: str, atualizado_em: str, nomes_areas: dict[str, str] | None = None) -> dict:
    """As trajetórias em colunas, para o painel. `nomes_areas` dá o nome por extenso das faixas
    que são áreas da Câmara (dados/areas.csv)."""
    fim_dia = dia(fim)
    enc = {e["rotulo"]: e for e in encerrados}
    por: dict[str, list[dict]] = {}
    for p in passagens:
        if p["rotulo"].split()[0] in PROJETOS:
            por.setdefault(p["rotulo"], []).append(p)
    linhas = []
    for rotulo, ps in por.items():
        segs, terminal, dia_terminal = trechos(ps, enc.get(rotulo), fim_dia)
        tipo, resto = rotulo.split()
        materia_id, ementa = catalogo_.get(rotulo, ("", ""))
        linhas.append({
            "rotulo": rotulo, "tipo": TIPOS.index(tipo), "ano": int(resto.rsplit("/", 1)[1]),
            "trechos": [v for s in segs for v in s], "desfecho": terminal, "dia_desfecho": dia_terminal,
            "fases": fases(rotulo, segs, passos),
            "id": int(materia_id) if materia_id.isdigit() else None,
            "ementa": ementa[:EMENTA_MAX], "autor": autores.get(rotulo, ""),
        })
    linhas.sort(key=lambda x: (x["trechos"][1], x["ano"], x["rotulo"]))
    return {
        "inicio": INICIO_FEED.isoformat(), "fim": fim_dia, "atualizado_em": atualizado_em,
        "faixas": FAIXAS, "nomes": {f: (nomes_areas or {}).get(f, "") for f in COMISSOES + FORA},
        "n_comissoes": len(COMISSOES), "n_fora": len(FORA), "tipos": TIPOS, "fases": FASES,
        "projetos": {k: [x[k] for x in linhas] for k in
                     ("rotulo", "tipo", "ano", "trechos", "desfecho", "dia_desfecho", "fases", "id", "ementa", "autor")},
    }
