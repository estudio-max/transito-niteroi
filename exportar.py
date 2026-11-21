"""Exporta o banco para o JSON que o painel público lê.

Uso:  uv run exportar.py                      grava painel/public/dados.json
      uv run exportar.py --enviar host:pasta  grava e envia por scp
"""

import argparse
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import antes_depois
import incidentes
from coletor import (
    CAMERAS,
    COLUNAS,
    FUSO,
    REGIAO,
    ROTULO_SENTIDO,
    SENTIDOS,
    VEICULOS,
    criar_tabela_estado,
)
from historia import criar_tabela_clima
from incidentes import PUBLICAVEIS

SAIDA = Path("painel/public/dados.json")
COBERTURA_DIAS = 14  # o mapa de cobertura mostra as duas últimas semanas
JANELA_H = 24  # o painel mostra as últimas 24 h de coleta
MIN_CLIPES_PUBLICAR = 3  # ocorrência só vai ao painel depois de ~3 min parada (modelo local erra)
RECENTE_MIN = 15  # medição mais velha que isso não descreve "agora"
MIN_BASE_HORA = 30  # clipes do mesmo tipo de dia e hora, na câmera, para dizer o que é habitual
MIN_DIAS_BASE = 3  # em pelo menos tantos dias diferentes (um dia só não é "habitual")
BALDE_MIN = 5  # um ponto do gráfico = 5 min (1 clipe de ~20 veículos é ruidoso demais)


def ler(db, desde_utc):
    """Clipes a partir de desde_utc (ISO), com as classes somadas por sentido."""
    somas = ", ".join(
        f"{' + '.join(f'{v}_{s}' for v in VEICULOS.values())} AS {s}" for s in SENTIDOS
    )
    tipos = ", ".join(
        f"{' + '.join(f'{v}_{s}' for s in SENTIDOS)} AS {v}" for v in VEICULOS.values()
    )
    cur = db.execute(
        "SELECT camera, clipe_utc, duracao_s, ocupacao,"
        # config = detector e linha de contagem: o habitual e a tendência só comparam clipes
        # medidos do mesmo jeito (trocar qualquer um dos dois muda a contagem)
        " COALESCE(modelo, '') || '|' || COALESCE(detector, '') || '|' || COALESCE(linha, '')"
        # passo ≠ 1 muda o rastreamento e a contagem: entra no config, sem reescrever o passado
        " || CASE WHEN COALESCE(passo, '') IN ('', '1') THEN '' ELSE '|passo=' || passo END"
        f" AS config, {somas}, {tipos}"
        " FROM clipes"
        " WHERE clipe_utc >= ? ORDER BY clipe_utc",
        (desde_utc,),
    )
    nomes = [d[0] for d in cur.description]
    return [dict(zip(nomes, linha, strict=True)) for linha in cur]


def _fluxo_h(clipes, sentidos=SENTIDOS):
    duracao = sum(c["duracao_s"] for c in clipes)
    veiculos = sum(c[s] for c in clipes for s in sentidos)
    return round(veiculos * 3600 / duracao) if duracao else None


def _ocupacao(clipes):
    return round(sum(c["ocupacao"] for c in clipes) / len(clipes), 1) if clipes else None


def _epoch(utc):
    return datetime.fromisoformat(utc).timestamp()


def agregar(clipes, minutos=BALDE_MIN):
    """Série temporal em baldes de N minutos: [{t (ms), <cam>_<sentido>_fluxo, <cam>_ocup}].
    O fluxo é separado por sentido: somar sentidos opostos misturaria o que vai para a
    ponte com o que vem dela. Baldes sem clipe entram só com t (a linha quebra no buraco)."""
    passo = minutos * 60
    baldes = {}
    for c in clipes:
        baldes.setdefault(int(_epoch(c["clipe_utc"]) // passo), {}).setdefault(
            c["camera"], []
        ).append(c)
    if not baldes:
        return []
    serie = []
    for b in range(min(baldes), max(baldes) + 1):
        ponto = {"t": b * passo * 1000}
        for camera, grupo in baldes.get(b, {}).items():
            for s in SENTIDOS:
                ponto[f"{camera}_{s}_fluxo"] = _fluxo_h(grupo, (s,))
            ponto[f"{camera}_ocup"] = _ocupacao(grupo)
        serie.append(ponto)
    return serie


N_CAMERAS = len(CAMERAS)


def cobertura(instantes_utc, agora_utc, dias=COBERTURA_DIAS, cameras=N_CAMERAS):
    """Minutos coletados por câmera em cada hora dos últimos `dias` dias (fuso de Niterói).
    Devolve {dias: ['AAAA-MM-DD', ... mais recente primeiro], minutos: [[24 valores], ...]}.
    Um clipe ~ 1 minuto de vídeo; o valor é a média entre as câmeras, limitado a 60."""
    hoje = datetime.fromisoformat(agora_utc).astimezone(FUSO).date()
    datas = [(hoje - timedelta(days=i)).isoformat() for i in range(dias)]
    indice = {d: i for i, d in enumerate(datas)}
    contagem = [[0] * 24 for _ in datas]
    for utc in instantes_utc:
        local = datetime.fromisoformat(utc).astimezone(FUSO)
        i = indice.get(local.date().isoformat())
        if i is not None:
            contagem[i][local.hour] += 1
    return {
        "dias": datas,
        "minutos": [[min(60, round(n / cameras)) for n in linha] for linha in contagem],
    }


def ler_ocorrencias(db, desde_utc, limite=20):
    """Incidentes publicáveis (acidente, enguiço, bloqueio) ativos desde desde_utc que
    duraram ao menos MIN_CLIPES_PUBLICAR clipes: parada curta é mais provavelmente erro.
    Deduplica por (câmera, início): o mesmo evento não pode virar duas ocorrências."""
    incidentes.criar_tabelas(db)
    cur = db.execute(
        "SELECT camera, inicio_utc, fim_utc, clipes, classe, tipo, confianca, descricao"
        f" FROM incidentes WHERE fim_utc >= ? AND clipes >= ?"
        f" AND tipo IN ({', '.join('?' * len(PUBLICAVEIS))})"
        " ORDER BY inicio_utc DESC, fim_utc DESC",
        (desde_utc, MIN_CLIPES_PUBLICAR, *PUBLICAVEIS),
    )
    nomes = [d[0] for d in cur.description]
    saida, vistos = [], set()
    for linha in cur:
        o = dict(zip(nomes, linha, strict=True))
        chave = (o["camera"], o["inicio_utc"])
        if chave in vistos:
            continue  # mesmo evento com mais de uma linha (ex.: reaberto por engano)
        vistos.add(chave)
        saida.append(o)
        if len(saida) >= limite:
            break
    return saida


def _dt(utc):
    return datetime.fromisoformat(utc)


def _hora_local(utc):
    return _dt(utc).astimezone(FUSO).strftime("%Hh%M")


def situacao(historico, agora_utc):
    """Para cada câmera contada, compara a ocupação dos últimos RECENTE_MIN minutos com o que a
    própria câmera registrou no mesmo tipo de dia (útil ou fim de semana) e na mesma hora.
    Níveis (ids antigos, significados novos): livre = abaixo do habitual, moderado = dentro
    do habitual, pesado = acima do habitual (acima do percentil 85 daquele dia e hora);
    sem_historico = ainda sem base (30 clipes em 3 dias) para aquele dia e hora;
    sem_dado_recente. É relativo ao que a câmera já registrou, não a um "normal" oficial."""
    agora = _dt(agora_utc)
    base = montar_base(historico)
    saida = {}
    for camera in CAMERAS:
        todos = [c for c in historico if c["camera"] == camera]
        recentes = [
            c for c in todos if agora - _dt(c["clipe_utc"]) <= timedelta(minutes=RECENTE_MIN)
        ]
        if not recentes:
            saida[camera] = {"nivel": "sem_dado_recente"}
            continue
        ocup = _ocupacao(recentes)
        nivel, pct, dias, clipes = _nivel_habitual(
            ocup, base[camera], _chave(max(c["clipe_utc"] for c in recentes))
        )  # hora da medição, não do relógio
        if nivel is None:
            saida[camera] = {
                "nivel": "sem_historico",
                "ocupacao": ocup,
                "base": {
                    "dias": dias,
                    "clipes": clipes,
                    "dias_min": MIN_DIAS_BASE,
                    "clipes_min": MIN_BASE_HORA,
                },
            }
            continue
        saida[camera] = {"nivel": nivel, "ocupacao": ocup, "percentil": pct}
    return saida


def _chave(utc):
    """(dia útil?, hora) no relógio de Niterói: o "mesmo dia e hora" da comparação."""
    local = _dt(utc).astimezone(FUSO)
    return local.weekday() < 5, local.hour


def montar_base(historico):
    """{câmera: {(dia útil?, hora): {"oc": ocupações ordenadas, "dias": datas}}}.
    Só entram clipes contados com a mesma configuração do detector (modelo, resolução,
    rastreador) do clipe mais recente da câmera: um detector mais sensível vê mais veículos
    por quadro, e misturar as séries pareceria "acima do habitual" só por causa da troca."""
    base = {cam: {} for cam in CAMERAS}
    atual = {}
    for c in historico:
        if c["camera"] in base and c["clipe_utc"] >= atual.get(c["camera"], ("", ""))[0]:
            atual[c["camera"]] = (c["clipe_utc"], c.get("config"))
    for c in historico:
        if c["camera"] not in base or c.get("config") != atual[c["camera"]][1]:
            continue
        b = base[c["camera"]].setdefault(_chave(c["clipe_utc"]), {"oc": [], "dias": set()})
        b["oc"].append(c["ocupacao"])
        b["dias"].add(_dt(c["clipe_utc"]).astimezone(FUSO).date())
    for por_camera in base.values():
        for b in por_camera.values():
            b["oc"].sort()
    return base


def _nivel_habitual(ocup, base_camera, chave):
    """(nível, percentil, dias, clipes) frente ao habitual daquele dia e hora;
    (None, None, dias, clipes) sem base, para o painel mostrar o progresso da base."""
    b = base_camera.get(chave)
    if not b or len(b["oc"]) < MIN_BASE_HORA or len(b["dias"]) < MIN_DIAS_BASE:
        return None, None, len(b["dias"]) if b else 0, len(b["oc"]) if b else 0
    nivel, pct = _nivel(ocup, b["oc"])
    return nivel, pct, len(b["dias"]), len(b["oc"])


def _nivel(ocup, ocupacoes):
    """(nível, percentil) de uma ocupação dentro de todas as ocupações da câmera.
    ocupacoes vem ORDENADA: a busca binária mantém o cálculo rápido com meses de coleta."""
    from bisect import bisect_right

    pct = round(100 * bisect_right(ocupacoes, ocup) / len(ocupacoes))
    return ("livre" if pct <= 15 else "moderado" if pct <= 85 else "pesado"), pct


def _dia_relativo(utc, agora_utc):
    dia = _dt(utc).astimezone(FUSO).date()
    hoje = _dt(agora_utc).astimezone(FUSO).date()
    if dia == hoje:
        return "hoje"
    if dia == hoje - timedelta(days=1):
        return "ontem"
    return dia.strftime("%d/%m")


BLOCO_H = 3  # com coleta contínua, o histórico é cortado em blocos fixos de 3 horas


def _bloco(utc):
    local = _dt(utc).astimezone(FUSO)
    return local.date(), local.hour // BLOCO_H


def periodos(historico, ocorrencias, agora_utc, limite=60):  # 7 dias de blocos de 3 h
    """Histórico legível: cada período contínuo de coleta (intervalo entre clipes < 30 min,
    cortado em blocos fixos de BLOCO_H horas do relógio de Niterói) vira um bloco com, por câmera, uma faixa de 5 em 5 minutos (livre, moderado, pesado,
    ou None sem medição), os minutos pesados, o pior momento, o fluxo por sentido e os
    ônibus por hora, mais as ocorrências publicáveis do período. Mais recente primeiro."""
    ordenados = sorted(historico, key=lambda c: c["clipe_utc"])
    blocos, atual = [], []
    for c in ordenados:
        quebra = atual and (
            _dt(c["clipe_utc"]) - _dt(atual[-1]["clipe_utc"]) > timedelta(minutes=30)
            or _bloco(c["clipe_utc"]) != _bloco(atual[-1]["clipe_utc"])
        )
        if quebra:
            blocos.append(atual)
            atual = []
        atual.append(c)
    if atual:
        blocos.append(atual)

    base_habitual = montar_base(historico)
    passo = BALDE_MIN * 60
    saida = []
    for bloco in reversed(blocos[-limite:]):
        ini, fim = bloco[0]["clipe_utc"], bloco[-1]["clipe_utc"]
        b0 = int(_epoch(ini) // passo)
        n_baldes = int(_epoch(fim) // passo) - b0 + 1
        cameras = []
        for cam, cfg in CAMERAS.items():
            grupo = [c for c in bloco if c["camera"] == cam]
            if not grupo:
                continue
            baldes = {}
            for c in grupo:
                baldes.setdefault(int(_epoch(c["clipe_utc"]) // passo) - b0, []).append(c)
            faixa = [
                _nivel_habitual(
                    _ocupacao(baldes[i]),
                    base_habitual[cam],
                    _chave(datetime.fromtimestamp((b0 + i) * passo, UTC).isoformat()),
                )[0]
                if i in baldes
                else None
                for i in range(n_baldes)
            ]
            com_base = any(n is not None for n in faixa)
            pior_i = max(baldes, key=lambda i: _ocupacao(baldes[i]))
            duracao = sum(c["duracao_s"] for c in grupo)
            cameras.append(
                {
                    "id": cam,
                    "nome": cfg["nome"],
                    "faixa": faixa,
                    "minutos_pesado": faixa.count("pesado") * BALDE_MIN,
                    "pior_utc": datetime.fromtimestamp((b0 + pior_i) * passo, UTC).isoformat(),
                    "fluxo_h": {s: _fluxo_h(grupo, (s,)) for s in SENTIDOS},
                    "onibus_h": round(sum(c.get("onibus", 0) for c in grupo) * 3600 / duracao)
                    if duracao
                    else None,
                    "com_base": com_base,
                }
            )
        ocorr = [
            o for o in ocorrencias if ini <= o["inicio_utc"] <= fim or ini <= o["fim_utc"] <= fim
        ]
        saida.append(
            {
                "inicio_utc": ini,
                "fim_utc": fim,
                "dia": _dia_relativo(ini, agora_utc),
                "inicio_t": datetime.fromtimestamp(b0 * passo, UTC).isoformat(),
                "balde_min": BALDE_MIN,
                "cameras": cameras,
                "ocorrencias": len(ocorr),
                "frase": _frase_periodo(cameras, len(ocorr)),
            }
        )
    return saida


JANELAS = {"7d": 7, "30d": 30, "total": None}


def resumos(todos, ocorrencias, agora_utc):
    """Resumo por janela (7 dias, 30 dias, toda a história) e câmera: tempo de vídeo, % do
    tempo pesado (baldes de 5 min), horário que costuma ser o pior, perfil das 24 horas
    (nível típico de cada hora), fluxo médio por sentido, ônibus por hora e ocorrências.
    O nível de cada balde compara com o mesmo dia e hora; o perfil das 24 horas mostra o formato
    do dia (quais horas são mais cheias que o resto do dia da própria câmera)."""
    agora = _dt(agora_utc)
    base_habitual = montar_base(todos)
    base = {cam: sorted(c["ocupacao"] for c in todos if c["camera"] == cam) for cam in CAMERAS}
    passo = BALDE_MIN * 60
    saida = {}
    for chave, dias in JANELAS.items():
        clipes = (
            todos
            if dias is None
            else [c for c in todos if agora - _dt(c["clipe_utc"]) <= timedelta(days=dias)]
        )
        cameras = []
        for cam, cfg in CAMERAS.items():
            g = [c for c in clipes if c["camera"] == cam]
            if not g:
                continue
            com_base = len(base[cam]) >= MIN_BASE_HORA
            baldes, horas = {}, {}
            for c in g:
                baldes.setdefault(int(_epoch(c["clipe_utc"]) // passo), []).append(c)
                horas.setdefault(_dt(c["clipe_utc"]).astimezone(FUSO).hour, []).append(c)
            niveis = [
                n
                for bk, b in baldes.items()
                if (
                    n := _nivel_habitual(
                        _ocupacao(b),
                        base_habitual[cam],
                        _chave(datetime.fromtimestamp(bk * passo, UTC).isoformat()),
                    )[0]
                )
            ]
            ocup_hora = {h: _ocupacao(hs) for h, hs in horas.items()}
            duracao = sum(c["duracao_s"] for c in g)
            cameras.append(
                {
                    "id": cam,
                    "nome": cfg["nome"],
                    "horas_video": round(duracao / 3600, 1),
                    "pct_pesado": round(100 * niveis.count("pesado") / len(niveis))
                    if niveis
                    else None,
                    "minutos_pesado": niveis.count("pesado") * BALDE_MIN,
                    "pior_hora": max(ocup_hora, key=ocup_hora.get),
                    "perfil": [
                        _nivel(ocup_hora[h], base[cam])[0] if com_base and h in ocup_hora else None
                        for h in range(24)
                    ],
                    "fluxo_h": {s: _fluxo_h(g, (s,)) for s in SENTIDOS},
                    "onibus_h": round(sum(c.get("onibus", 0) for c in g) * 3600 / duracao)
                    if duracao
                    else None,
                }
            )
        desde = min((c["clipe_utc"] for c in clipes), default=None)
        saida[chave] = {
            "desde_utc": desde,
            "dias_com_dados": len({_dt(c["clipe_utc"]).astimezone(FUSO).date() for c in clipes}),
            "ocorrencias": sum(1 for o in ocorrencias if desde and o["inicio_utc"] >= desde),
            "cameras": cameras,
        }
    return saida


def _frase_periodo(cameras, n_ocorrencias):
    partes = []
    for c in cameras:
        if not c["com_base"]:
            partes.append(f"{c['nome']}: ainda sem base para comparar com este dia e horário")
        elif c["minutos_pesado"]:
            partes.append(
                f"{c['nome']}: acima do habitual por {c['minutos_pesado']} min"
                f" (pior às {_hora_local(c['pior_utc'])})"
            )
        else:
            partes.append(f"{c['nome']}: sem trânsito acima do habitual")
    if n_ocorrencias:
        partes.append(f"{n_ocorrencias} ocorrência" + ("s" if n_ocorrencias > 1 else ""))
    return "; ".join(partes) + "."


def tendencia(historico, agora_utc):
    """Para cada câmera contada: veículos por hora (os dois sentidos) nos últimos 15, 30 e 60
    minutos e a direção: compara os últimos 15 minutos com os 45 anteriores. Não depende do
    habitual: diz só se o movimento está subindo, estável ou descendo agora.
    Cada janela só vale se os clipes a cobrem de ponta a ponta (o mais antigo alcança dois
    terços dela) e somam um terço dela em vídeo; senão o número de 30 ou 60 min é None e não
    há direção. Assim "60 min" não vira média de 25, e a 000018, que repete clipe e tem só
    metade do tempo em vídeo, não fica de fora. Só usa clipes do mesmo detector do clipe mais
    recente: logo depois de uma troca, um detector que conta mais pareceria movimento subindo."""
    agora = _dt(agora_utc)
    saida = {}
    for cam in CAMERAS:
        g = [c for c in historico if c["camera"] == cam]
        if g:
            config = max(g, key=lambda c: c["clipe_utc"]).get("config")
            g = [c for c in g if c.get("config") == config]

        def janela(de, ate, g=g):
            return [
                c
                for c in g
                if timedelta(minutes=de) <= agora - _dt(c["clipe_utc"]) < timedelta(minutes=ate)
            ]

        def video_min(clipes):
            return sum(c["duracao_s"] for c in clipes) / 60

        def cobre(clipes, minutos, inicio=0):  # janela [inicio, inicio + minutos) atrás
            if not clipes:
                return False
            idade = (agora - min(_dt(c["clipe_utc"]) for c in clipes)).total_seconds() / 60
            return idade >= inicio + minutos * 2 / 3 and video_min(clipes) >= minutos / 3

        ult15, ult30, ult60, antes = janela(0, 15), janela(0, 30), janela(0, 60), janela(15, 60)
        if not ult15:
            continue
        direcao = None
        if cobre(ult15, 15) and cobre(antes, 45, inicio=15):
            razao = _fluxo_h(ult15) / max(_fluxo_h(antes), 1)
            direcao = "subindo" if razao > 1.15 else "descendo" if razao < 0.85 else "estavel"
        dur15 = sum(c["duracao_s"] for c in ult15)
        saida[cam] = {
            "m15": _fluxo_h(ult15),
            # o mesmo movimento dos últimos 15 min separado por tipo (veículos/h)
            "tipos": {
                v: round(sum(c.get(v, 0) for c in ult15) * 3600 / dur15) if dur15 else 0
                for v in VEICULOS.values()
            },
            "m30": _fluxo_h(ult30) if cobre(ult30, 30) else None,
            "m60": _fluxo_h(ult60) if cobre(ult60, 60) else None,
            "direcao": direcao,
        }
    return saida


def texto_simples(dados):
    """Página só texto, sem JavaScript, para internet ruim: veredito, cada ponto com a
    tendência e as ocorrências. Gerada a cada coleta como texto.html."""
    from html import escape

    nomes = {c: cfg["nome"] for c, cfg in CAMERAS.items()}
    nivel = {
        "livre": "abaixo do habitual",
        "moderado": "dentro do habitual",
        "pesado": "acima do habitual",
        "sem_historico": "ainda sem base para comparar com este dia e hora",
        "sem_dado_recente": "sem medição agora",
    }
    seta = {"subindo": "subindo", "estavel": "estável", "descendo": "descendo", None: ""}
    linhas = [dados["veredito"]["texto"]]
    if dados["veredito"].get("detalhe"):
        linhas.append(dados["veredito"]["detalhe"])
    for cam, s in dados.get("situacao", {}).items():
        t = dados.get("tendencia", {}).get(cam)
        mov = (
            f" Movimento: {t['m15']:,} veículos/h nos últimos 15 min".replace(",", ".")
            + (f", {seta[t['direcao']]}" if t["direcao"] else "")
            + "."
            if t and t["m15"] is not None
            else ""
        )
        linhas.append(f"{nomes.get(cam, cam)}: {nivel.get(s['nivel'], s['nivel'])}.{mov}")
    movs = dados.get("movimentos", {})
    if movs:
        rotulo = {"leste": "leste", "oeste": "oeste", "norte": "norte", "sul": "sul"}
        for cam, d in movs.items():
            partes = ", ".join(
                f"{rotulo.get(m, m)} {q}" for m, q in sorted(d.items(), key=lambda x: -x[1])
            )
            linhas.append(f"{nomes.get(cam, cam)} — por direção: {partes}.")
    oc = dados.get("ocorrencias", [])
    linhas.append(
        "Ocorrências nas últimas 24 h: "
        + (
            "; ".join(
                f"{TIPO_TEXTO.get(o['tipo'], o['tipo']).lower()} em {o['camera']} desde "
                f"{_hora_local(o['inicio_utc'])}"
                + (f" até {_hora_local(o['fim_utc'])}" if o.get("fim_utc") else "")
                for o in oc
            )
            if oc
            else "nenhuma"
        )
        + "."
    )
    corpo = "\n".join(f"<p>{escape(x)}</p>" for x in linhas)
    quando = _dt(dados["gerado_utc"]).astimezone(FUSO).strftime("%d/%m às %Hh%M")
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        # base _top: dentro de um iframe em outro site, o link abre o painel na janela inteira
        '<base target="_top">'
        "<title>Saída da Ponte, só texto</title>"
        '<meta name="robots" content="noindex"></head>'
        '<body style="font-family:sans-serif;max-width:40rem;margin:1rem auto;padding:0 1rem;'
        'line-height:1.5;color:#111;background:#fff">'
        "<h1>Trânsito na saída da Ponte</h1>"
        f"{corpo}"
        f"<p><small>Atualizado em {quando}. Medição automática por IA nas câmeras públicas da"
        ' NitTrans, ainda sem conferência. <a href="./">Painel completo</a>.</small></p>'
        "</body></html>"
    )


def onibus(historico, agora_utc):
    """Ônibus por hora e intervalo médio entre eles, na última hora, por câmera contada.
    Só com pelo menos 10 minutos de vídeo na hora (menos que isso é sorte, não média)."""
    agora = _dt(agora_utc)
    saida = {}
    for camera in CAMERAS:
        grupo = [
            c
            for c in historico
            if c["camera"] == camera and agora - _dt(c["clipe_utc"]) <= timedelta(hours=1)
        ]
        duracao = sum(c["duracao_s"] for c in grupo)
        if duracao < 600:
            continue
        por_hora = round(sum(c.get("onibus", 0) for c in grupo) * 3600 / duracao)
        saida[camera] = {
            "por_hora": por_hora,
            "intervalo_min": round(60 / por_hora, 1) if por_hora else None,
            "minutos_video": round(duracao / 60),
        }
    return saida


def cameras_no_ar(estados, agora_utc):
    """estados: {camera: (verificado_utc, http, ultimo_video_utc)} da última verificação.
    no_ar = responde e o vídeo foi renovado há pouco; parada = responde com vídeo velho;
    fora = erro HTTP ou sem conexão; sem_verificacao = coletor parado (nada recente)."""
    agora = _dt(agora_utc)
    saida = []
    for cam in REGIAO:
        e = estados.get(cam["id"])
        if not e or agora - _dt(e[0]) > timedelta(minutes=30):
            estado = "sem_verificacao"
        elif e[1] != 200:
            estado = "fora"
        elif not e[2] or _dt(e[0]) - _dt(e[2]) > timedelta(minutes=10):
            estado = "parada"
        else:
            estado = "no_ar"
        saida.append(
            {
                **cam,
                "estado": estado,
                "ultimo_video_utc": e[2] if e else None,
                "contada": cam["id"] in CAMERAS,
            }
        )
    return saida


def movimentos_resumo(db, desde_utc):
    """Veículos por direção de movimento (RF6) por câmera, nas últimas 24 h.
    {} se a tabela `movimentos` ainda não existir (coletor antigo)."""
    try:
        linhas = db.execute(
            "SELECT camera, movimento, SUM(quantidade) FROM movimentos"
            " WHERE clipe_utc >= ? GROUP BY camera, movimento ORDER BY camera, movimento",
            (desde_utc,),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    saida = {}
    for cam, mov, q in linhas:
        saida.setdefault(cam, {})[mov] = q
    return saida


TIPO_TEXTO = {"acidente": "Acidente", "enguico": "Veículo enguiçado", "bloqueio": "Bloqueio"}


def _lista(nomes):
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def veredito(sit, ocorrencias, ultimo, agora_utc, ultimo_periodo=None):
    """Uma frase para quem abre o painel: o que está acontecendo agora ou, com a coleta
    parada, o resumo do último período medido. nivel: ok, atencao, alerta (ocorrência
    em andamento), pausado (sem medição recente)."""
    agora = _dt(agora_utc)
    if not ultimo or agora - _dt(ultimo) > timedelta(minutes=RECENTE_MIN):
        if ultimo_periodo:
            p = ultimo_periodo
            return {
                "nivel": "pausado",
                "texto": f"Último período medido: {p['dia']}, das"
                f" {_hora_local(p['inicio_utc'])} às {_hora_local(p['fim_utc'])}.",
                "detalhe": p["frase"],
            }
        return {"nivel": "pausado", "texto": "Ainda não há medição."}
    nomes = {c: cfg["nome"] for c, cfg in CAMERAS.items()}
    partes, nivel = [], "ok"
    abertas = [
        o for o in ocorrencias if agora - _dt(o["fim_utc"]) <= timedelta(minutes=RECENTE_MIN)
    ]
    if abertas:
        o, nivel = abertas[0], "alerta"
        partes.append(
            f"{TIPO_TEXTO[o['tipo']]} em {nomes.get(o['camera'], o['camera'])}"
            f" desde {_hora_local(o['inicio_utc'])}."
        )
    pesados = [nomes[c] for c, s in sit.items() if s["nivel"] == "pesado"]
    if pesados:
        nivel = "alerta" if abertas else "atencao"
        partes.append(f"Trânsito acima do habitual em {_lista(pesados)}.")
    if not partes:
        if any("percentil" in s for s in sit.values()):
            partes.append("Trânsito dentro do habitual ou abaixo nos pontos medidos.")
        else:  # sem base não é "tudo bem": cartão neutro, nunca verde
            nivel = "sem_base"
            partes.append(
                "Coleta em andamento. Ainda não dá para dizer se o trânsito está acima ou"
                " abaixo do habitual: faltam dias de coleta neste dia da semana e horário."
            )
    return {"nivel": nivel, "texto": " ".join(partes)}


def montar(
    clipes,
    agora_utc,
    instantes_cobertura=(),
    ocorrencias=(),
    historico=None,
    estados=None,
    ocorrencias_historico=None,
):
    """Tudo que o painel mostra, a partir dos clipes já lidos. historico = clipes dos
    últimos COBERTURA_DIAS dias (base da situação, dos ônibus e dos períodos); estados =
    câmeras no ar; ocorrencias_historico = ocorrências publicáveis do mesmo intervalo."""
    historico = clipes if historico is None else historico
    ultimo = max((c["clipe_utc"] for c in clipes), default=None)
    sit = situacao(historico, agora_utc)
    hist_periodos = periodos(
        historico,
        ocorrencias if ocorrencias_historico is None else ocorrencias_historico,
        agora_utc,
    )
    resumo = []
    if ultimo:
        corte = (datetime.fromisoformat(ultimo) - timedelta(hours=1)).isoformat()
        for camera, cfg in CAMERAS.items():
            grupo = [c for c in clipes if c["camera"] == camera and c["clipe_utc"] >= corte]
            resumo.append(
                {
                    "id": camera,
                    "nome": cfg["nome"],
                    "ocupacao": _ocupacao(grupo),
                    "clipes": len(grupo),
                    # fluxo_h = última hora coletada; total = veículos em toda a janela
                    "por_sentido": {
                        s: {
                            "fluxo_h": _fluxo_h(grupo, (s,)),
                            "total": sum(c[s] for c in clipes if c["camera"] == camera),
                        }
                        for s in SENTIDOS
                    },
                    # composição por tipo em toda a janela exportada, não só na última hora
                    "tipos": {
                        v: sum(c.get(v, 0) for c in clipes if c["camera"] == camera)
                        for v in VEICULOS.values()
                    },
                }
            )
    return {
        "gerado_utc": agora_utc,
        "ultimo_clipe_utc": ultimo,
        "validado": False,  # só muda quando a fase 2 (validação) fechar
        "balde_min": BALDE_MIN,
        "cameras": [
            {"id": c, "nome": cfg["nome"], "sentido_confirmado": cfg["sentido_confirmado"]}
            for c, cfg in CAMERAS.items()
        ],
        "sentidos": ROTULO_SENTIDO,
        "veredito": veredito(
            sit, ocorrencias, ultimo, agora_utc, hist_periodos[0] if hist_periodos else None
        ),
        "periodos": hist_periodos,
        "situacao": sit,
        "onibus": onibus(historico, agora_utc),
        "tendencia": tendencia(historico, agora_utc),
        "regiao": cameras_no_ar(estados or {}, agora_utc),
        "resumo": resumo,
        "total_veiculos": sum(c[s] for c in clipes for s in SENTIDOS),
        "total_clipes": len(clipes),
        "serie": agregar(clipes),
        "cobertura": cobertura(instantes_cobertura, agora_utc),
        # um ponto por clipe para o diagrama fluxo x ocupação
        "dispersao": [
            {"c": c["camera"], "f": _fluxo_h([c]), "o": round(c["ocupacao"], 1)} for c in clipes
        ],
        "ultimos": [
            {
                "camera": CAMERAS.get(c["camera"], {}).get("nome", c["camera"]),
                "utc": c["clipe_utc"],
                **{s: c[s] for s in SENTIDOS},
                "fluxo_h": _fluxo_h([c]),
                "ocupacao": round(c["ocupacao"], 1),
            }
            for c in sorted(clipes, key=lambda c: c["clipe_utc"], reverse=True)[:20]
        ],
        # classificação automática (modelo de visão local), não confirmada: o painel avisa
        "ocorrencias": [
            {**o, "camera": CAMERAS.get(o["camera"], {}).get("nome", o["camera"])}
            for o in ocorrencias
        ],
    }


def exportar(banco="fluxo.db", saida=SAIDA, enviar=None):
    agora = datetime.now(UTC)
    db = sqlite3.connect(banco, timeout=30)
    desde_janela = (agora - timedelta(hours=JANELA_H)).isoformat()
    historico = ler(db, (agora - timedelta(days=COBERTURA_DIAS + 1)).isoformat())
    clipes = [c for c in historico if c["clipe_utc"] >= desde_janela]
    ocorrencias_hist = ler_ocorrencias(
        db, (agora - timedelta(days=COBERTURA_DIAS + 1)).isoformat(), limite=500
    )
    ocorrencias = [o for o in ocorrencias_hist if o["fim_utc"] >= desde_janela][:20]
    instantes = [c["clipe_utc"] for c in historico]
    criar_tabela_estado(db)
    estados = {
        camera: (verificado, http, video)
        for camera, verificado, http, video in db.execute(
            "SELECT e.camera, e.verificado_utc, e.http,"
            " (SELECT MAX(video_utc) FROM estado_cameras WHERE camera = e.camera)"
            " FROM estado_cameras e WHERE e.verificado_utc ="
            " (SELECT MAX(verificado_utc) FROM estado_cameras WHERE camera = e.camera)"
        )
    }
    db.close()
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    dados = montar(
        clipes,
        agora.isoformat(timespec="seconds"),
        instantes,
        ocorrencias,
        historico,
        estados,
        ocorrencias_hist,
    )
    arquivo_csv = saida.with_name("dados-por-hora.csv")
    db = sqlite3.connect(banco, timeout=30)
    arquivo_csv.write_text(csv_por_hora(db), encoding="utf-8")
    nomes = {cam["id"]: cam["nome"] for cam in REGIAO}
    todos = ler(db, "0000")  # ponytail: lê toda a história a cada 5 min; agregar em tabela se pesar
    dados["resumos"] = resumos(
        todos, ler_ocorrencias(db, "0000", limite=100000), dados["gerado_utc"]
    )
    dados["antes_depois"] = [
        {**r, "nome": nomes.get(r["camera"], r["camera"])}
        for r in antes_depois.avaliar(db, agora.astimezone(FUSO).date())
    ]
    dados["movimentos"] = movimentos_resumo(db, desde_janela)
    db.close()
    saida.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    arquivo_feed = saida.with_name("feed.xml")
    arquivo_feed.write_text(
        feed(dados["periodos"], ocorrencias_hist, dados["gerado_utc"]), encoding="utf-8"
    )
    arquivo_texto = saida.with_name("texto.html")
    arquivo_texto.write_text(texto_simples(dados), encoding="utf-8")
    if enviar:
        subprocess.run(  # noqa: S603
            [  # noqa: S607 - scp do sistema, como no resto do projeto
                "scp",
                "-q",
                "-o",
                "BatchMode=yes",
                str(saida),
                str(arquivo_feed),
                str(arquivo_csv),
                str(arquivo_texto),
                f"{enviar}/",
            ],  # noqa: S607
            check=True,
            timeout=60,
        )
    return len(clipes)


SITE = "https://transito.fanara.com.br/"
AVISO = "Medição automática por IA nas câmeras públicas da NitTrans, ainda sem conferência."
LIMITE_TITULO = 240  # cabe num post de rede social com o link


def _resumo_curto(periodo):
    pesadas = [c for c in periodo["cameras"] if c["com_base"] and c["minutos_pesado"]]
    if not pesadas:
        if any(c["com_base"] for c in periodo["cameras"]):
            return "sem trânsito acima do habitual nos pontos medidos"
        return "ainda sem base para comparar com o habitual"
    pior = max(pesadas, key=lambda c: c["minutos_pesado"])
    texto = (
        f"trânsito acima do habitual na {pior['nome']} por {pior['minutos_pesado']} min"
        f" (pior às {_hora_local(pior['pior_utc'])})"
    )
    outros = len(pesadas) - 1
    if outros:
        texto += f" e em mais {outros} ponto" + ("s" if outros > 1 else "")
    return texto


def itens_feed(periodos_lista, ocorrencias, agora_utc):
    """Textos prontos para publicar: um por período encerrado e um por ocorrência
    publicável. Cada item tem id estável (o mesmo período não vira dois posts)."""
    agora = _dt(agora_utc)
    nomes = {c: cfg["nome"] for c, cfg in CAMERAS.items()}
    itens = []
    for p in periodos_lista:
        if agora - _dt(p["fim_utc"]) <= timedelta(minutes=RECENTE_MIN):
            continue  # período ainda em andamento
        dia = p["dia"].capitalize() if p["dia"] in ("hoje", "ontem") else f"Em {p['dia']}"
        titulo = (
            f"Saída da Ponte, Niterói. {dia}, das {_hora_local(p['inicio_utc'])} às"
            f" {_hora_local(p['fim_utc'])}: {_resumo_curto(p)}."
        )
        itens.append(
            {
                "id": f"periodo-{p['inicio_utc']}",
                "quando": p["fim_utc"],
                "titulo": titulo[:LIMITE_TITULO],
                "texto": f"{p['frase']} {AVISO}",
            }
        )
    for o in ocorrencias:
        tipo = TIPO_TEXTO.get(o["tipo"], o["tipo"]).lower()
        titulo = (
            f"Possível {tipo} em {nomes.get(o['camera'], o['camera'])}, Niterói,"
            f" desde {_hora_local(o['inicio_utc'])} (classificação automática, não confirmada)."
        )
        itens.append(
            {
                "id": f"ocorrencia-{o['camera']}-{o['inicio_utc']}",
                "quando": o["inicio_utc"],
                "titulo": titulo[:LIMITE_TITULO],
                "texto": f"{o['descricao']} {AVISO}",
            }
        )
    return sorted(itens, key=lambda i: i["quando"], reverse=True)[:30]


def feed(periodos_lista, ocorrencias, agora_utc):
    """RSS 2.0 com os itens de itens_feed. Serviços como Buffer, IFTTT ou Zapier leem o
    RSS e publicam nas redes sociais; o projeto não guarda senha de rede social."""
    from email.utils import format_datetime
    from xml.etree import ElementTree as ET

    rss = ET.Element("rss", version="2.0")
    canal = ET.SubElement(rss, "channel")
    for tag, valor in (
        ("title", "Trânsito na saída da Ponte, Niterói"),
        ("link", SITE),
        ("description", "Resumo de cada período medido nas câmeras públicas da NitTrans. " + AVISO),
        ("language", "pt-BR"),
        ("lastBuildDate", format_datetime(_dt(agora_utc))),
    ):
        ET.SubElement(canal, tag).text = valor
    for item in itens_feed(periodos_lista, ocorrencias, agora_utc):
        el = ET.SubElement(canal, "item")
        ET.SubElement(el, "title").text = item["titulo"]
        ET.SubElement(el, "link").text = SITE
        ET.SubElement(el, "description").text = item["texto"]
        ET.SubElement(el, "guid", isPermaLink="false").text = item["id"]
        ET.SubElement(el, "pubDate").text = format_datetime(_dt(item["quando"]))
    return ET.tostring(rss, encoding="unicode", xml_declaration=True)


def csv_por_hora(db):
    """Dados abertos: uma linha por câmera e hora (de Niterói), com toda a história do banco,
    os veículos por tipo e sentido, a ocupação média e a chuva daquela hora.
    ponytail: hora local por deslocamento fixo de -3 h (o Brasil não tem horário de verão
    desde 2019); se voltar, trocar por conversão com fuso."""
    import csv
    import io

    criar_tabela_clima(db)
    somas = ", ".join(f"SUM(c.{col})" for col in COLUNAS)
    linhas = db.execute(
        "SELECT strftime('%Y-%m-%d %H:00', c.clipe_utc, '-3 hours') AS hora_local, c.camera,"
        f" ROUND(SUM(c.duracao_s) / 60.0, 1), {somas},"
        " COALESCE(substr(c.modelo, 1, instr(c.modelo || '@', '@') - 1), '') || ' '"
        " || COALESCE(c.detector, '')"
        " || CASE WHEN c.linha IS NULL THEN '' ELSE ' linha ' || c.linha END,"
        " ROUND(AVG(c.ocupacao), 2), MAX(k.chuva_mm)"
        " FROM clipes c LEFT JOIN clima k"
        " ON k.hora_utc = strftime('%Y-%m-%dT%H:00:00', c.clipe_utc) || '+00:00'"
        " GROUP BY hora_local, c.camera, c.modelo, c.detector, c.linha"
        " ORDER BY hora_local, c.camera"
    ).fetchall()
    nomes = {cam["id"]: cam["nome"] for cam in REGIAO}
    saida = io.StringIO()
    w = csv.writer(saida, lineterminator=chr(10))
    w.writerow(
        [
            "hora_niteroi",
            "camera",
            "nome",
            "minutos_de_video",
            *COLUNAS,
            "deteccao",
            "ocupacao_media",
            "chuva_mm",
        ]
    )
    for hora_local, cam, minutos, *resto in linhas:
        w.writerow([hora_local, cam, nomes.get(cam, cam), minutos, *resto])
    return saida.getvalue()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--banco", default="fluxo.db")
    ap.add_argument("--saida", default=str(SAIDA))
    ap.add_argument("--enviar", help="destino scp, ex.: hostgator-fanara:transito.fanara.com.br")
    args = ap.parse_args()
    print(exportar(args.banco, args.saida, args.enviar), "clipes exportados")
