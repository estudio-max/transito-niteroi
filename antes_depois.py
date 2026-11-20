"""Antes e depois de intervenções na via (semáforo, faixa, lombada, obra, pintura...).

O registro fica em intervencoes.csv (separado por ";"), editável à mão:
    data;camera;tipo;descricao;fonte
    2026-12-01;000018;semaforo;Ciclo do semáforo passou de 90 s para 120 s;NitTrans, ofício 123

Para cada intervenção, compara a mesma câmera no mesmo tipo de dia (útil ou fim de semana)
e na mesma hora, nas JANELA_DIAS antes e depois, sem o dia da intervenção e sem as horas
com chuva. Só mostra resultado com MIN_HORAS horas comparáveis dos dois lados.
"""

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
JANELA_DIAS = 28
MIN_HORAS = 12  # horas (tipo de dia x hora) presentes antes e depois
MIN_MINUTOS = 10  # minutos de vídeo por hora, de cada lado, para a hora contar
CHUVA_MM = 0.5  # hora com chuva a partir disso fica de fora
TIPOS = {
    "semaforo": "mudança de semáforo",
    "faixa": "mudança de faixas",
    "lombada": "lombada ou redutor",
    "obra": "obra",
    "urbanismo_tatico": "urbanismo tático",
    "sinalizacao": "sinalização",
    "fiscalizacao": "fiscalização",
    "outro": "intervenção",
}


def ler_intervencoes(caminho="intervencoes.csv"):
    p = Path(caminho)
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return [
            {**linha, "data": date.fromisoformat(linha["data"].strip())}
            for linha in csv.DictReader(f, delimiter=";")
            if linha.get("data", "").strip()
        ]


def _local(utc):
    return datetime.fromisoformat(utc).astimezone(FUSO)


def _perfil(clipes):
    """{(dia_util, hora): {minutos, ocupacao, desce_h, sobe_h}} de uma lista de clipes."""
    grupos = {}
    for c in clipes:
        t = _local(c["clipe_utc"])
        grupos.setdefault((t.weekday() < 5, t.hour), []).append(c)
    perfil = {}
    for chave, g in grupos.items():
        dur = sum(c["duracao_s"] for c in g)
        perfil[chave] = {
            "minutos": dur / 60,
            "ocupacao": sum(c["ocupacao"] for c in g) / len(g),
            "desce_h": sum(c["desce"] for c in g) * 3600 / dur if dur else 0,
            "sobe_h": sum(c["sobe"] for c in g) * 3600 / dur if dur else 0,
        }
    return perfil


def _variacao(antes, depois):
    return round(100 * (depois - antes) / antes) if antes else None


def comparar(clipes, chuva, intervencao, hoje):
    """clipes: da câmera da intervenção, com camera, clipe_utc, duracao_s, ocupacao,
    desce, sobe. chuva: {hora_utc ISO: mm}. Devolve o resultado para o painel."""
    d0 = intervencao["data"]
    base = {
        "data": d0.isoformat(),
        "camera": intervencao["camera"],
        "tipo": TIPOS.get(intervencao["tipo"], intervencao["tipo"]),
        "descricao": intervencao["descricao"],
        "fonte": intervencao.get("fonte", ""),
    }
    secos = [
        c
        for c in clipes
        if chuva.get(c["clipe_utc"][:13] + ":00:00+00:00", 0) < CHUVA_MM
        and c["camera"] == intervencao["camera"]
    ]
    antes = [
        c for c in secos if d0 - timedelta(days=JANELA_DIAS) <= _local(c["clipe_utc"]).date() < d0
    ]
    depois = [
        c for c in secos if d0 < _local(c["clipe_utc"]).date() <= d0 + timedelta(days=JANELA_DIAS)
    ]
    pa, pd = _perfil(antes), _perfil(depois)
    comuns = sorted(
        k for k in pa.keys() & pd.keys() if min(pa[k]["minutos"], pd[k]["minutos"]) >= MIN_MINUTOS
    )
    base["dias_depois"] = max(0, min((hoje - d0).days, JANELA_DIAS))
    base["horas_comparaveis"] = len(comuns)
    if len(comuns) < MIN_HORAS:
        base["situacao"] = "aguardando"
        base["frase"] = (
            f"Aguardando dados: {len(comuns)} de {MIN_HORAS} horas comparáveis"
            f" (mesmo tipo de dia e horário, sem chuva) antes e depois."
        )
        return base

    def media(perfil, campo):
        return sum(perfil[k][campo] for k in comuns) / len(comuns)

    res = {
        campo: {"antes": round(media(pa, campo), 1), "depois": round(media(pd, campo), 1)}
        for campo in ("ocupacao", "desce_h", "sobe_h")
    }
    for v in res.values():
        v["variacao_pct"] = _variacao(v["antes"], v["depois"])
    base.update(situacao="pronto", **res)
    var = res["ocupacao"]["variacao_pct"]
    sentido = "caiu" if var is not None and var < 0 else "subiu"
    base["frase"] = (
        f"Depois da mudança, a ocupação média {sentido} {abs(var or 0)}%"
        f" (de {res['ocupacao']['antes']} para {res['ocupacao']['depois']} veículos por quadro),"
        f" em {len(comuns)} horas comparáveis: mesmo tipo de dia e horário, sem chuva."
    )
    return base


def avaliar(db, hoje, caminho="intervencoes.csv"):
    """Lê o registro e o banco e compara cada intervenção. Mais recente primeiro."""
    from coletor import SENTIDOS, VEICULOS

    intervencoes = ler_intervencoes(caminho)
    if not intervencoes:
        return []
    somas = ", ".join(
        f"{' + '.join(f'{v}_{s}' for v in VEICULOS.values())} AS {s}" for s in SENTIDOS
    )
    cur = db.execute(f"SELECT camera, clipe_utc, duracao_s, ocupacao, {somas} FROM clipes")
    nomes = [d[0] for d in cur.description]
    clipes = [dict(zip(nomes, linha, strict=True)) for linha in cur]
    try:
        chuva = dict(db.execute("SELECT hora_utc, chuva_mm FROM clima"))
    except Exception:  # banco antigo, sem a tabela de clima
        chuva = {}
    resultados = [comparar(clipes, chuva, i, hoje) for i in intervencoes]
    return sorted(resultados, key=lambda r: r["data"], reverse=True)
