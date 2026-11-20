"""Pontos críticos de sinistros em Niterói a partir de duas fontes públicas.

1. PRF, dados abertos (boletins de acidente das rodovias federais, com coordenadas e
   vítimas): cobre só a BR-101 e a Ponte dentro de Niterói. Os ZIPs por ano ficam em
   dados-prf/ (baixados de gov.br/prf, "Acidentes - agrupados por ocorrência").
2. NitTrans, "Vias com maior incidência de sinistros de trânsito" (tabela publicada só como
   imagem em nittrans.niteroi.rj.gov.br/estatisticas-e-estudos, outubro de 2026), transcrita
   à mão em dados-externos/nittrans_vias_sinistros.csv. Conta quantidade, não gravidade.

Uso:  uv run sinistros.py    grava painel/public/sinistros.json
"""

import csv
import io
import json
import zipfile
from pathlib import Path

PASTA_PRF = Path("dados-prf")
NITTRANS = Path("dados-externos/nittrans_vias_sinistros.csv")
SAIDA = Path("painel/public/sinistros.json")
# Retângulo de Niterói: descarta coordenada errada no boletim.
LAT, LON = (-23.0, -22.83), (-43.16, -42.95)


def _num(texto):
    try:
        return float(texto.replace(",", "."))
    except (AttributeError, ValueError):
        return None


def ler_prf(pasta=PASTA_PRF):
    """Boletins de Niterói de todos os ZIPs da pasta, com campos já convertidos."""
    registros = []
    for arq in sorted(pasta.glob("datatran*.zip")):
        with zipfile.ZipFile(arq) as z:
            texto = z.read(z.namelist()[0]).decode("latin-1")
        for r in csv.DictReader(io.StringIO(texto), delimiter=";"):
            if not r["municipio"].upper().startswith("NITER"):
                continue
            lat, lon = _num(r["latitude"]), _num(r["longitude"])
            registros.append(
                {
                    "ano": int(r["data_inversa"][:4]),
                    "br": r["br"],
                    "km": int(_num(r["km"]) or 0),
                    "mortos": int(r["mortos"] or 0),
                    "feridos_graves": int(r["feridos_graves"] or 0),
                    "lat": lat if lat and LAT[0] <= lat <= LAT[1] else None,
                    "lon": lon if lon and LON[0] <= lon <= LON[1] else None,
                }
            )
    return registros


# Trecho da BR-101 dentro de Niterói em que km e coordenadas formam um caminho coerente
# (km 317 na divisa com São Gonçalo, 321-322 no acesso à Ponte, 327 sobre a Ponte).
KM_VALIDOS = range(317, 328)
DISTANCIA_MAX_KM = 1.5  # da posição típica do quilômetro


def _dist_km(a, b):
    """Distância aproximada em km entre (lat, lon) próximos (projeção plana local)."""
    import math

    dy = (a[0] - b[0]) * 111.0
    dx = (a[1] - b[1]) * 111.0 * math.cos(math.radians(a[0]))
    return (dx * dx + dy * dy) ** 0.5


def coerentes(registros):
    """Separa os boletins que podem ir ao mapa e ao ranking dos que têm rodovia, km ou
    coordenada incompatível com o trecho de Niterói (erros de digitação na base da PRF,
    como "BR-101, km 307" com coordenada no Centro). Devolve (coerentes, descartados)."""
    from statistics import median

    candidatos = [
        r for r in registros if r["br"] == "101" and r["km"] in KM_VALIDOS and r["lat"] and r["lon"]
    ]
    tipico = {}
    for km in {r["km"] for r in candidatos}:
        g = [r for r in candidatos if r["km"] == km]
        tipico[km] = (median(r["lat"] for r in g), median(r["lon"] for r in g))
    ok = [
        r for r in candidatos if _dist_km((r["lat"], r["lon"]), tipico[r["km"]]) <= DISTANCIA_MAX_KM
    ]
    ids = {id(r) for r in ok}
    return ok, [r for r in registros if id(r) not in ids]


def trechos(registros):
    """Agrupa por rodovia e quilômetro e ordena por gravidade: mortos mais feridos graves
    (o indicador internacional KSI), depois mortos, depois número de sinistros."""
    grupos = {}
    for r in registros:
        grupos.setdefault((r["br"], r["km"]), []).append(r)
    saida = []
    for (br, km), g in grupos.items():
        coords = [(r["lat"], r["lon"]) for r in g if r["lat"] and r["lon"]]
        mortos = sum(r["mortos"] for r in g)
        graves = sum(r["feridos_graves"] for r in g)
        saida.append(
            {
                "nome": f"BR-{br}, km {km}",
                "sinistros": len(g),
                "mortos": mortos,
                "feridos_graves": graves,
                "graves": mortos + graves,
                "lat": round(sum(c[0] for c in coords) / len(coords), 5) if coords else None,
                "lon": round(sum(c[1] for c in coords) / len(coords), 5) if coords else None,
            }
        )
    return sorted(saida, key=lambda t: (-t["graves"], -t["mortos"], -t["sinistros"]))


def ler_nittrans(caminho=NITTRANS):
    with caminho.open(encoding="utf-8", newline="") as f:
        return [
            {
                "via": r["via"],
                **{k: int(r[k]) for k in ("2024", "2025", "2026", "total")},
            }
            for r in csv.DictReader(f, delimiter=";")
        ]


def montar(registros, vias):
    anos = sorted({r["ano"] for r in registros})
    ok, descartados = coerentes(registros)
    return {
        "prf": {
            "fonte": "PRF, dados abertos de acidentes (gov.br/prf)",
            "anos": [anos[0], anos[-1]] if anos else [],
            "total_sinistros": len(registros),
            "total_mortos": sum(r["mortos"] for r in registros),
            "total_feridos_graves": sum(r["feridos_graves"] for r in registros),
            "fora_do_mapa": len(descartados),
            "trechos": trechos(ok),
        },
        "nittrans": {
            "fonte": "NitTrans, Estatísticas e Estudos: vias com maior incidência de"
            " sinistros (tabela em imagem, out/2026, transcrita)",
            "url": "https://nittrans.niteroi.rj.gov.br/estatisticas-e-estudos/",
            "vias": vias,
        },
    }


if __name__ == "__main__":
    dados = montar(ler_prf(), ler_nittrans())
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    p = dados["prf"]
    print(
        p["anos"],
        p["total_sinistros"],
        "sinistros,",
        p["total_mortos"],
        "mortos,",
        p["total_feridos_graves"],
        "feridos graves;",
        len(p["trechos"]),
        "trechos",
    )
    for t in p["trechos"][:8]:
        print(" ", t)
