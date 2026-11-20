"""Dados de leitura rápida do painel: situação, ônibus, câmeras no ar e veredito."""

import sqlite3
import urllib.error

from coletor import REGIAO, checar_cameras
from exportar import cameras_no_ar, montar, onibus, periodos, situacao, veredito

AGORA = "2026-11-19T21:00:00+00:00"  # 18h em Niterói


def _clipe(camera, minutos_atras, ocupacao=2.0, onibus=0, duracao=60.0):
    h, m = divmod(21 * 60 - minutos_atras, 60)
    return {
        "camera": camera,
        "clipe_utc": f"2026-11-19T{h:02d}:{m:02d}:00+00:00",
        "duracao_s": duracao,
        "ocupacao": ocupacao,
        "onibus": onibus,
        "desce": 0,
        "sobe": 0,
    }


def _base_mesma_hora(camera="000018", dias=3):
    """O habitual daquele dia e hora: 13 clipes por dia, às 17h de Niterói (20h UTC), nos
    `dias` dias úteis anteriores a AGORA (quinta 19/11), ocupação de 1 a 13 × dias."""
    saida, k = [], 0
    for dia in (18, 17, 16)[:dias]:
        for m in range(13):
            k += 1
            saida.append(
                {
                    **_clipe(camera, 0, ocupacao=float(k)),
                    "clipe_utc": f"2026-11-{dia}T20:{m:02d}:00+00:00",
                }
            )
    return saida


def _historico(camera="000018", dias=3, agora_ocup=None):
    """A base do mesmo dia e hora (3 dias úteis) e, se pedido, um clipe agora (17h58 local)."""
    hist = _base_mesma_hora(camera, dias)
    if agora_ocup is not None:
        hist.append(_clipe(camera, 2, ocupacao=agora_ocup))
    return hist


def test_situacao_compara_com_o_mesmo_dia_e_hora_da_propria_camera():
    # abaixo (até o percentil 15), dentro, acima (além do percentil 85) do habitual
    assert situacao(_historico(agora_ocup=3.0), AGORA)["000018"]["nivel"] == "livre"
    assert situacao(_historico(agora_ocup=20.0), AGORA)["000018"]["nivel"] == "moderado"
    assert situacao(_historico(agora_ocup=39.5), AGORA)["000018"]["nivel"] == "pesado"


def test_situacao_nao_mistura_hora_do_dia_nem_tipo_de_dia():
    # a base é só das 17h; às 3h da manhã (outro horário) ou num sábado, não há base
    madrugada = {**_clipe("000018", 2, ocupacao=39.5), "clipe_utc": "2026-11-19T06:00:00+00:00"}
    sabado = {**_clipe("000018", 2, ocupacao=39.5), "clipe_utc": "2026-11-21T20:58:00+00:00"}
    for clipe, agora in (
        (madrugada, "2026-11-19T06:01:00+00:00"),
        (sabado, "2026-11-21T21:00:00+00:00"),
    ):
        assert situacao(_base_mesma_hora() + [clipe], agora)["000018"]["nivel"] == "sem_historico"


def test_situacao_sem_medicao_recente_ou_sem_historico():
    assert situacao(_historico(), AGORA)["000018"]["nivel"] == "sem_dado_recente"
    dois_dias = _historico(dias=2, agora_ocup=3.0)  # só 2 dias: um dia a menos que o mínimo
    assert situacao(dois_dias, AGORA)["000018"]["nivel"] == "sem_historico"


def test_onibus_por_hora_e_intervalo():
    hist = [_clipe("000018", m, onibus=1) for m in range(0, 20)]  # 20 min, 20 ônibus
    r = onibus(hist, AGORA)["000018"]
    assert (r["por_hora"], r["intervalo_min"], r["minutos_video"]) == (60, 1.0, 20)
    assert "000018" not in onibus(hist[:5], AGORA)  # 5 min de vídeo é pouco


def test_cameras_no_ar_por_estado():
    estados = {
        "000025": ("2026-11-19T20:58:00+00:00", 200, "2026-11-19T20:57:00+00:00"),
        "000019": ("2026-11-19T20:58:00+00:00", 500, "2026-11-19T12:00:00+00:00"),
        "000021": ("2026-11-19T20:58:00+00:00", 200, "2026-11-19T20:00:00+00:00"),
        "000026": ("2026-11-19T19:00:00+00:00", 200, "2026-11-19T19:00:00+00:00"),
    }
    r = {c["id"]: c for c in cameras_no_ar(estados, AGORA)}
    assert [r[i]["estado"] for i in ("000025", "000019", "000021", "000026", "000017")] == [
        "no_ar",
        "fora",
        "parada",
        "sem_verificacao",
        "sem_verificacao",
    ]
    assert r["000018"]["contada"] and not r["000025"]["contada"]
    assert len(r) == len(REGIAO) == 7


def test_veredito():
    sit_pesado = {"000018": {"nivel": "pesado", "percentil": 95}}
    sit_livre = {"000018": {"nivel": "livre", "percentil": 30}}
    recente = "2026-11-19T20:58:00+00:00"
    enguico = {
        "camera": "000018",
        "tipo": "enguico",
        "inicio_utc": "2026-11-19T20:40:00+00:00",
        "fim_utc": recente,
    }
    assert veredito(sit_livre, [], None, AGORA) == {
        "nivel": "pausado",
        "texto": "Ainda não há medição.",
    }
    periodo = {
        "dia": "hoje",
        "inicio_utc": "2026-11-19T09:30:00+00:00",
        "fim_utc": "2026-11-19T12:29:00+00:00",
        "frase": "Jansen x Mal. Deodoro: acima do habitual por 40 min (pior às 08h15).",
    }
    v = veredito(sit_livre, [], "2026-11-19T12:29:00+00:00", AGORA, periodo)
    assert v == {
        "nivel": "pausado",
        "texto": "Último período medido: hoje, das 06h30 às 09h29.",
        "detalhe": "Jansen x Mal. Deodoro: acima do habitual por 40 min (pior às 08h15).",
    }
    assert veredito(sit_livre, [], recente, AGORA) == {
        "nivel": "ok",
        "texto": "Trânsito dentro do habitual ou abaixo nos pontos medidos.",
    }
    assert veredito(sit_pesado, [], recente, AGORA) == {
        "nivel": "atencao",
        "texto": "Trânsito acima do habitual em Jansen x Mal. Deodoro.",
    }
    v = veredito(sit_pesado, [enguico], recente, AGORA)
    assert v["nivel"] == "alerta"
    assert v["texto"].startswith("Veículo enguiçado em Jansen x Mal. Deodoro desde 17h40.")
    sem_hist = {"000018": {"nivel": "sem_historico"}}
    v = veredito(sem_hist, [], recente, AGORA)
    assert v["nivel"] == "sem_base" and "faltam dias de coleta" in v["texto"]


def test_montar_inclui_os_blocos_novos():
    d = montar([_clipe("000018", 1)], AGORA, historico=_historico(agora_ocup=5.0))
    assert {"veredito", "situacao", "onibus", "regiao"} <= d.keys()


def test_checar_cameras_grava_uma_linha_por_camera():
    def cabecalho(camera):
        if camera == "000019":
            raise urllib.error.HTTPError("u", 500, "erro", {}, None)
        if camera == "000021":
            raise TimeoutError
        return 200, "2026-11-19T20:59:00+00:00"

    db = sqlite3.connect(":memory:")
    checar_cameras(db, AGORA, cabecalho)
    linhas = dict(db.execute("SELECT camera, http FROM estado_cameras"))
    assert len(linhas) == 7 and linhas["000019"] == 500 and linhas["000021"] == 0
    assert linhas["000018"] == 200


def test_periodos_separa_coletas_e_resume_cada_uma():
    base = _base_mesma_hora()  # 3 dias úteis às 17h, ocupação de 1 a 39
    hoje = [_clipe("000018", m, ocupacao=39.0 if m <= 10 else 2.0) for m in range(1, 31)]
    pers = periodos(base + hoje, [], AGORA)
    assert len(pers) == 4  # um período por dia de base e o de hoje
    p = pers[0]  # mais recente primeiro
    assert p["dia"] == "hoje" and p["fim_utc"] == "2026-11-19T20:59:00+00:00"
    (cam,) = p["cameras"]
    # o fim de hoje (ocupação 39) é acima do habitual das 17h; o começo (2,0) não
    assert cam["faixa"][-1] == "pesado" and cam["faixa"][0] != "pesado"
    assert cam["minutos_pesado"] == 10  # os 10 últimos minutos, 2 baldes de 5
    assert p["frase"].startswith("Jansen x Mal. Deodoro: acima do habitual por 10 min (pior às 17h")


def test_periodos_conta_ocorrencias_e_avisa_sem_historico():
    curto = [_clipe("000018", m) for m in range(1, 6)]
    enguico = {
        "inicio_utc": "2026-11-19T20:57:00+00:00",
        "fim_utc": "2026-11-19T20:59:00+00:00",
    }
    (p,) = periodos(curto, [enguico], AGORA)
    assert p["ocorrencias"] == 1
    assert p["frase"] == (
        "Jansen x Mal. Deodoro: ainda sem base para comparar com este dia e horário; 1 ocorrência."
    )
    assert set(p["cameras"][0]["faixa"]) == {None}


def _periodo(fim_utc, minutos_pesado=15):
    return {
        "inicio_utc": "2026-11-19T10:14:00+00:00",
        "fim_utc": fim_utc,
        "dia": "hoje",
        "frase": "Jansen x Mal. Deodoro: pesado por 15 min (pior às 07h25).",
        "cameras": [
            {
                "nome": "Jansen x Mal. Deodoro",
                "com_base": True,
                "minutos_pesado": minutos_pesado,
                "pior_utc": "2026-11-19T10:25:00+00:00",
            }
        ],
    }


def test_itens_feed_so_periodos_encerrados_e_ocorrencias():
    from exportar import itens_feed

    encerrado = _periodo("2026-11-19T12:29:00+00:00")
    andando = {**_periodo("2026-11-19T20:58:00+00:00"), "inicio_utc": "2026-11-19T20:00:00+00:00"}
    enguico = {
        "camera": "000018",
        "tipo": "enguico",
        "inicio_utc": "2026-11-19T11:00:00+00:00",
        "descricao": "Carro parado na faixa.",
    }
    itens = itens_feed([andando, encerrado], [enguico], AGORA)
    assert [i["id"] for i in itens] == [
        "periodo-2026-11-19T10:14:00+00:00",
        "ocorrencia-000018-2026-11-19T11:00:00+00:00",
    ]
    assert itens[0]["titulo"] == (
        "Saída da Ponte, Niterói. Hoje, das 07h14 às 09h29: trânsito acima do habitual na"
        " Jansen x Mal. Deodoro por 15 min (pior às 07h25)."
    )
    assert "não confirmada" in itens[1]["titulo"]
    assert all(len(i["titulo"]) <= 240 for i in itens)
    sem = itens_feed([_periodo("2026-11-19T12:29:00+00:00", 0)], [], AGORA)
    assert sem[0]["titulo"].endswith("sem trânsito acima do habitual nos pontos medidos.")


def test_feed_e_rss_valido():
    from xml.etree import ElementTree as ET

    from exportar import feed

    xml = feed([_periodo("2026-11-19T12:29:00+00:00")], [], AGORA)
    canal = ET.fromstring(xml).find("channel")  # noqa: S314 - XML gerado pelo próprio teste
    (item,) = canal.findall("item")
    assert item.find("guid").text == "periodo-2026-11-19T10:14:00+00:00"
    assert item.find("pubDate").text.endswith("+0000")


def test_periodos_cortados_em_blocos_de_3_horas():
    # coleta contínua das 17h30 às 18h29 (Niterói): vira dois blocos, 15h-18h e 18h-21h
    continuo = [_clipe("000018", m) for m in range(-29, 31)]
    pers = periodos(continuo, [], "2026-11-19T22:00:00+00:00")
    assert [p["inicio_utc"][11:16] for p in pers] == ["21:00", "20:30"]


def test_passagens_batem_com_contar():
    from coletor import contar, passagens

    linha = ((100, 300), (500, 300))
    hist = {
        1: [(0, 200, 280, 40, 30), (10, 200, 310, 40, 30), (20, 200, 330, 40, 30)],
        2: [(5, 300, 320, 20, 20), (15, 300, 290, 20, 20)],
        3: [(0, 700, 280, 40, 30), (10, 700, 320, 40, 30)],  # fora do segmento
    }
    classes = {1: "carro", 2: "moto", 3: "onibus"}
    lista = passagens(hist, classes, linha, fps=10)
    assert [x[:3] for x in lista] == [(1.0, "carro", "desce"), (1.5, "moto", "sobe")]
    # carro: 50 px em 2 s, caixa de 30 px de altura = 0,83 alturas por segundo
    assert lista[0][3] == round(50 / 30 / 2, 2)
    traj = {t: (classes[t], [(x, y) for _, x, y, _, _ in pts]) for t, pts in hist.items()}
    assert len(lista) == sum(contar(traj, linha).values())


def test_clima_grava_so_horas_passadas():
    from historia import atualizar_clima

    resposta = {
        "hourly": {
            "time": ["2026-11-19T19:00", "2026-11-19T20:00", "2026-11-19T22:00"],
            "precipitation": [0.0, 2.5, 9.9],
            "temperature_2m": [25.0, 23.1, 20.0],
        }
    }
    db = sqlite3.connect(":memory:")
    assert atualizar_clima(db, AGORA, lambda: resposta) == 2
    assert db.execute("SELECT hora_utc, chuva_mm FROM clima ORDER BY 1").fetchall() == [
        ("2026-11-19T19:00:00+00:00", 0.0),
        ("2026-11-19T20:00:00+00:00", 2.5),
    ]


def test_csv_por_hora_soma_por_camera_e_junta_a_chuva():
    from coletor import abrir_banco, gravar
    from exportar import csv_por_hora
    from historia import atualizar_clima

    db = abrir_banco(":memory:")
    from collections import Counter

    for minuto, carros in ((5, 10), (6, 4)):
        gravar(
            db,
            "000018",
            f"2026-11-19T20:{minuto:02d}:00+00:00",
            60,
            3.0,
            Counter(carro_desce=carros),
        )
    resposta = {
        "hourly": {"time": ["2026-11-19T20:00"], "precipitation": [2.5], "temperature_2m": [23.0]}
    }
    atualizar_clima(db, AGORA, lambda: resposta)
    cabecalho, linha = csv_por_hora(db).strip().split(chr(10))
    assert cabecalho.startswith("hora_niteroi,camera,nome,minutos_de_video,carro_desce")
    campos = linha.split(",")
    assert campos[:5] == ["2026-11-19 17:00", "000018", "Jansen x Mal. Deodoro", "2.0", "14"]
    assert campos[-1] == "2.5"


def test_copia_do_banco_usa_so_o_host(tmp_path):
    from historia import copiar_banco

    banco = tmp_path / "fluxo.db"
    sqlite3.connect(banco).execute("CREATE TABLE t (x)")
    comandos = []
    destino = copiar_banco(
        banco, "servidor:pasta/site", "2026-11-19", lambda cmd, **_: comandos.append(cmd)
    )
    assert destino == "servidor:backup-transito/fluxo-2026-11-19.db"
    assert comandos[0][-4:] == ["servidor", "mkdir", "-p", "backup-transito"]
    assert comandos[1][-1] == "servidor:backup-transito/"


def test_velocidade_relativa_independe_da_distancia_da_camera():
    from coletor import velocidade_relativa

    # mesmo carro, mesma velocidade real: longe (caixa e passo pequenos) e perto (grandes)
    longe = [(q, 400, 100 + 2 * q, 20, 15) for q in range(0, 21)]
    perto = [(q, 400, 300 + 4 * q, 40, 30) for q in range(0, 21)]
    assert velocidade_relativa(longe, 10, 10) == velocidade_relativa(perto, 10, 10)
    assert velocidade_relativa(longe[:2], 0, 10) is None  # janela curta demais


def test_resumos_por_janela():
    from exportar import resumos

    antigo = [  # 20 dias atrás, 40 clipes com ocupação de 1 a 40
        {**_clipe("000018", 0, ocupacao=m + 1.0), "clipe_utc": f"2026-10-30T12:{m:02d}:00+00:00"}
        for m in range(40)
    ]
    recente = [_clipe("000018", m, ocupacao=39.0 if m <= 10 else 2.0) for m in range(1, 31)]
    r = resumos(
        antigo + _base_mesma_hora() + recente,
        [{"inicio_utc": "2026-11-19T20:55:00+00:00"}],
        AGORA,
    )
    assert set(r) == {"7d", "30d", "total"}
    (c7,) = r["7d"]["cameras"]
    assert c7["horas_video"] == round(69 / 60, 1) and c7["pior_hora"] == 17  # 17h em Niterói
    assert c7["minutos_pesado"] == 10  # os 10 últimos minutos de hoje, acima do habitual das 17h
    assert 0 < c7["pct_pesado"] < 50 and c7["perfil"][3] is None  # 3h da manhã sem coleta
    assert r["7d"]["ocorrencias"] == 1 and r["7d"]["dias_com_dados"] == 4
    assert r["total"]["dias_com_dados"] == 5
    assert r["total"]["cameras"][0]["horas_video"] == round(109 / 60, 1)
