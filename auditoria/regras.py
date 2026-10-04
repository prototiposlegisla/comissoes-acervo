# -*- coding: utf-8 -*-
"""
Regras da auditoria: cada função recebe linhas dos CSVs de dados/ e devolve suspeitas de
erro de registro no SPLEGIS.

Uma suspeita é um dicionário com:
  regra      identificador da regra (ver REGRAS)
  rotulo     matéria ("PL 69/2026")
  comissao   comissão envolvida, quando houver
  detalhe    o que distingue duas suspeitas da mesma regra na mesma matéria e comissão
             (o número do despacho, por exemplo); entra na chave, então não pode mudar de
             um dia para o outro
  data_fato  quando aconteceu o registro suspeito (AAAA-MM-DD)
  descricao  o problema, em uma frase
  evidencia  os valores que mostram o problema, com a fonte de cada um

As regras só apontam o que outra informação contradiz. O que a secretaria confirmar como
correto vai para descartadas.csv (ver __main__.py).
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta

COMISSOES = {"ADM", "CCJ", "ECON", "EDUC", "FIN", "SAUDE", "URB"}
PROJETOS = {"PL", "PDL", "PR", "PLO"}
INICIO_FEED = "2018-11-01"  # antes disso, as passagens pelas comissões estão incompletas

# Regra -> (gravidade, o que ela procura). Alta: o próprio sistema desmente o registro.
# Média: registro muito improvável, que pede conferência.
REGRAS = {
    "arquivamento-275-mesma-legislatura": (
        "alta", "Arquivado por término de legislatura (art. 275) na mesma legislatura em que foi lido."),
    "arquivamento-275-fora-do-lote": (
        "media", "Arquivado por término de legislatura fora do início da legislatura."),
    "despacho-com-ano-do-projeto": (
        "alta", "Despacho datado exatamente um ano antes do envio real à comissão."),
    "data-impossivel": ("alta", "Data com ano anterior a 1980 ou no futuro."),
    "despacho-antes-da-leitura": ("media", "Despacho datado mais de 30 dias antes da leitura do projeto."),
    "despacho-depois-do-parecer": ("media", "Despacho datado depois do parecer que ele originou."),
    "recebimento-antes-do-envio": ("alta", "Recebimento datado antes do envio."),
    "recebimento-um-ano-depois": (
        "media", "Recebimento no mesmo dia e mês do envio, um ano depois (ano trocado?)."),
    "recebimento-dia-mes-trocados": (
        "media", "Recebimento que só faz sentido com o dia e o mês trocados."),
    "parecer-numero-invalido": ("alta", "Número de parecer fora do formato ou de enchimento."),
    "parecer-ano-impossivel": ("alta", "Ano do número do parecer incompatível com o projeto ou com a data."),
    "parecer-sem-data": ("media", "Parecer numerado sem data."),
    "leitura-divergente": ("media", "Data de leitura diferente em dois serviços do SPLEGIS."),
    "leitura-antes-do-ano": ("media", "Leitura muito anterior ao ano do número do projeto."),
    "recebida-sem-despacho": ("alta", "Comissão recebeu e manteve a matéria sem ter sido despachada a ela."),
    "votado-e-parado": ("media", "Matéria votada na comissão e não enviada adiante há mais de 30 dias."),
    "em-transito": ("media", "Matéria enviada à comissão e não recebida há mais de 30 dias."),
    "tramita-depois-de-encerrada": ("alta", "Matéria encerrada com tramitação posterior ao encerramento."),
}

PASSOS_POS_VOTO = {"Deliberado", "Assinar Certidão de Votação", "Publicar Parecer",
                   "Aguardando Publicação do Parecer", "Assinar Parecer"}
LIMITE_DIAS = 30  # cerca de 95% dos casos levam menos que isso (feed de 2018 a 2026)
ANO_MINIMO = 1980
LIMITE_LEITURA = 180  # diferença normal entre as datas de leitura de dois serviços: até ~4 meses
_RX_PARECER = re.compile(r"^(\d{1,4})/(\d{4})$")


# ----------------------------------------------------------------------------- utilidades
def _dt(v: str | None) -> datetime | None:
    if not v or v == "?":
        return None
    try:
        return datetime.fromisoformat(v[:19])
    except ValueError:
        return None


def _br(d: datetime | date | None, hora: bool = False) -> str:
    if d is None:
        return "?"
    return d.strftime("%d/%m/%Y %H:%M" if hora and isinstance(d, datetime) else "%d/%m/%Y")


def _ano(rotulo: str) -> int:
    return int(rotulo.rsplit("/", 1)[1])


def _tipo(rotulo: str) -> str:
    return rotulo.split()[0]


def legislatura(ano: int) -> int:
    """Legislaturas de 4 anos que começam em 2013, 2017, 2021, 2025..."""
    return (ano - 1) // 4


def _suspeita(regra: str, rotulo: str, comissao: str, detalhe: str, data_fato, descricao: str,
              evidencia: str) -> dict:
    data = data_fato.date() if isinstance(data_fato, datetime) else data_fato
    return {"regra": regra, "rotulo": rotulo, "comissao": comissao, "detalhe": detalhe,
            "data_fato": data.isoformat() if data else "", "descricao": descricao, "evidencia": evidencia}


def _leituras(autores: list[dict]) -> dict[str, datetime]:
    leit = {}
    for a in autores:
        d = _dt(a["leitura"])
        if d and (a["rotulo"] not in leit or d < leit[a["rotulo"]]):
            leit[a["rotulo"]] = d
    return leit


def _despachos(despachos: list[dict]) -> dict[tuple, dict]:
    """(rotulo, despacho) -> {"em": data, "comissoes": [...]}"""
    saida: dict[tuple, dict] = {}
    for d in despachos:
        item = saida.setdefault((d["rotulo"], d["despacho"]), {"em": _dt(d["despachado_em"]), "comissoes": []})
        item["comissoes"].append(d["comissao"])
    return saida


# ----------------------------------------------------------------------------- 1. arquivamento
def arquivamento_fora_de_fase(encerrados: list[dict]) -> list[dict]:
    """O art. 275 arquiva, no início de cada legislatura, o que sobrou da anterior. Arquivar
    por ele um projeto lido na legislatura corrente (inclusive já aprovado) é erro de motivo;
    arquivar fora dos primeiros meses da legislatura é aplicação tardia ou avulsa."""
    saida = []
    for e in encerrados:
        if "TERMINO DE LEGISLATURA" not in e["motivo"].upper():
            continue
        enc, leit = _dt(e["encerramento"]), _dt(e["leitura"])
        if enc is None:
            continue
        ev = f"encerrados: lido em {_br(leit)}, encerrado em {_br(enc, True)} com \"{e['motivo']}\""
        if leit and legislatura(leit.year) == legislatura(enc.year):
            saida.append(_suspeita(
                "arquivamento-275-mesma-legislatura", e["rotulo"], "", "", enc,
                f"Arquivado por término de legislatura em {_br(enc)}, na mesma legislatura em que foi lido.", ev))
        elif not (enc.year % 4 == 1 and enc.month <= 3):
            saida.append(_suspeita(
                "arquivamento-275-fora-do-lote", e["rotulo"], "", "", enc,
                f"Arquivado por término de legislatura em {_br(enc)}, fora do início da legislatura.", ev))
    return saida


# ----------------------------------------------------------------------------- 2. datas
def registros_de_envio(presencas: list[dict], historico: list[dict]) -> list[dict]:
    """Envio e recebimento de cada passagem como o SPLEGIS os registra (presenças da
    reconstrução e estados do retrato diário), sem repetição: rotulo, comissao, enviado_em,
    recebido_em."""
    vistos, saida = set(), []
    for l in [*presencas, *historico]:
        k = (l["rotulo"], l["comissao"], l["enviado_em"], l["recebido_em"])
        if k not in vistos and l["enviado_em"] not in ("", "?"):
            vistos.add(k)
            saida.append({"rotulo": k[0], "comissao": k[1], "enviado_em": k[2], "recebido_em": k[3]})
    return saida


def datas_de_despacho(despachos: list[dict], relatorias: list[dict], autores: list[dict],
                      registros: list[dict], tramitacoes: list[dict]) -> list[dict]:
    """Despachos com o ano do projeto no lugar do ano corrente, anteriores à leitura ou
    posteriores ao próprio parecer. `registros` vem de registros_de_envio."""
    envios: dict[tuple, list[datetime]] = defaultdict(list)  # (rotulo, comissão) -> envios a ela
    for p in registros:
        if d := _dt(p["enviado_em"]):
            envios[(p["rotulo"], p["comissao"])].append(d)
    for t in tramitacoes:
        if t["tipo"] == "envio" and (d := _dt(t["data"])):
            envios[(t["rotulo"], t["para"])].append(d)
    pareceres: dict[tuple, list[datetime]] = defaultdict(list)
    for r in relatorias:
        if r["parecer"] and (d := _dt(r["parecer_em"])):
            pareceres[(r["rotulo"], r["despacho"])].append(d)
    leit = _leituras(autores)

    saida = []
    for (rotulo, n), desp in sorted(_despachos(despachos).items()):
        em = desp["em"]
        if em is None:
            continue
        um_ano = em.replace(year=em.year + 1) if not (em.month == 2 and em.day == 29) else None
        achado = None
        if um_ano:
            for c in desp["comissoes"]:
                perto = [d for d in envios.get((rotulo, c), []) if abs((d - um_ano).total_seconds()) <= 300]
                if perto:
                    achado = (c, perto[0])
                    break
        if achado:
            c, real = achado
            saida.append(_suspeita(
                "despacho-com-ano-do-projeto", rotulo, c, f"despacho {n}", em,
                f"Despacho {n} registrado em {_br(em, True)}, mas o envio à {c} foi em {_br(real, True)}.",
                f"despachos: despacho {n} em {_br(em, True)}; tramitação: envio à {c} em {_br(real, True)}"))
            continue
        if em.year < ANO_MINIMO:
            saida.append(_suspeita(
                "data-impossivel", rotulo, "", f"despacho {n}", em,
                f"Despacho {n} registrado com a data {_br(em)}.", f"despachos: despacho {n} em {_br(em, True)}"))
            continue
        # Despachos alguns dias antes da leitura acontecem (2020, 2013); meses antes, não.
        if (l := leit.get(rotulo)) and em.date() < l.date() - timedelta(days=LIMITE_DIAS):
            saida.append(_suspeita(
                "despacho-antes-da-leitura", rotulo, "", f"despacho {n}", em,
                f"Despacho {n} registrado em {_br(em)}, antes da leitura do projeto ({_br(l)}).",
                f"despachos: despacho {n} em {_br(em, True)}; autores: leitura em {_br(l)}"))
        if (ps := pareceres.get((rotulo, n))) and em.date() > min(ps).date() + timedelta(days=1):
            saida.append(_suspeita(
                "despacho-depois-do-parecer", rotulo, "", f"despacho {n}", em,
                f"Despacho {n} registrado em {_br(em)}, depois do parecer de {_br(min(ps))}.",
                f"despachos: despacho {n} em {_br(em, True)}; relatorias: primeiro parecer em {_br(min(ps))}"))
    return saida


def _trocar_dia_mes(d: datetime) -> datetime | None:
    if d.day > 12 or d.day == d.month:
        return None
    return d.replace(day=d.month, month=d.day)


def datas_de_recebimento(registros: list[dict]) -> list[dict]:
    """Recebimentos antes do envio, com o ano trocado ou com o dia e o mês trocados.
    `registros` vem de registros_de_envio."""
    saida = []
    for p in registros:
        envio, receb = _dt(p["enviado_em"]), _dt(p["recebido_em"])
        if envio is None or receb is None:
            continue
        detalhe = f"envio de {envio:%Y-%m-%d %H:%M}"
        ev = f"tramitação: enviado à {p['comissao']} em {_br(envio, True)}, recebido em {_br(receb, True)}"
        trocado = _trocar_dia_mes(receb)
        plausivel = trocado is not None and envio <= trocado <= envio + timedelta(days=LIMITE_DIAS)
        if receb.year == envio.year + 1 and (receb.month, receb.day) == (envio.month, envio.day):
            saida.append(_suspeita(
                "recebimento-um-ano-depois", p["rotulo"], p["comissao"], detalhe, receb,
                f"Enviada em {_br(envio)} e recebida em {_br(receb)}: mesmo dia e mês, um ano depois.", ev))
        elif plausivel and (receb < envio or receb > envio + timedelta(days=LIMITE_DIAS * 2)):
            saida.append(_suspeita(
                "recebimento-dia-mes-trocados", p["rotulo"], p["comissao"], detalhe, receb,
                f"Recebimento em {_br(receb)}; com dia e mês trocados ({_br(trocado)}), fica logo após o envio.",
                ev))
        elif receb < envio - timedelta(minutes=1):
            saida.append(_suspeita(
                "recebimento-antes-do-envio", p["rotulo"], p["comissao"], detalhe, receb,
                f"Recebida em {_br(receb, True)}, antes do envio ({_br(envio, True)}).", ev))
    return saida


def pareceres(relatorias: list[dict]) -> list[dict]:
    """Número de parecer malformado, de enchimento, com ano impossível ou sem data."""
    saida, vistos = [], set()
    for r in relatorias:
        numero = r["parecer"]
        if not numero or (numero, r["rotulo"]) in vistos:  # parecer conjunto: uma suspeita só
            continue
        vistos.add((numero, r["rotulo"]))
        em = _dt(r["parecer_em"])
        ev = (f"relatorias: parecer {numero} da {r['comissao']}, relator {r['relator']}, "
              f"de {_br(em)}, \"{r['conclusao']}\"")
        m = _RX_PARECER.match(numero)
        if not m or m[1] == "9999":
            saida.append(_suspeita("parecer-numero-invalido", r["rotulo"], r["comissao"], numero, em,
                                   f"Parecer com número \"{numero}\".", ev))
            continue
        ano_num, ano_proj = int(m[2]), _ano(r["rotulo"])
        if ano_num < ano_proj or (em and ano_num > em.year):
            motivo = (f"anterior ao projeto ({ano_proj})" if ano_num < ano_proj
                      else f"posterior à data do parecer ({_br(em)})")
            saida.append(_suspeita("parecer-ano-impossivel", r["rotulo"], r["comissao"], numero, em,
                                   f"Parecer {numero}: o ano do número é {motivo}.", ev))
        if em is None:
            saida.append(_suspeita("parecer-sem-data", r["rotulo"], r["comissao"], numero, None,
                                   f"Parecer {numero} sem data.", ev))
    return saida


def leituras(encerrados: list[dict], autores: list[dict]) -> list[dict]:
    """Leitura diferente nos encerramentos e nos autores, ou muito antes do ano do número
    (projetos lidos em dezembro costumam levar o número do ano seguinte)."""
    saida = []
    leit = _leituras(autores)
    for e in encerrados:
        a, b = leit.get(e["rotulo"]), _dt(e["leitura"])
        # Os encerramentos costumam trazer uma data alguns dias ou semanas anterior à dos
        # autores; só diferenças de meses indicam erro.
        if a and b and abs((a - b).days) > LIMITE_LEITURA:
            saida.append(_suspeita(
                "leitura-divergente", e["rotulo"], "", "", b,
                f"Lido em {_br(a)} segundo os autores e em {_br(b)} segundo os encerramentos "
                f"({abs((a - b).days)} dias de diferença).",
                f"autores: leitura em {_br(a)}; encerrados: leitura em {_br(b)}"))
    for rotulo, d in sorted(leit.items()):
        if d.date() < date(_ano(rotulo) - 1, 12, 1):
            saida.append(_suspeita(
                "leitura-antes-do-ano", rotulo, "", "", d,
                f"Projeto de {_ano(rotulo)} lido em {_br(d)}.", f"autores: leitura em {_br(d)}"))
    return saida


# ----------------------------------------------------------------------------- 3. despacho × caminho
def recebida_sem_despacho(passagens: list[dict], despachos: list[dict], passos: list[dict],
                          hoje: datetime) -> list[dict]:
    """Projeto que ficou numa comissão para a qual nenhum despacho o mandou. Só conta a
    passagem de mais de um dia com algum passo interno, ou de mais de 7 dias: as outras são
    envios errados desfeitos logo em seguida."""
    designadas: dict[str, set] = defaultdict(set)
    for d in despachos:
        designadas[d["rotulo"]].add(d["comissao"])
    com_passo: dict[tuple, list[datetime]] = defaultdict(list)
    for p in passos:
        if (d := _dt(p["data"])) and p.get("tipo", "interna") == "interna":
            com_passo[(p["comissao"], p["rotulo"])].append(d)
    saida = []
    for p in passagens:
        rotulo, c = p["rotulo"], p["comissao"]
        desde = _dt(p["desde"])
        if (desde is None or p["desde"] < INICIO_FEED or _tipo(rotulo) not in PROJETOS or _ano(rotulo) < 2013
                or rotulo not in designadas or c in designadas[rotulo]):
            continue
        ate = _dt(p["ate"]) or hoje
        n = sum(desde <= d <= ate for d in com_passo.get((c, rotulo), []))
        dias = (ate - desde).days
        # Envio errado desfeito no mesmo dia já está corrigido; a comissão excluída do despacho
        # depois (motivo "para exclusão da comissão") esteve nele.
        if dias < 1 or (n == 0 and dias <= 7) or "EXCLUS" in (p.get("motivo") or "").upper():
            continue
        saida.append(_suspeita(
            "recebida-sem-despacho", rotulo, c, f"envio de {desde:%Y-%m-%d %H:%M}", desde,
            f"Esteve na {c} de {_br(desde)} a {_br(_dt(p['ate'])) if p['ate'] else 'hoje'} ({n} passos internos), "
            f"mas nenhum despacho a designou (despachos: {', '.join(sorted(designadas[rotulo]))}).",
            f"tramitação: enviado por {p['origem'] or '?'} em {_br(desde, True)}"
            + (f", saiu para {p['destino']}" if p["destino"] else "")
            + (f" ({p['motivo']})" if p.get("motivo") else "")))
    return saida


# ----------------------------------------------------------------------------- 4. acervo de hoje
def votado_e_parado(acervo: list[dict], hoje: datetime) -> list[dict]:
    saida = []
    for a in acervo:
        d = _dt(a["interna_data"])
        if a["interna_tipo"] not in PASSOS_POS_VOTO or d is None or (hoje - d).days <= LIMITE_DIAS:
            continue
        saida.append(_suspeita(
            "votado-e-parado", a["rotulo"], a["comissao"], f"passo de {d:%Y-%m-%d %H:%M}", d,
            f"Em \"{a['interna_tipo']}\" desde {_br(d)} ({(hoje - d).days} dias) e ainda na {a['comissao']}.",
            f"acervo: passo {a['interna_area']}/{a['interna_tipo']} em {_br(d, True)}"))
    return saida


def em_transito(acervo: list[dict], hoje: datetime) -> list[dict]:
    saida = []
    for a in acervo:
        d = _dt(a["enviado_em"])
        if a["recebido_em"] or d is None or (hoje - d).days <= LIMITE_DIAS:
            continue
        saida.append(_suspeita(
            "em-transito", a["rotulo"], a["comissao"], f"envio de {d:%Y-%m-%d %H:%M}", d,
            f"Enviada por {a['enviado_por']} à {a['comissao']} em {_br(d)} e não recebida há {(hoje - d).days} dias.",
            f"acervo: enviado em {_br(d, True)}, sem recebimento"
            + (f"; relator {a['relator']}" if a["relator"] else "")))
    return saida


# ----------------------------------------------------------------------------- 5. encerramento
def tramita_depois_de_encerrada(encerrados: list[dict], passagens: list[dict],
                                relatorias: list[dict]) -> list[dict]:
    """Projeto encerrado com envio a comissão, despacho ou parecer depois do encerramento.
    Desarquivado, o projeto sai da lista de encerrados; se continua nela, o encerramento ou a
    tramitação está registrado errado. Não contam os apensados (tramitam com o principal) nem
    envios depois devolvidos ao arquivo (o erro já foi desfeito)."""
    encerr = {e["rotulo"]: (_dt(e["encerramento"]), e["motivo"]) for e in encerrados
              if e["motivo"].upper() != "APENSADO"}
    depois_de: dict[str, list] = defaultdict(list)
    for p in sorted(passagens, key=lambda p: p["desde"] or ""):
        enc = encerr.get(p["rotulo"], (None,))[0]
        if enc and (d := _dt(p["desde"])) and d.date() > enc.date() + timedelta(days=1):
            depois_de[p["rotulo"]].append((d, p))
    fatos: dict[str, list[tuple]] = defaultdict(list)
    for rotulo, lista in depois_de.items():
        ultima = lista[-1][1]
        if ultima["destino"] == "ARQUIVO":
            continue
        for d, p in lista:
            onde = "continua lá" if not p["destino"] else f"saiu para {p['destino']}"
            fatos[rotulo].append((d, f"envio à {p['comissao']} por {p['origem'] or '?'} ({onde})"))
    for r in relatorias:
        enc = encerr.get(r["rotulo"], (None,))[0]
        if enc is None:
            continue
        if (d := _dt(r["despachado_em"])) and d.date() > enc.date() + timedelta(days=1):
            fatos[r["rotulo"]].append((d, f"despacho {r['despacho']}"))
        if r["parecer"] and (d := _dt(r["parecer_em"])) and d.date() > enc.date() + timedelta(days=1):
            fatos[r["rotulo"]].append((d, f"parecer {r['parecer']} da {r['comissao']}"))
    saida = []
    for rotulo, lista in sorted(fatos.items()):
        enc, motivo = encerr[rotulo]
        depois = sorted(set(lista))
        saida.append(_suspeita(
            "tramita-depois-de-encerrada", rotulo, "", "", enc,
            f"Encerrado em {_br(enc)} ({motivo}), mas teve {len(depois)} registro(s) depois, "
            f"a partir de {_br(depois[0][0])}.",
            f"encerrados: {_br(enc, True)}; depois: " + "; ".join(f"{_br(d, True)} {t}" for d, t in depois[:4])
            + (" ..." if len(depois) > 4 else "")))
    return saida
