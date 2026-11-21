from argparse import Namespace
from collections import Counter

import pytest

import validar
from coletor import abrir_banco, gravar
from validar import (
    COLUNAS,
    TODOS,
    contada,
    erros,
    gravar_eventos,
    gravar_manual,
    ler_eventos,
    ler_manual,
    limpar,
    parear,
    sessao,
    totais,
)


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(validar, "PASTA", tmp_path)
    return tmp_path


def _linha(camera="000026", condicao="noite", auto=None, manual=None, pares=()):
    """auto, manual: {'carro_desce': n, ...}; o que faltar vale zero."""
    return {
        "camera": camera,
        "condicao": condicao,
        **{f"auto_{c}": (auto or {}).get(c, 0) for c in COLUNAS},
        **{f"manual_{c}": (manual or {}).get(c, 0) for c in COLUNAS},
        "pares": pares,
    }


def test_erro_total_tem_sinal_e_erro_medio_e_por_clipe():
    r = erros(
        [
            _linha(auto={"carro_sobe": 22}, manual={"carro_sobe": 20}),
            _linha(auto={"carro_sobe": 18}, manual={"carro_sobe": 20}),
        ]
    )
    e = r["000026", "noite", "sobe", "carro"]
    assert (e["clipes"], e["auto"], e["manual"]) == (2, 40, 40)
    assert e["erro_total"] == 0  # erros opostos se cancelam no total...
    assert abs(e["erro_medio_abs"] - 0.10) < 1e-9  # ...mas não no erro por clipe


def test_erro_positivo_quando_automatico_conta_a_mais():
    e = erros([_linha(auto={"carro_desce": 33}, manual={"carro_desce": 30})])
    assert abs(e["000026", "noite", "desce", "carro"]["erro_total"] - 0.10) < 1e-9


def test_manual_zero_nao_divide():
    e = erros([_linha(auto={"moto_desce": 2})])["000026", "noite", "desce", "moto"]
    assert e["erro_total"] is None and e["erro_medio_abs"] is None


def test_agrupa_por_camera_e_condicao():
    r = erros(
        [
            _linha(condicao="dia", auto={"carro_sobe": 10}, manual={"carro_sobe": 10}),
            _linha(camera="000018", auto={"carro_sobe": 5}, manual={"carro_sobe": 10}),
        ]
    )
    assert r["000026", "dia", "sobe", TODOS]["erro_total"] == 0
    assert r["000018", "noite", "sobe", TODOS]["erro_total"] == -0.5


def test_total_certo_pode_esconder_erro_por_tipo():
    """O sistema viu a moto como carro: o total bate, o erro só aparece por tipo."""
    r = erros([_linha(auto={"carro_desce": 10}, manual={"carro_desce": 9, "moto_desce": 1})])
    assert r["000026", "noite", "desce", TODOS]["erro_total"] == 0
    assert r["000026", "noite", "desce", "moto"]["erro_total"] == -1
    assert r["000026", "noite", "desce", "carro"]["erro_total"] > 0


def test_erros_soma_divergencias_na_classe_certa():
    pares = [
        {"tipo": "perdido", "quadro": 1, "sentido": "desce", "manual": "moto", "auto": None},
        {"tipo": "a_mais", "quadro": 2, "sentido": "desce", "manual": None, "auto": "carro"},
        {
            "tipo": "classe_trocada",
            "quadro": 3,
            "sentido": "desce",
            "manual": "onibus",
            "auto": "caminhao",
        },
        {"tipo": "acerto", "quadro": 4, "sentido": "desce", "manual": "carro", "auto": "carro"},
    ]
    r = erros([_linha(pares=pares)])
    chave = "000026", "noite", "desce"
    assert r[*chave, "moto"]["perdidos"] == 1
    assert r[*chave, "carro"]["a_mais"] == 1  # a mais conta na classe que o sistema viu
    assert r[*chave, "onibus"]["trocados"] == 1  # trocado conta na classe que a pessoa viu
    todos = r[*chave, TODOS]
    assert (todos["perdidos"], todos["a_mais"], todos["trocados"]) == (1, 1, 1)
    assert r["000026", "noite", "sobe", TODOS]["perdidos"] == 0


def test_parear_acha_perdido_a_mais_e_classe_trocada():
    manual = [(10, "carro", "desce"), (50, "moto", "desce"), (90, "onibus", "desce")]
    auto = [(12, "carro", "desce"), (70, "carro", "desce"), (95, "caminhao", "desce")]
    tipos = [(p["tipo"], p["manual"], p["auto"]) for p in parear(manual, auto, tolerancia=10)]
    assert tipos == [
        ("acerto", "carro", "carro"),
        ("perdido", "moto", None),
        ("a_mais", None, "carro"),
        ("classe_trocada", "onibus", "caminhao"),
    ]


def test_parear_nao_liga_sentidos_diferentes_nem_fora_da_tolerancia():
    assert [p["tipo"] for p in parear([(10, "carro", "desce")], [(10, "carro", "sobe")], 5)] == [
        "perdido",
        "a_mais",
    ]
    fora = parear([(10, "carro", "sobe")], [(16, "carro", "sobe")], 5)
    assert [p["tipo"] for p in fora] == ["perdido", "a_mais"]
    assert [p["tipo"] for p in parear([(10, "carro", "sobe")], [(15, "carro", "sobe")], 5)] == [
        "acerto"
    ]


def test_contagem_dupla_aparece_como_a_mais():
    """Um veículo real, duas trajetórias cruzando a linha: o segundo cruzamento sobra."""
    pares = parear([(30, "carro", "sobe")], [(29, "carro", "sobe"), (33, "carro", "sobe")], 20)
    assert [p["tipo"] for p in pares] == ["acerto", "a_mais"]


def test_totais_tem_todas_as_colunas():
    n = totais([(1, "moto", "sobe"), (2, "moto", "sobe"), (3, "carro", "desce")])
    assert list(n) == COLUNAS
    assert (n["moto_sobe"], n["carro_desce"], n["onibus_desce"]) == (2, 1, 0)


def test_contada_exige_todos_os_tipos_e_sentidos():
    cheia = {f"manual_{c}": "0" for c in COLUNAS}
    assert contada(cheia)
    assert not contada(cheia | {"manual_moto_sobe": ""})
    assert not contada(cheia | {"manual_moto_sobe": None})
    assert not contada({"manual_desce": "3", "manual_sobe": "0"})  # planilha antiga


def test_planilha_antiga_ganha_colunas_por_tipo(pasta):
    (pasta / "manual.csv").write_text(
        "arquivo;camera;condicao;manual_desce;manual_sobe;obs\na_1;000026;noite;;;chuva fina\n",
        encoding="utf-8-sig",
    )
    gravar_manual(ler_manual())
    (linha,) = ler_manual()
    assert (linha["arquivo"], linha["camera"], linha["obs"]) == ("a_1", "000026", "chuva fina")
    assert "manual_moto_desce" in linha and "manual_desce" not in linha
    assert not contada(linha)


def test_recontar_um_clipe_substitui_os_eventos_dele(pasta):
    gravar_eventos("a_1", [(5, "carro", "sobe"), (2, "moto", "desce")])
    gravar_eventos("a_2", [(7, "onibus", "sobe")])
    gravar_eventos("a_1", [(9, "caminhao", "desce")])
    assert ler_eventos() == {"a_1": [(9, "caminhao", "desce")], "a_2": [(7, "onibus", "sobe")]}


def test_limpar_apaga_so_videos_ja_contados(pasta):
    gravar_manual(
        [
            {"arquivo": "a_1", "camera": "000026"} | {f"manual_{c}": 0 for c in COLUNAS},
            {"arquivo": "a_2", "camera": "000026"},
        ]
    )
    for nome in ("a_1.mp4", "a_1_diag.mp4", "a_2.mp4"):
        (pasta / nome).write_bytes(b"x")
    limpar(None)
    assert sorted(p.name for p in pasta.glob("*.mp4")) == ["a_2.mp4"]
    assert (pasta / "manual.csv").exists()


def test_referencia_grava_no_formato_da_contagem_manual(pasta, monkeypatch):
    import ultralytics

    gravar_manual([{"arquivo": "a_1", "camera": "000026"}, {"arquivo": "a_2", "camera": "000018"}])
    (pasta / "a_1.mp4").write_bytes(b"x")  # a_2 sem vídeo: fica de fora
    monkeypatch.setattr(ultralytics, "YOLO", lambda modelo: modelo)
    vistos = [(3, "carro", "sobe"), (9, "moto", "desce")]
    monkeypatch.setattr(validar, "eventos_auto", lambda *a, **k: vistos)
    args = Namespace(modelo="yolo11x.pt", imgsz=1280, conf=None, tracker=None)
    validar.referencia(args)
    (linha,) = ler_manual("referencia")
    assert contada(linha) and linha["arquivo"] == "a_1"
    assert (linha["manual_carro_sobe"], linha["manual_moto_desce"]) == ("1", "1")
    assert ler_eventos("eventos_referencia") == {"a_1": vistos}
    assert ler_manual()[0]["manual_carro_sobe"] == ""  # a contagem manual não é tocada
    # rodar de novo retoma: o clipe já feito não passa pelo detector outra vez
    (pasta / "a_2.mp4").write_bytes(b"x")
    rodados = []
    monkeypatch.setattr(validar, "eventos_auto", lambda v, *a, **k: rodados.append(v.stem) or [])
    validar.referencia(args)
    assert rodados == ["a_2"]
    assert [x["arquivo"] for x in ler_manual("referencia")] == ["a_1", "a_2"]
    assert ler_eventos("eventos_referencia") == {"a_1": vistos}


def _sessao(teclas, n_quadros=30, fps=10):
    """Roda o contador manual com um roteiro de teclas ('.' = nenhuma tecla)."""
    import cv2
    import numpy as np

    quadro = cv2.imencode(".jpg", np.zeros((450, 800, 3), np.uint8))[1]
    roteiro = iter(teclas)
    telas = []
    eventos = sessao(
        [quadro] * n_quadros,
        ((0, 200), (799, 200)),
        fps,
        lambda _ms: -1 if (t := next(roteiro)) == "." else ord(t),
        telas.append,
    )
    return eventos, telas


def test_sessao_registra_tipo_sentido_e_quadro():
    eventos, telas = _sessao("..1.W\r")  # W maiúsculo: Caps Lock não atrapalha
    assert eventos == [(2, "carro", "desce"), (4, "moto", "sobe")]
    assert telas[0].shape == (450, 800, 3)


def test_sessao_desfaz_pausa_e_volta():
    eventos, _ = _sessao("3z" + " ..4 " + "\r")
    assert eventos == [(2, "caminhao", "desce")]  # pausado no quadro 2: o 4 cai nele
    eventos, _ = _sessao("." * 20 + "a" + "q\r")
    assert eventos == [(1, "carro", "sobe")]  # voltou 3 s (30 quadros): início do clipe


def test_sessao_para_no_ultimo_quadro_e_esc_nao_grava():
    eventos, _ = _sessao("....e\r", n_quadros=3)
    assert eventos == [(2, "onibus", "sobe")]
    assert _sessao("1\x1b")[0] is None


def test_carregar_le_todos_os_quadros(tmp_path):
    import cv2
    import numpy as np

    video = tmp_path / "v.mp4"
    saida = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for _ in range(7):
        saida.write(np.zeros((48, 64, 3), np.uint8))
    saida.release()
    quadros, fps = validar.carregar(video)
    assert (len(quadros), fps) == (7, 10)


def test_banco_guarda_parametros_e_migra_banco_antigo(tmp_path):
    caminho = tmp_path / "f.db"
    db = abrir_banco(caminho)
    db.execute("ALTER TABLE clipes DROP COLUMN linha")  # simula banco da fase 1
    db.commit()
    db.close()
    db = abrir_banco(caminho)
    gravar(db, "000026", "t1", 60, 2.0, Counter(), {"modelo": "m", "passo": "2", "linha": "L"})
    assert db.execute("SELECT modelo, passo, linha FROM clipes").fetchone() == ("m", "2", "L")


def test_sentido_de_segue_o_primeiro_cruzamento():
    linha = ((0, 50), (100, 50))
    assert validar.sentido_de([(50, 10), (50, 90)], linha) == "desce"
    assert validar.sentido_de([(50, 90), (50, 10), (50, 90)], linha) == "sobe"
    assert validar.sentido_de([(50, 10), (60, 20)], linha) is None


def test_desenhar_sentidos_pinta_cada_sentido_e_deixa_em_cinza_quem_andou_sem_cruzar():
    import numpy as np

    quadro = np.zeros((100, 200, 3), np.uint8)
    trajetorias = {
        1: ("carro", [(40, 10), (40, 50), (40, 90)]),  # desce
        2: ("carro", [(160, 90), (160, 50), (160, 10)]),  # sobe
        3: ("carro", [(10, 30), (110, 30)]),  # andou 100 px sem cruzar: cinza
        4: ("moto", [(100, 80), (110, 90)]),  # quase parado: some
    }
    img, n = validar.desenhar_sentidos(quadro, ((0, 60), (199, 60)), trajetorias)
    assert n == Counter(desce=1, sobe=1, fora=1)
    assert tuple(img[75, 40]) == validar.COR_SENTIDO["desce"]
    assert tuple(img[75, 160]) == validar.COR_SENTIDO["sobe"]
    assert tuple(img[30, 70]) == validar.CINZA
    assert not img[85, 105].any()


def test_pagina_sentidos_pergunta_por_camera_com_contagem_e_rotulo_atual():
    ficha = {
        "camera": "000026",
        "utc": "2026-11-21T21:30:00+00:00",
        "enquadramento": "A",
        "desce": 7,
        "sobe": 3,
        "fora": 4,
        "jpg": b"foto",
    }
    pagina = validar.pagina_sentidos([ficha])
    assert (
        "Jansen sent. Ponte" in pagina and "21/11 18:30" in pagina and "enquadramento A" in pagina
    )
    assert "7 veículos que vêm em direção à câmera" in pagina
    assert "4 veículos que andaram sem cruzar a linha amarela" in pagina
    assert "“para a ponte”" in pagina and "Sentido confirmado" in pagina
    assert "data:image/jpeg;base64,Zm90bw==" in pagina


def test_pagina_sentidos_aceita_ponto_derivado_e_via_de_mao_unica():
    ficha = {"camera": "000019d", "utc": "2026-11-21T22:00:00+00:00", "enquadramento": None}
    pagina = validar.pagina_sentidos([ficha | {"desce": 0, "sobe": 40, "fora": 9, "jpg": b""}])
    assert "Alameda, pista para Centro e BR" in pagina
    assert "“para o Centro, Santana e BR”" in pagina and "Fica fora do painel" in pagina
