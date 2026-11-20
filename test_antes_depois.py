from datetime import UTC, date, datetime, timedelta

from antes_depois import comparar, ler_intervencoes

INTERV = {
    "data": date(2026, 12, 10),  # quinta-feira
    "camera": "000018",
    "tipo": "semaforo",
    "descricao": "Ciclo maior",
    "fonte": "teste",
}
HOJE = date(2026, 12, 30)


def _clipes(dias, horas, ocupacao, desce=20, camera="000018"):
    """Um clipe de 60 s por dia (deslocamento em dias a partir da intervenção) e hora local
    (Niterói = UTC-3), com 10 clipes por hora para passar do mínimo de minutos."""
    saida = []
    for d in dias:
        dia = INTERV["data"] + timedelta(days=d)
        for h in horas:
            for m in range(10):
                utc = datetime(dia.year, dia.month, dia.day, h, m, tzinfo=UTC) + timedelta(hours=3)
                saida.append(
                    {
                        "camera": camera,
                        "clipe_utc": utc.isoformat(),
                        "duracao_s": 60.0,
                        "ocupacao": ocupacao,
                        "desce": desce,
                        "sobe": 10,
                    }
                )
    return saida


HORAS = range(6, 20)  # 14 horas de dia útil


def test_queda_de_ocupacao_depois_da_intervencao():
    clipes = _clipes([-7, -1], HORAS, 6.0) + _clipes([1, 6], HORAS, 4.5)
    r = comparar(clipes, {}, INTERV, HOJE)
    assert r["situacao"] == "pronto" and r["horas_comparaveis"] == 14
    assert r["ocupacao"] == {"antes": 6.0, "depois": 4.5, "variacao_pct": -25}
    assert r["frase"].startswith("Depois da mudança, a ocupação média caiu 25% (de 6.0 para 4.5")


def test_dia_da_intervencao_outra_camera_e_chuva_ficam_de_fora():
    clipes = (
        _clipes([-1], HORAS, 6.0)
        + _clipes([0], HORAS, 99.0)  # o próprio dia não entra
        + _clipes([1], HORAS, 4.5)
        + _clipes([1], HORAS, 99.0, camera="000026")
    )
    # chuva às 10h locais do dia seguinte: essa hora some só do lado "depois"
    dia1 = INTERV["data"] + timedelta(days=1)
    chuva = {f"{dia1.isoformat()}T13:00:00+00:00": 3.0}
    r = comparar(clipes, chuva, INTERV, HOJE)
    assert r["horas_comparaveis"] == 13
    assert r["ocupacao"]["depois"] == 4.5


def test_poucas_horas_fica_aguardando():
    clipes = _clipes([-1], range(7, 10), 6.0) + _clipes([1], range(7, 10), 4.5)
    r = comparar(clipes, {}, INTERV, date(2026, 12, 12))
    assert r["situacao"] == "aguardando" and r["horas_comparaveis"] == 3
    assert r["dias_depois"] == 2
    assert "3 de 12 horas" in r["frase"]


def test_ler_registro(tmp_path):
    arq = tmp_path / "intervencoes.csv"
    arq.write_text(
        "data;camera;tipo;descricao;fonte\n2026-12-10;000018;semaforo;Ciclo maior;NitTrans\n\n",
        encoding="utf-8",
    )
    (i,) = ler_intervencoes(arq)
    assert i["data"] == date(2026, 12, 10) and i["camera"] == "000018"
    assert ler_intervencoes(tmp_path / "nao-existe.csv") == []
