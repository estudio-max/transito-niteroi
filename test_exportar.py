import json
from collections import Counter

from coletor import abrir_banco, gravar
from exportar import agregar, cobertura, exportar, ler, montar


def _clipe(camera, utc, desce=0, sobe=0, duracao=60.0, ocupacao=2.0):
    return {
        "camera": camera,
        "clipe_utc": utc,
        "duracao_s": duracao,
        "ocupacao": ocupacao,
        "desce": desce,
        "sobe": sobe,
    }


def test_agregar_soma_o_balde_e_converte_para_veiculos_por_hora():
    serie = agregar(
        [
            _clipe("000026", "2026-11-13T00:00:10+00:00", sobe=20, ocupacao=2.0),
            _clipe("000026", "2026-11-13T00:01:10+00:00", sobe=10, ocupacao=3.0),
        ]
    )
    assert len(serie) == 1
    assert serie[0]["000026_sobe_fluxo"] == 900  # 30 veículos em 120 s
    assert serie[0]["000026_desce_fluxo"] == 0
    assert serie[0]["000026_ocup"] == 2.5


def test_agregar_deixa_buraco_onde_nao_houve_coleta():
    serie = agregar(
        [
            _clipe("000026", "2026-11-13T00:00:10+00:00", sobe=20),
            _clipe("000026", "2026-11-13T00:16:10+00:00", sobe=20),
        ]
    )
    assert [("000026_sobe_fluxo" in p) for p in serie] == [True, False, False, True]
    assert serie[1]["t"] - serie[0]["t"] == 5 * 60 * 1000


def test_agregar_separa_cameras_e_aceita_vazio():
    serie = agregar(
        [
            _clipe("000026", "2026-11-13T00:00:10+00:00", sobe=20),
            _clipe("000018", "2026-11-13T00:00:40+00:00", desce=5, sobe=5),
        ]
    )
    assert serie[0]["000026_sobe_fluxo"] == 1200
    # sentidos opostos da mesma câmera ficam em séries separadas, não somados
    assert (serie[0]["000018_desce_fluxo"], serie[0]["000018_sobe_fluxo"]) == (300, 300)
    assert agregar([]) == []


def test_montar_resume_a_ultima_hora_coletada():
    dados = montar(
        [
            _clipe("000026", "2026-11-12T20:00:00+00:00", sobe=99),  # fora da última hora
            _clipe("000026", "2026-11-13T00:00:00+00:00", sobe=20),
            _clipe("000026", "2026-11-13T00:30:00+00:00", sobe=40),
        ],
        "2026-11-13T00:31:00+00:00",
    )
    r26 = next(r for r in dados["resumo"] if r["id"] == "000026")
    assert r26["clipes"] == 2
    assert r26["por_sentido"]["sobe"] == {"fluxo_h": 1800, "total": 159}  # total = 24 h
    assert r26["por_sentido"]["desce"] == {"fluxo_h": 0, "total": 0}
    r18 = next(r for r in dados["resumo"] if r["id"] == "000018")
    assert (r18["clipes"], r18["ocupacao"]) == (0, None)
    assert r18["por_sentido"]["desce"] == {"fluxo_h": None, "total": 0}
    assert dados["sentidos"]["desce"] == "da ponte para Icaraí"
    assert [c["sentido_confirmado"] for c in dados["cameras"]] == [False, True]
    assert dados["validado"] is False
    assert dados["ultimos"][0]["utc"] == "2026-11-13T00:30:00+00:00"
    assert (dados["total_veiculos"], dados["total_clipes"]) == (159, 3)
    assert dados["dispersao"][0] == {"c": "000026", "f": 5940, "o": 2.0}


def test_cobertura_por_dia_e_hora_no_fuso_de_niteroi():
    # 21:30 UTC de 12/11 = 18:30 em Niterói; 02:10 UTC de 13/11 = 23:10 do dia 12
    c = cobertura(
        ["2026-11-12T21:30:00+00:00"] * 4
        + ["2026-11-13T02:10:00+00:00"] * 2
        + ["2026-10-01T12:00:00+00:00"],  # fora dos 14 dias: ignorado
        "2026-11-13T12:00:00+00:00",
        cameras=2,
    )
    assert c["dias"][:2] == ["2026-11-13", "2026-11-12"] and len(c["dias"]) == 14
    assert c["minutos"][1][18] == 2 and c["minutos"][1][23] == 1
    assert sum(map(sum, c["minutos"])) == 3


def test_cobertura_limita_a_60_minutos():
    c = cobertura(["2026-11-13T12:00:00+00:00"] * 200, "2026-11-13T15:00:00+00:00", cameras=2)
    assert c["minutos"][0][9] == 60


def test_montar_sem_dados():
    dados = montar([], "2026-11-13T00:00:00+00:00")
    assert (dados["resumo"], dados["serie"], dados["ultimos"]) == ([], [], [])


def test_exportar_le_o_banco_e_grava_json(tmp_path):
    banco = tmp_path / "f.db"
    db = abrir_banco(banco)
    agora = __import__("datetime").datetime.now(__import__("datetime").UTC)
    gravar(db, "000026", agora.isoformat(), 60, 2.0, Counter(carro_sobe=18, moto_sobe=2))
    gravar(db, "000026", "2020-01-01T00:00:00+00:00", 60, 2.0, Counter(carro_sobe=5))  # antigo
    assert [c["sobe"] for c in ler(db, "2021-01-01")] == [20]
    db.close()
    saida = tmp_path / "pub" / "dados.json"
    assert exportar(banco, saida) == 1
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert dados["ultimos"][0]["fluxo_h"] == 1200
    assert dados["resumo"][0]["tipos"] == {"carro": 18, "moto": 2, "onibus": 0, "caminhao": 0}


def test_exportar_roda_como_script(tmp_path):
    """Regressão (19/11/2026): função definida depois do bloco __main__ quebrava a linha de
    comando, embora os testes que importam o módulo passassem."""
    import subprocess
    import sys

    banco = tmp_path / "fluxo.db"
    abrir_banco(banco).close()
    r = subprocess.run(  # noqa: S603
        [sys.executable, "exportar.py", "--banco", str(banco), "--saida", str(tmp_path / "d.json")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert (tmp_path / "d.json").exists() and (tmp_path / "feed.xml").exists()
    assert (tmp_path / "dados-por-hora.csv").exists()
