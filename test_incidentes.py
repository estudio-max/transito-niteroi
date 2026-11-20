import sqlite3

import cv2
import numpy as np

from exportar import ler_ocorrencias, montar
from incidentes import imagens, parados, registrar

FPS = 10


def _parado(x=400, y=300, de=0, ate=300, w=60, h=40, tremor=0):
    """Trajetória parada em (x, y) dos quadros `de` a `ate`."""
    return [(q, x + (tremor if q % 2 else -tremor), y, w, h) for q in range(de, ate)]


def _andando(de=0, ate=300):
    return [(q, 100 + 3 * q, 300, 60, 40) for q in range(de, ate)]


def test_parado_tempo_suficiente_e_achado():
    (a,) = parados({1: _parado(tremor=5)}, {1: "carro"}, FPS)
    assert (a["classe"], a["x"], a["y"], a["segundos"], a["vizinhos"]) == ("carro", 405, 300, 30, 0)


def test_andando_ou_parado_pouco_tempo_nao_conta():
    assert parados({1: _andando(), 2: _parado(ate=150)}, {}, FPS) == []


def test_para_depois_de_andar_pega_o_trecho_parado():
    pts = _andando(0, 50) + [(q, 247, 300, 60, 40) for q in range(50, 300)]
    (a,) = parados({1: pts}, {1: "moto"}, FPS)
    # a âncora pega o fim da frenagem (até 0,3 altura antes); a posição é onde parou
    assert (a["quadro_ini"], a["quadro_fim"], a["segundos"], a["x"]) == (45, 299, 25, 247)


def test_dois_parados_juntos_sao_vizinhos():
    achados = parados({1: _parado(400), 2: _parado(450), 3: _parado(700)}, {}, FPS)
    assert sorted(a["vizinhos"] for a in achados) == [0, 1, 1]


def _db():
    return sqlite3.connect(":memory:")


P = {"classe": "carro", "x": 400, "y": 300, "w": 60, "h": 40, "segundos": 30, "vizinhos": 0}
P.update(quadro_ini=0, quadro_fim=290)


def _classificador(chamadas, tipo="enguico"):
    def f(jpgs, p):
        chamadas.append(len(jpgs))
        return {"tipo": tipo, "confianca": "media", "descricao": "carro parado na faixa"}

    return f


def test_nao_segura_a_trava_de_escrita_durante_a_chamada_lenta_ao_modelo(tmp_path):
    """O modelo de visão leva até ~2 min: nesse tempo o banco tem de aceitar outra escrita."""
    import sqlite3

    arquivo = tmp_path / "t.db"
    db = sqlite3.connect(arquivo)
    outro = sqlite3.connect(arquivo, timeout=0.2)
    durante = []

    def lento(jpgs, p):
        durante.append(db.in_transaction)
        outro.execute("CREATE TABLE IF NOT EXISTS outra (x)")  # falharia com a trava presa
        outro.commit()
        return {"tipo": "enguico", "confianca": "media", "descricao": "x"}

    registrar(db, "000018", "2026-11-18T10:00:00+00:00", [P], {}, lento)
    (novo,) = registrar(db, "000018", "2026-11-18T10:01:00+00:00", [P], {}, lento)
    assert novo["tipo"] == "enguico" and durante == [False]


def test_incidente_so_abre_no_segundo_clipe_e_depois_estende():
    db, chamadas = _db(), []
    cls = _classificador(chamadas)
    assert registrar(db, "000018", "2026-11-18T10:00:00+00:00", [P], {}, cls) == []
    (novo,) = registrar(db, "000018", "2026-11-18T10:01:00+00:00", [P], {}, cls)
    assert novo["tipo"] == "enguico" and chamadas == [0]
    assert registrar(db, "000018", "2026-11-18T10:02:00+00:00", [P], {}, cls) == []
    assert chamadas == [0]  # incidente aberto: não classifica de novo
    assert db.execute("SELECT inicio_utc, fim_utc, clipes FROM incidentes").fetchall() == [
        ("2026-11-18T10:00:00+00:00", "2026-11-18T10:02:00+00:00", 3)
    ]


def test_outro_lugar_ou_muito_depois_nao_emenda():
    db, chamadas = _db(), []
    cls = _classificador(chamadas)
    registrar(db, "000018", "2026-11-18T10:00:00+00:00", [P], {}, cls)
    longe = {**P, "x": 600}
    assert registrar(db, "000018", "2026-11-18T10:01:00+00:00", [longe], {}, cls) == []
    assert registrar(db, "000026", "2026-11-18T10:01:00+00:00", [P], {}, cls) == []
    assert registrar(db, "000018", "2026-11-18T10:20:00+00:00", [P], {}, cls) == []
    assert chamadas == []


def test_dois_parados_do_mesmo_incidente_no_mesmo_clipe_contam_um_clipe():
    db, chamadas = _db(), []
    cls = _classificador(chamadas, "acidente")
    vizinho = {**P, "x": 420}
    registrar(db, "000018", "2026-11-18T10:00:00+00:00", [P, vizinho], {}, cls)
    novos = registrar(db, "000018", "2026-11-18T10:01:00+00:00", [P, vizinho], {}, cls)
    assert len(novos) == 1 and chamadas == [0]
    registrar(db, "000018", "2026-11-18T10:02:00+00:00", [P, vizinho], {}, cls)
    assert db.execute("SELECT clipes FROM incidentes").fetchall() == [(3,)]


def test_falha_da_api_nao_perde_o_incidente():
    def quebra(jpgs, p):
        raise RuntimeError("sem chave")

    db = _db()
    registrar(db, "000018", "2026-11-18T10:00:00+00:00", [P], {}, quebra)
    (novo,) = registrar(db, "000018", "2026-11-18T10:01:00+00:00", [P], {}, quebra)
    assert novo["tipo"] == "indeterminado" and "sem chave" in novo["descricao"]


def test_imagens_marcam_tres_quadros():
    jpg = cv2.imencode(".jpg", np.zeros((450, 800, 3), np.uint8))[1].tobytes()
    quadros = {q: jpg for q in range(0, 300, 10)}
    saida = imagens(quadros, P)
    assert len(saida) == 4  # 3 quadros + ampliação da vizinhança
    ampliada = cv2.imdecode(np.frombuffer(saida[3], np.uint8), cv2.IMREAD_COLOR)
    assert ampliada.shape[:2] == (720, 720)  # janela de 4 × 60 px, ampliada 3×
    img = cv2.imdecode(np.frombuffer(saida[0], np.uint8), cv2.IMREAD_COLOR)
    assert img[300, 400 - 30 - 4][2] > 150  # borda vermelha da caixa
    assert imagens({}, P) == []


def _ollama_responde(monkeypatch, conteudo):
    import io
    import json
    import urllib.request

    enviado = {}

    def falso(req, timeout):
        enviado.update(json.loads(req.data))
        return io.BytesIO(json.dumps({"message": {"content": conteudo}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", falso)
    return enviado


def test_classificar_vlm_le_resposta_valida_e_manda_as_imagens(monkeypatch):
    import json

    from incidentes import classificar_vlm

    ok = json.dumps({"tipo": "enguico", "confianca": "alta", "descricao": "x" * 300})
    enviado = _ollama_responde(monkeypatch, ok)
    r = classificar_vlm([b"a", b"b", b"c"], P)
    assert (r["tipo"], r["confianca"], len(r["descricao"])) == ("enguico", "alta", 200)
    assert len(enviado["messages"][1]["images"]) == 3 and enviado["think"] is False


def test_classificar_vlm_resposta_quebrada_vira_indeterminado(monkeypatch):
    from incidentes import classificar_vlm

    for ruim in ("não é json", '{"tipo": "ovni", "confianca": "alta", "descricao": "x"}', "{}"):
        _ollama_responde(monkeypatch, ruim)
        assert classificar_vlm([b"a"], P)["tipo"] == "indeterminado"


def test_painel_recebe_so_ocorrencias_publicaveis():
    db = _db()
    for tipo in ("enguico", "estacionado"):
        cls = _classificador([], tipo)
        x = 100 if tipo == "enguico" else 600
        for minuto in range(3):
            registrar(db, "000018", f"2026-11-18T10:0{minuto}:00+00:00", [{**P, "x": x}], {}, cls)
    # incidente que durou só 2 clipes não vai ao painel
    registrar(db, "000026", "2026-11-18T10:00:00+00:00", [P], {}, _classificador([], "acidente"))
    registrar(db, "000026", "2026-11-18T10:01:00+00:00", [P], {}, _classificador([], "acidente"))
    ocorr = ler_ocorrencias(db, "2026-11-18T00:00:00+00:00")
    assert [o["tipo"] for o in ocorr] == ["enguico"]
    dados = montar([], "2026-11-18T10:05:00+00:00", (), ocorr)
    assert dados["ocorrencias"][0]["camera"] == "Jansen x Mal. Deodoro"
