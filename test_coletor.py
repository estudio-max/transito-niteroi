from datetime import datetime

import pytest

from coletor import (
    FUSO,
    abrir_banco,
    contar,
    cruzou,
    dentro_janela,
    gravar,
    ja_processado,
    ler_janelas,
    rastrear,
)

PICOS = ler_janelas("06:30-09:30, 17:00-20:00")


def _em(dia, hh, mm=0):  # novembro de 2026: dia 13 é sexta, 14 é sábado
    return datetime(2026, 11, dia, hh, mm, tzinfo=FUSO)


def test_dentro_e_fora_das_janelas():
    assert dentro_janela(_em(13, 6, 30), PICOS)  # início entra
    assert dentro_janela(_em(13, 19, 59), PICOS)
    assert not dentro_janela(_em(13, 9, 30), PICOS)  # fim não entra
    assert not dentro_janela(_em(13, 12), PICOS)


def test_fim_de_semana_so_quando_pedido():
    assert not dentro_janela(_em(14, 18), PICOS)
    assert dentro_janela(_em(14, 18), PICOS, dias_uteis=False)


def test_sem_janelas_coleta_sempre():
    assert ler_janelas(None) == [] and ler_janelas("") == []
    assert dentro_janela(_em(14, 3), [])


def test_rastrear_repassa_o_detector_ao_modelo(monkeypatch):
    chamadas = {}

    class Modelo:
        def track(self, **kw):
            chamadas.update(kw)
            return iter(())

    class Cap:
        def get(self, _):
            return 0

        def release(self):
            pass

    import cv2

    monkeypatch.setattr(cv2, "VideoCapture", lambda _: Cap())
    traj, ocup, _ = rastrear("x.mp4", Modelo(), 1, None, imgsz=960, conf=0.1)
    assert (chamadas["imgsz"], chamadas["conf"]) == (960, 0.1)
    assert (traj, ocup) == ({}, 0)


def test_janela_invertida_e_rejeitada():
    with pytest.raises(ValueError):
        ler_janelas("20:00-17:00")


LINHA = ((100, 300), (500, 300))


def test_cruzou_descendo_e_subindo():
    assert cruzou((200, 290), (200, 310), *LINHA) == 1
    assert cruzou((200, 310), (200, 290), *LINHA) == -1


def test_nao_cruza_do_mesmo_lado_nem_fora_do_segmento():
    assert cruzou((200, 280), (200, 295), *LINHA) == 0
    assert cruzou((600, 290), (600, 310), *LINHA) == 0  # passa ao lado da linha


def test_cruzou_linha_inclinada():
    assert cruzou((50, 10), (10, 50), (0, 0), (100, 100)) != 0


def test_contar_por_classe_e_sentido():
    traj = {
        1: ("carro", [(200, 280), (200, 295), (200, 310)]),
        2: ("moto", [(300, 320), (300, 290)]),
        3: ("onibus", [(700, 280), (700, 320)]),  # fora da linha
        4: ("carro", [(250, 100), (250, 120)]),  # nem chega na linha
    }
    assert contar(traj, LINHA) == {"carro_desce": 1, "moto_sobe": 1}


def test_trajetoria_tremida_conta_uma_vez():
    traj = {1: ("carro", [(200, 298), (200, 302), (200, 298), (200, 302)])}
    assert contar(traj, LINHA) == {"carro_desce": 1}


def test_trajetoria_vazia_ou_de_um_ponto():
    assert contar({}, LINHA) == {}
    assert contar({1: ("carro", [(200, 300)])}, LINHA) == {}


def test_banco_nao_duplica_clipe():
    db = abrir_banco(":memory:")
    c = contar({1: ("carro", [(200, 290), (200, 310)])}, LINHA)
    assert not ja_processado(db, "000026", "t1")
    gravar(db, "000026", "t1", 57.5, 3.2, c)
    gravar(db, "000026", "t1", 57.5, 3.2, c)
    assert ja_processado(db, "000026", "t1")
    assert db.execute(
        "SELECT count(*), sum(carro_desce), sum(moto_sobe) FROM clipes"
    ).fetchone() == (1, 1, 0)
