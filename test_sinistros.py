import io
import zipfile

from sinistros import ler_nittrans, ler_prf, montar, trechos

CABECALHO = (
    '"id";"data_inversa";"br";"km";"municipio";"mortos";"feridos_graves";"latitude";"longitude"'
)


def _zip(pasta, ano, linhas):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"datatran{ano}.csv", "\n".join([CABECALHO, *linhas]).encode("latin-1"))
    (pasta / f"datatran{ano}.zip").write_bytes(buf.getvalue())


def test_le_so_niteroi_e_descarta_coordenada_fora():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        _zip(
            pasta,
            2025,
            [
                "1;2025-03-18;101;321;NITEROI;1;0;-22,8679;-43,1109",
                "2;2025-03-19;101;321,5;NITERÓI;0;2;0;0",  # coordenada zerada
                "3;2025-03-19;101;300;SAO GONCALO;5;5;-22,8;-43,0",
            ],
        )
        regs = ler_prf(pasta)
    assert [(r["km"], r["mortos"], r["feridos_graves"]) for r in regs] == [(321, 1, 0), (321, 0, 2)]
    assert regs[0]["lat"] == -22.8679 and regs[1]["lat"] is None


def test_trechos_ordenados_por_gravidade():
    regs = [
        {"br": "101", "km": 322, "mortos": 0, "feridos_graves": 1, "lat": -22.88, "lon": -43.11},
        {"br": "101", "km": 322, "mortos": 0, "feridos_graves": 0, "lat": -22.88, "lon": -43.11},
        {"br": "101", "km": 322, "mortos": 0, "feridos_graves": 0, "lat": None, "lon": None},
        {"br": "101", "km": 321, "mortos": 1, "feridos_graves": 1, "lat": -22.87, "lon": -43.11},
    ]
    t = trechos(regs)
    assert [x["nome"] for x in t] == ["BR-101, km 321", "BR-101, km 322"]
    assert (t[1]["sinistros"], t[1]["graves"], t[1]["lat"]) == (3, 1, -22.88)


def test_categorias_e_grupos_para_o_filtro():
    from sinistros import categoria

    assert categoria("Colisão traseira") == categoria("Engavetamento") == "colisao"
    assert categoria("Queda de ocupante de veículo") == "queda"
    assert categoria("Atropelamento de Pedestre") == "atropelamento"
    assert categoria("Saída de leito carroçável") == categoria("Tombamento") == "tombamento"
    assert categoria("Incêndio") == categoria("") == "outros"

    def r(cat, mortos=0, graves=0, feridos=0):
        return {
            "br": "101",
            "km": 321,
            "lat": -22.87,
            "lon": -43.11,
            "categoria": cat,
            "mortos": mortos,
            "feridos_graves": graves,
            "feridos": feridos,
        }

    (t,) = trechos(
        [
            r("colisao"),
            r("colisao", feridos=2),
            r("queda", mortos=1),
            r("queda", graves=1, feridos=1),
        ]
    )
    assert t["grupos"]["colisao"] == {
        "n": 2,
        "vitimas": 1,
        "fatais": 0,
        "mortos": 0,
        "feridos_graves": 0,
    }
    assert t["grupos"]["queda"] == {
        "n": 2,
        "vitimas": 2,
        "fatais": 1,
        "mortos": 1,
        "feridos_graves": 1,
    }


def test_transcricao_da_nittrans_soma_certo():
    vias = ler_nittrans()
    assert len(vias) == 30 and vias[1]["via"] == "Alameda São Boaventura"
    assert all(v["2024"] + v["2025"] + v["2026"] == v["total"] for v in vias)
    dados = montar([], vias)
    assert dados["prf"]["trechos"] == [] and dados["nittrans"]["vias"][0]["total"] == 819


def test_descarta_km_e_coordenada_incoerentes():
    from sinistros import coerentes

    def r(br, km, lat, lon):
        return {"br": br, "km": km, "lat": lat, "lon": lon, "mortos": 0, "feridos_graves": 0}

    bons = [r("101", 322, -22.879, -43.1116) for _ in range(5)]
    km_errado = r("101", 307, -22.8917, -43.1227)  # o caso real do mapa
    rodovia_errada = r("40", 322, -22.879, -43.1116)
    longe = r("101", 322, -22.95, -43.05)  # km certo, coordenada a ~10 km
    ok, fora = coerentes([*bons, km_errado, rodovia_errada, longe])
    assert len(ok) == 5
    assert fora == [km_errado, rodovia_errada, longe]
