# -*- coding: utf-8 -*-
"""
Auditoria dos registros da tramitação nas comissões: aplica as regras de regras.py aos
dados coletados e mantém a lista de suspeitas em suspeitas.csv, numa pasta de saída.

A lista é de uso interno da SGP e fica fora deste repositório, que é público: o
repositório privado da auditoria roda este módulo com --saida apontando para ele.

A lista é cumulativa. Cada suspeita guarda quando apareceu pela primeira vez, quando foi
vista pela última vez e, se deixou de aparecer (a secretaria corrigiu o registro), quando
isso aconteceu. Uma suspeita que a secretaria confirmar como correta entra, à mão, em
descartadas.csv (chave, motivo, data), na mesma pasta, e passa a constar como descartada.

Uso (da raiz do repositório):  python -m auditoria [--saida PASTA]   (padrão: auditoria/saida/)
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from auditoria import regras as R
from coletor import config as C
from coletor.util import gravar_csv, ler_csv, log
from painel import fluxos

SAIDA_PADRAO = C.RAIZ / "auditoria" / "saida"  # fora do git
CAMPOS = ["chave", "regra", "gravidade", "rotulo", "comissao", "data_fato", "descricao", "evidencia",
          "primeira_vez", "ultima_vez", "resolvida_em", "situacao"]
CAMPOS_DESCARTADAS = ["chave", "motivo", "data"]


def chave(s: dict) -> str:
    return "|".join((s["regra"], s["rotulo"], s["comissao"], s["detalhe"]))


def auditar(d: dict, hoje: datetime) -> list[dict]:
    """Todas as suspeitas de hoje. `d` traz as linhas de cada arquivo de dados/."""
    passos = d["passos_reconstrucao"] + d["passos_internos"]
    registros = R.registros_de_envio(d["presencas"], d["historico"])
    apensamentos = R.apensamento_nao_efetivado(d["acervo"], d["relatorias"], passos, hoje)
    return [
        *apensamentos,
        *R.arquivamento_fora_de_fase(d["encerrados"]),
        *R.datas_de_despacho(d["despachos"], d["relatorias"], d["autores"], registros, d["tramitacoes"]),
        *R.datas_de_recebimento(registros),
        *R.pareceres(d["relatorias"]),
        *R.leituras(d["encerrados"], d["autores"]),
        *R.recebida_sem_despacho(d["passagens"], d["despachos"], passos, hoje),
        *R.votado_e_parado(d["acervo"], hoje, {(s["rotulo"], s["comissao"]) for s in apensamentos}),
        *R.em_transito(d["acervo"], hoje),
        *R.tramita_depois_de_encerrada(d["encerrados"], d["passagens"], d["relatorias"]),
    ]


def atualizar(anteriores: list[dict], atuais: list[dict], descartadas: set[str], dia: str) -> list[dict]:
    """Junta as suspeitas de hoje à lista acumulada."""
    linhas = {l["chave"]: dict(l) for l in anteriores}
    vistas = set()
    for s in atuais:
        k = chave(s)
        if k in vistas:
            continue
        vistas.add(k)
        linha = linhas.get(k) or {"chave": k, "primeira_vez": dia}
        linha.update({"regra": s["regra"], "gravidade": R.REGRAS[s["regra"]][0], "rotulo": s["rotulo"],
                      "comissao": s["comissao"], "data_fato": s["data_fato"], "descricao": s["descricao"],
                      "evidencia": s["evidencia"], "ultima_vez": dia, "resolvida_em": ""})
        linhas[k] = linha
    for k, linha in linhas.items():
        if k not in vistas and not linha.get("resolvida_em"):
            linha["resolvida_em"] = dia
        linha["situacao"] = ("descartada" if k in descartadas
                             else "resolvida" if linha["resolvida_em"] else "aberta")
    ordem = {"aberta": 0, "descartada": 1, "resolvida": 2}
    return sorted(linhas.values(), key=lambda l: (ordem[l["situacao"]], l["regra"], l["data_fato"], l["chave"]))


def carregar() -> tuple[dict, datetime, str]:
    coletas = ler_csv(C.ARQ_COLETAS)
    ultima = max(coletas, key=lambda c: c["coletado_em"])
    hoje = datetime.fromisoformat(ultima["coletado_em"]).replace(tzinfo=None)
    rec = C.DIR_DADOS / "reconstrucao"
    tramitacoes = ler_csv(C.ARQ_TRAMITACOES)
    presencas, historico = ler_csv(rec / "presencas.csv"), ler_csv(C.ARQ_HISTORICO)
    dados = {
        "acervo": ler_csv(C.ARQ_ACERVO),
        "autores": ler_csv(C.DIR_DADOS / "autores.csv"),
        "despachos": ler_csv(C.DIR_DADOS / "despachos.csv"),
        "encerrados": ler_csv(C.DIR_DADOS / "encerrados.csv"),
        "relatorias": ler_csv(C.DIR_DADOS / "relatorias.csv"),
        "tramitacoes": tramitacoes,
        "passos_internos": ler_csv(C.ARQ_PASSOS_FEED),
        "passos_reconstrucao": [p for p in ler_csv(rec / "passos_internos.csv") if p["fonte"] == "feed"],
        "presencas": presencas,
        "historico": historico,
        "passagens": fluxos.passagens(presencas, historico, coletas, tramitacoes),
    }
    return dados, hoje, ultima["data"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Suspeitas de erro de registro no SPLEGIS.")
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO,
                    help="pasta de suspeitas.csv e descartadas.csv (padrão: auditoria/saida/)")
    args = ap.parse_args(argv)
    arq_suspeitas, arq_descartadas = args.saida / "suspeitas.csv", args.saida / "descartadas.csv"

    dados, hoje, dia = carregar()
    atuais = auditar(dados, hoje)
    descartadas = {l["chave"] for l in ler_csv(arq_descartadas)}
    linhas = atualizar(ler_csv(arq_suspeitas), atuais, descartadas, dia)
    gravar_csv(arq_suspeitas, CAMPOS, linhas)
    if not arq_descartadas.exists():
        gravar_csv(arq_descartadas, CAMPOS_DESCARTADAS, [])
    situacao = Counter(l["situacao"] for l in linhas)
    log(f"suspeitas.csv: {situacao['aberta']} abertas, {situacao['resolvida']} resolvidas, "
        f"{situacao['descartada']} descartadas")
    for regra, n in sorted(Counter(l["regra"] for l in linhas if l["situacao"] == "aberta").items()):
        log(f"  {regra}: {n}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
