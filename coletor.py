"""Coletor de fluxo: baixa o último clipe de cada câmera da NitTrans, conta os
veículos que cruzam uma linha e grava só os números em SQLite.

Uso:  uv run coletor.py            (laço, a cada 60 s)
      uv run coletor.py --uma-vez
      uv run coletor.py --janelas 06:30-09:30,17:00-20:00   (só nesses horários, dias úteis)
"""

import argparse
import functools
import json
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from datetime import time as hora
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import historia
import incidentes

FUSO = ZoneInfo("America/Sao_Paulo")

URL = "https://appnittrans.niteroi.rj.gov.br:8888/{id}/last_video.mp4"
VEICULOS = {2: "carro", 3: "moto", 5: "onibus", 7: "caminhao"}  # classes COCO
SENTIDOS = ("desce", "sobe")  # na imagem, com a linha A→B da esquerda p/ direita

# Linha de contagem (A, B) em pixels do quadro 800x450. Calibrar olhando um quadro:
# deve cortar todas as faixas, longe de onde os veículos param.
# ponytail: uma linha por câmera; contagem por movimento (RF6) pede várias linhas.
CAMERAS = {
    "000019": {
        "nome": "Alameda, acesso à Ponte",
        # 1280x720 (as outras duas são 800x450). Linha PROVISÓRIA (21/11/2026), calibrada por
        # rastreamento automático, SEM conferência visual: a via desce/sobe no lado esquerdo
        # do quadro (pés dos veículos em x 20..710), com o cruzamento no topo (y<320).
        # Folha de sentidos de 21/11/2026: a linha só cruza a rampa da esquerda, e o autor
        # confirmou que ela leva quem vem do Fonseca pela Alameda e sobe a ponte. A pista da
        # direita (do Fonseca para o Centro, o Santana ou a BR) não é contada: pede outra linha.
        "linha": ((30, 400), (710, 400)),
        "sentidos": {"sobe": "para a ponte"},  # mão única: só o sentido que existe
        "sentido_confirmado": True,
    },
    # Ponto derivado: segunda linha sobre o mesmo clipe da 000019 (`fonte`), para a pista da
    # direita, que o autor descreveu como do Fonseca para o Centro, o Santana ou a BR. Linha
    # medida em 21/11/2026 pelas trajetórias de 2 clipes: em y=400 os veículos passam entre
    # x 810 e 1033. O clipe é baixado e rastreado uma vez só; cada linha grava com seu id.
    "000019d": {
        "nome": "Alameda, pista para Centro e BR",
        "fonte": "000019",
        "linha": ((770, 400), (1090, 400)),
        "sentidos": {"sobe": "para o Centro, Santana e BR"},  # mão única
        "sentido_confirmado": True,
    },
    "000021": {
        "nome": "Alameda x João Brasil",
        # 800x450. CRUZAMENTO: via horizontal no topo (y 150–230) e via diagonal (canto
        # inferior direito → topo). A linha única só pega a via vertical/diagonal; o fluxo
        # completo (por direção) fica na tabela movimentos (RF6). Linha PROVISÓRIA (21/11).
        "linha": ((600, 300), (790, 300)),
        # Confirmado pelo autor em 21/11/2026 (folha de sentidos + Street View, referência: o
        # hospital veterinário à esquerda): o laranja (se afasta) vem do Fonseca em direção à
        # ponte, e pode seguir para a ponte, o Ponto Cem Réis, o Barreto ou a BR. A pista da
        # esquerda, sem linha, seria a que vem da ponte para o Fonseca.
        "sentidos": {"sobe": "vindo do Fonseca"},  # mão única
        "sentido_confirmado": True,
    },
    "000026": {
        "nome": "Jansen sent. Ponte",
        # A câmera alterna entre dois enquadramentos ao longo do dia e cada um pede uma linha:
        # A mostra as duas pistas com canteiro (visto de 16/11 à noite e de madrugada); B só a
        # pista que se afasta, com a outra escondida atrás das árvores (13/11 e hoje de dia).
        # `linha_do_clipe` reconhece o enquadramento de cada clipe pelas miniaturas guardadas
        # em enquadramentos.json; "linha" é o padrão quando o clipe não pôde ser lido.
        "enquadramentos": {
            "A": ((95, 300), (640, 300)),
            "B": ((265, 300), (645, 300)),
        },
        "linha": ((265, 300), (645, 300)),
        # Confirmado pelo autor em 21/11/2026 (folha de sentidos + Street View da Av.
        # Washington Luís): o azul (vem para a câmera, pistas da esquerda) segue para Icaraí,
        # vindo da ponte, do Barreto ou do Fonseca (caminho comum para as praias da Região
        # Oceânica); o laranja (se afasta) vai de Icaraí para a ponte. As pistas que vão de
        # Icaraí para o Fonseca (cinza, para cima e à esquerda na imagem) não são contadas.
        "sentido_confirmado": True,
    },
    "000018": {
        "nome": "Jansen x Mal. Deodoro",
        "linha": ((150, 250), (799, 250)),
        # confirmado pelo autor em 12/11/2026: lado esquerdo da imagem = para Icaraí
        "sentido_confirmado": True,
    },
}

# As 7 câmeras da NitTrans em volta da saída da Ponte, na ordem em que o painel mostra.
# Só as de CAMERAS são contadas; as outras entram no painel como "no ar / sem contagem".
# lat/lon do OpenStreetMap (19/11/2026): cruzamento das vias quando o nome da câmera é um
# cruzamento; nas outras, um ponto da via ou do bairro. Todas aproximadas até alguém conferir.
REGIAO = [
    {
        "id": "000025",
        "nome": "Ilha da Conceição",
        "eixo": "Ilha da Conceição",
        "lat": -22.8716,
        "lon": -43.1144,
    },
    {
        "id": "000019",
        "nome": "Alameda, acesso à Ponte",
        "eixo": "Alameda (Fonseca)",
        "lat": -22.8807,
        "lon": -43.1066,
    },
    {
        "id": "000021",
        "nome": "Alameda x João Brasil",
        "eixo": "Alameda (Fonseca)",
        "lat": -22.8808,
        "lon": -43.1015,
    },
    {
        "id": "000026",
        "nome": "Jansen sent. Ponte",
        "eixo": "Av. Jansen de Melo",
        "lat": -22.8845,
        "lon": -43.1157,
    },
    {
        "id": "000018",
        "nome": "Jansen x Mal. Deodoro",
        "eixo": "Av. Jansen de Melo",
        "lat": -22.8891,
        "lon": -43.1145,
    },
    {
        "id": "000034",
        "nome": "Feliciano Sodré x Mergulhão",
        "eixo": "Av. Feliciano Sodré (Centro)",
        "lat": -22.8834,
        "lon": -43.1167,
    },
    {
        "id": "000017",
        "nome": "Feliciano Sodré",
        "eixo": "Av. Feliciano Sodré (Centro)",
        "lat": -22.8843,
        "lon": -43.1200,
    },
]

# Em todas as câmeras da Jansen de Melo a imagem olha para a ponte: o veículo que vem
# em direção à câmera ("desce" na imagem) vai para Icaraí (da ponte, do Barreto ou do
# Fonseca); o que se afasta ("sobe") vai para a ponte. Câmera de outra via tem os seus em CAMERAS[...]["sentidos"]; numa
# via de mão única só o sentido que existe tem nome, e o outro fica fora do painel (o pouco
# que a linha pega nele é erro do rastreador, como um veículo parado na fila).
ROTULO_SENTIDO = {"desce": "para Icaraí", "sobe": "para a ponte"}


def rotulos_sentido(camera):
    """Para onde vai cada sentido da imagem nesta câmera ({"desce": ..., "sobe": ...})."""
    return CAMERAS[camera].get("sentidos", ROTULO_SENTIDO)


COLUNAS = [f"{v}_{s}" for v in VEICULOS.values() for s in SENTIDOS]
PARAMETROS = ["modelo", "passo", "linha", "detector"]


ENQUADRAMENTOS = Path(__file__).with_name("enquadramentos.json")
# Abaixo disso o quadro não se parece com nenhum enquadramento guardado (o certo fica em
# 0,78 a 0,98; o errado, em 0,45 a 0,57; outra câmera, abaixo de 0,45).
SIMILARIDADE_MIN = 0.65


def descritor(quadro):
    """Miniatura 32x18 em cinza e seu mapa de bordas, cada um normalizado, num vetor só.
    São 1.152 números que não mostram pessoa, placa nem veículo; a miniatura sozinha
    separa o dia da noite, as bordas separam os enquadramentos."""
    import cv2
    import numpy as np

    cinza = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
    mini = cv2.resize(cinza, (32, 18), interpolation=cv2.INTER_AREA).astype(np.float32)
    g = cv2.GaussianBlur(cinza, (0, 0), 3)
    borda = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    borda = cv2.resize(borda, (32, 18), interpolation=cv2.INTER_AREA)
    v = np.concatenate([((m - m.mean()) / (m.std() + 1e-6)).ravel() for m in (mini, borda)])
    return v / (v.std() + 1e-6)


@functools.lru_cache(maxsize=1)
def _referencias():
    """{camera: {enquadramento: [descritor, ...]}}, guardados com 1 casa decimal (×10)."""
    if not ENQUADRAMENTOS.exists():
        return {}
    return json.loads(ENQUADRAMENTOS.read_text(encoding="utf-8"))


def enquadramento(camera, quadro, referencias=None):
    """(nome, similaridade) do enquadramento da câmera mais parecido com o quadro."""
    import numpy as np

    refs = (referencias if referencias is not None else _referencias())[camera]
    d = descritor(quadro)
    sims = {
        nome: max(float((d * np.array(r) / 10).mean()) for r in lista)
        for nome, lista in refs.items()
    }
    nome = max(sims, key=sims.get)
    return nome, sims[nome]


def linha_do_clipe(camera, video, referencias=None):
    """(linha, enquadramento, similaridade) do clipe. Câmera de um enquadramento só, ou
    clipe ilegível, devolve a linha padrão e enquadramento None."""
    import cv2

    cfg = CAMERAS[camera]
    if "enquadramentos" not in cfg:
        return cfg["linha"], None, None
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
    ok, quadro = cap.read()
    cap.release()
    try:
        if not ok:
            raise KeyError(camera)
        nome, sim = enquadramento(camera, quadro, referencias)
    except KeyError:  # sem quadro, ou sem miniaturas guardadas para a câmera
        return cfg["linha"], None, None
    return cfg["enquadramentos"][nome], nome, sim


def _lado(p, a, b):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def cruzou(p0, p1, a, b):
    """+1 se o passo p0→p1 cruza o segmento AB descendo, -1 subindo, 0 se não cruza."""
    l0, l1 = _lado(p0, a, b), _lado(p1, a, b)
    if (l0 < 0) == (l1 < 0):
        return 0
    if (_lado(a, p0, p1) < 0) == (_lado(b, p0, p1) < 0):
        return 0  # cruza a reta, mas fora do segmento
    return 1 if l1 >= 0 else -1


def contar(trajetorias, linha):
    """trajetorias: {id: (classe, [pontos])} → Counter{'carro_desce': n, ...}.
    Cada trajetória conta uma vez só (o primeiro cruzamento)."""
    total = Counter()
    for classe, pontos in trajetorias.values():
        for p0, p1 in zip(pontos, pontos[1:], strict=False):
            if s := cruzou(p0, p1, *linha):
                total[f"{classe}_{SENTIDOS[0] if s > 0 else SENTIDOS[1]}"] += 1
                break
    return total


MOVIMENTO_MIN = 20  # deslocamento mínimo (px) para a trajetória contar como movimento


def classificar_movimento(dx, dy, minimo=MOVIMENTO_MIN):
    """Rótulo do movimento de uma trajetória a partir do deslocamento (dx, dy) do pé da
    caixa: leste/oeste/norte/sul pelo eixo dominante. None se o veículo mal se moveu
    (parado). É a base do RF6: conta o fluxo de um cruzamento por direção."""
    if (dx * dx + dy * dy) ** 0.5 < minimo:
        return None
    if abs(dx) >= abs(dy):
        return "leste" if dx > 0 else "oeste"
    return "sul" if dy > 0 else "norte"


def movimentos(trajetorias, minimo=MOVIMENTO_MIN):
    """Counter{'<movimento>_<classe>': n}: uma trajetória = um movimento, pela direção do
    deslocamento (primeiro → último pé da caixa). Independe da linha de contagem, então
    captura também a via horizontal de um cruzamento (RF6)."""
    total = Counter()
    for classe, pontos in trajetorias.values():
        if len(pontos) < 2:
            continue
        (x0, y0), (x1, y1) = pontos[0], pontos[-1]
        m = classificar_movimento(x1 - x0, y1 - y0, minimo)
        if m:
            total[f"{m}_{classe}"] += 1
    return total


def velocidade_relativa(pts, q, fps, janela_s=1.0):
    """Deslocamento do pé da caixa no segundo em volta do quadro q, medido em alturas da
    própria caixa por segundo. Deslocamento e caixa encolhem juntos com a distância da
    câmera, então a razão serve para comparar horários na mesma câmera sem calibrar.
    Vira km/h multiplicando por uma constante por câmera e tipo de veículo, que exige uma
    referência de campo (ver STEPS.md). None se a janela tiver menos de 0,3 s."""
    perto = [p for p in pts if abs(p[0] - q) <= janela_s * fps]
    if len(perto) < 2:
        return None
    (q0, x0, y0, _, _), (q1, x1, y1, _, _) = perto[0], perto[-1]
    dt = (q1 - q0) / fps
    altura = sum(p[4] for p in perto) / len(perto)
    if dt < 0.3 or altura <= 0:
        return None
    return round(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / altura / dt, 2)


def passagens(historico, classes, linha, fps):
    """Cada veículo que cruzou a linha: [(segundo, classe, sentido, velocidade relativa)].
    historico vem de incidentes.observador ({id: [(quadro, x, y, largura, altura)]}), com o
    mesmo pé da caixa de rastrear; por isso a soma bate com contar(). Um cruzamento por
    trajetória (o primeiro), como em contar()."""
    saida = []
    for tid, pts in historico.items():
        for (_, x0, y0, *_), (q1, x1, y1, *_) in zip(pts, pts[1:], strict=False):
            if s := cruzou((x0, y0), (x1, y1), *linha):
                sentido = SENTIDOS[0] if s > 0 else SENTIDOS[1]
                vel = velocidade_relativa(pts, q1, fps)
                saida.append((round(q1 / fps, 1), classes.get(tid, "carro"), sentido, vel))
                break
    return sorted(saida, key=lambda p: p[:3])


def gravar_passagens(db, camera, clipe_utc, lista, commit=True):
    db.executemany(
        "INSERT INTO passagens (camera, clipe_utc, segundo, classe, sentido, vel_rel)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [(camera, clipe_utc, *p) for p in lista],
    )
    if commit:
        db.commit()


def gravar_movimentos(db, camera, clipe_utc, total, commit=True):
    db.executemany(
        "INSERT INTO movimentos (camera, clipe_utc, movimento, classe, quantidade)"
        " VALUES (?, ?, ?, ?, ?)",
        [(camera, clipe_utc, *m.split("_", 1), n) for m, n in total.items()],
    )
    if commit:
        db.commit()


def rastrear(video, modelo, passo=1, ao_quadro=None, **detector):
    """Roda detector + rastreador no clipe.
    Devolve (trajetorias, média de veículos por quadro, duração em s).
    ao_quadro(resultado, pontos) é chamado a cada quadro (usado na validação).
    detector: imgsz, conf etc., repassados ao modelo (padrão do Ultralytics: 640, 0,25)."""
    import cv2

    cap = cv2.VideoCapture(str(video))
    duracao = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 10)
    cap.release()

    classes, pontos, visiveis, quadros = {}, {}, 0, 0
    for r in modelo.track(
        source=str(video),
        stream=True,
        classes=list(VEICULOS),
        vid_stride=passo,
        verbose=False,
        **detector,
    ):
        quadros += 1
        visiveis += len(r.boxes)
        if r.boxes.id is not None:
            for tid, cls, (x1, _y1, x2, y2) in zip(
                r.boxes.id.int().tolist(),
                r.boxes.cls.int().tolist(),
                r.boxes.xyxy.tolist(),
                strict=True,
            ):
                classes.setdefault(tid, []).append(VEICULOS[cls])
                pontos.setdefault(tid, []).append(((x1 + x2) / 2, y2))  # pé da caixa
        if ao_quadro:
            ao_quadro(r, pontos)
    trajetorias = {t: (Counter(classes[t]).most_common(1)[0][0], pontos[t]) for t in pontos}
    return trajetorias, visiveis / max(quadros, 1), duracao


def abrir_banco(caminho):
    # 30 s de paciência: outro programa (ou a publicação) pode estar gravando
    db = sqlite3.connect(caminho, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")  # leitor não bloqueia o escritor (publicação concorrente)
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS clipes (camera TEXT, clipe_utc TEXT, duracao_s REAL,"
        " ocupacao REAL, "
        + ", ".join(f"{c} INTEGER DEFAULT 0" for c in COLUNAS)
        + ", PRIMARY KEY (camera, clipe_utc))"
    )
    # RM2: com que parâmetros cada clipe foi contado (migra bancos antigos)
    existentes = {r[1] for r in db.execute("PRAGMA table_info(clipes)")}
    for col in PARAMETROS:
        if col not in existentes:
            db.execute(f"ALTER TABLE clipes ADD COLUMN {col} TEXT")
    # cada veículo que cruzou a linha, com o segundo dentro do clipe (desde 19/11/2026)
    db.execute(
        "CREATE TABLE IF NOT EXISTS passagens (camera TEXT, clipe_utc TEXT, segundo REAL,"
        " classe TEXT, sentido TEXT)"
    )
    if "vel_rel" not in {r[1] for r in db.execute("PRAGMA table_info(passagens)")}:
        db.execute("ALTER TABLE passagens ADD COLUMN vel_rel REAL")  # piloto de velocidade
    # cada veículo por direção de movimento (RF6), independente da linha de contagem
    db.execute(
        "CREATE TABLE IF NOT EXISTS movimentos (camera TEXT, clipe_utc TEXT,"
        " movimento TEXT, classe TEXT, quantidade INTEGER)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS ix_clipes_utc ON clipes(clipe_utc)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_passagens_clipe ON passagens(camera, clipe_utc)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_movimentos_clipe ON movimentos(camera, clipe_utc)")
    return db


def ja_processado(db, camera, clipe_utc):
    return (
        db.execute(
            "SELECT 1 FROM clipes WHERE camera=? AND clipe_utc=?", (camera, clipe_utc)
        ).fetchone()
        is not None
    )


def gravar(db, camera, clipe_utc, duracao, ocupacao, contagem, parametros=None, commit=True):
    colunas = COLUNAS + PARAMETROS
    parametros = parametros or {}
    db.execute(
        f"INSERT OR IGNORE INTO clipes (camera, clipe_utc, duracao_s, ocupacao, {', '.join(colunas)})"
        f" VALUES (?, ?, ?, ?, {', '.join('?' * len(colunas))})",
        (
            camera,
            clipe_utc,
            duracao,
            ocupacao,
            *(contagem[c] for c in COLUNAS),
            *(parametros.get(p) for p in PARAMETROS),
        ),
    )
    if commit:
        db.commit()


def abrir_clipe(camera):
    """Abre o último clipe da câmera. Devolve (resposta HTTP, data UTC do clipe)."""
    req = urllib.request.Request(URL.format(id=camera), headers={"User-Agent": "fluxo-coletor"})
    resp = urllib.request.urlopen(req, timeout=60)
    return resp, parsedate_to_datetime(resp.headers["Last-Modified"]).isoformat()


def criar_tabela_estado(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS estado_cameras (camera TEXT, verificado_utc TEXT,"
        " http INTEGER, video_utc TEXT)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS ix_estado_cam ON estado_cameras(camera, verificado_utc)")


def checar_cameras(db, agora_utc, cabecalho=None):
    """Grava se cada câmera da REGIAO responde e quando o vídeo dela foi renovado.
    Só pede o cabeçalho (HEAD): não baixa vídeo."""

    def _cabecalho(camera):
        req = urllib.request.Request(
            URL.format(id=camera), method="HEAD", headers={"User-Agent": "fluxo-coletor"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, parsedate_to_datetime(r.headers["Last-Modified"]).isoformat()

    cabecalho = cabecalho or _cabecalho
    criar_tabela_estado(db)
    for cam in REGIAO:
        try:
            http, video = cabecalho(cam["id"])
        except urllib.error.HTTPError as e:
            http, video = e.code, None
        except Exception:  # timeout, DNS, conexão recusada
            http, video = 0, None
        db.execute(
            "INSERT INTO estado_cameras VALUES (?, ?, ?, ?)", (cam["id"], agora_utc, http, video)
        )
    db.commit()


def coletar(db, modelo, camera, passo, nome_modelo="", detector=None):
    """Baixa, conta e grava um clipe. Devolve a linha gravada ou None se repetido."""
    resp, clipe_utc = abrir_clipe(camera)
    with resp:
        if ja_processado(db, camera, clipe_utc):
            return None  # sai sem baixar o corpo
        dados = resp.read()
    ao_quadro, historico, quadros, n_quadros = incidentes.observador()
    with tempfile.TemporaryDirectory() as tmp:  # o vídeo nunca é guardado
        video = Path(tmp) / "clipe.mp4"
        video.write_bytes(dados)
        trajetorias, ocupacao, duracao = rastrear(
            video, modelo, passo, ao_quadro, **(detector or {})
        )
        linha, vista, sim = linha_do_clipe(camera, video)
    if sim is not None and sim < SIMILARIDADE_MIN:
        # ponytail: usa o enquadramento mais parecido mesmo assim; um terceiro enquadramento
        # entra com `uv run validar.py enquadramento` e uma linha nova em CAMERAS
        print(camera, f"ENQUADRAMENTO INCERTO ({vista}, similaridade {sim:.2f})", flush=True)
    contagem = contar(trajetorias, linha)
    parametros = {
        "modelo": nome_modelo,
        "passo": str(passo),
        "linha": str(linha),
        "detector": str(detector or {}),
    }
    gravar(db, camera, clipe_utc, duracao, ocupacao, contagem, parametros, commit=False)
    fps = n_quadros[0] / duracao if duracao else 10
    classes = {t: c for t, (c, _) in trajetorias.items()}
    # clipe, passagens e movimentos na mesma transação: queda no meio não deixa clipe sem detalhe
    gravar_passagens(db, camera, clipe_utc, passagens(historico, classes, linha, fps), commit=False)
    gravar_movimentos(db, camera, clipe_utc, movimentos(trajetorias), commit=False)
    extras = []
    for ponto, cfg in CAMERAS.items():  # pontos derivados: outras linhas no mesmo clipe
        if cfg.get("fonte") != camera:
            continue
        c = contar(trajetorias, cfg["linha"])
        p = parametros | {"linha": str(cfg["linha"])}
        # ponytail: a ocupação é a do quadro inteiro, igual à da fonte
        gravar(db, ponto, clipe_utc, duracao, ocupacao, c, p, commit=False)
        lista = passagens(historico, classes, cfg["linha"], fps)
        gravar_passagens(db, ponto, clipe_utc, lista, commit=False)
        extras.append(f"{ponto} {dict(c)}")
    db.commit()
    achados = incidentes.parados(historico, {t: c for t, (c, _) in trajetorias.items()}, fps)
    novos = incidentes.registrar(db, camera, clipe_utc, achados, quadros)
    for i in novos:
        print(camera, "INCIDENTE", i["tipo"], i["confianca"], i["descricao"], flush=True)
    parados = f"{len(achados)} parados" + (f", enquadramento {vista}" if vista else "")
    parados += "".join(f", {e}" for e in extras)
    return clipe_utc, round(ocupacao, 1), dict(contagem), parados


def ler_janelas(texto):
    """'06:30-09:30,17:00-20:00' → [(time(6,30), time(9,30)), ...]. Vazio = sem restrição."""
    janelas = []
    for parte in filter(None, (p.strip() for p in (texto or "").split(","))):
        ini, fim = (hora.fromisoformat(x.strip()) for x in parte.split("-"))
        if fim <= ini:
            raise ValueError(f"janela {parte!r}: o fim precisa ser depois do início")
        janelas.append((ini, fim))
    return janelas


def dentro_janela(agora, janelas, dias_uteis=True):
    """Se a coleta deve rodar em `agora` (datetime com fuso de Niterói)."""
    if not janelas:
        return True
    if dias_uteis and agora.weekday() >= 5:
        return False
    t = agora.time()
    return any(ini <= t < fim for ini, fim in janelas)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--banco", default="fluxo.db")
    ap.add_argument("--intervalo", type=int, default=60, help="segundos entre rodadas (mín. 60)")
    ap.add_argument(
        "--passo",
        type=int,
        default=1,
        help="processa 1 a cada N quadros; >1 derruba a contagem (ver STEPS.md)",
    )
    ap.add_argument("--modelo", default="yolo11n.pt")
    ap.add_argument("--imgsz", type=int, help="resolução do detector (padrão do modelo: 640)")
    ap.add_argument("--conf", type=float, help="confiança mínima (padrão do modelo: 0,25)")
    ap.add_argument(
        "--tracker",
        help="yaml do rastreador, ex.: rastreador_permissivo.yaml (padrão: bytetrack.yaml)",
    )
    ap.add_argument("--uma-vez", action="store_true")
    ap.add_argument(
        "--publicar",
        help="destino scp do painel, ex.: hostgator-fanara:transito.fanara.com.br (a cada 5 min)",
    )
    ap.add_argument(
        "--janelas",
        help="só coleta nesses horários (Niterói), ex.: 06:30-09:30,17:00-20:00",
    )
    ap.add_argument(
        "--fim-de-semana",
        action="store_true",
        help="com --janelas, coleta também sábado e domingo",
    )
    args = ap.parse_args()
    janelas = ler_janelas(args.janelas)
    opcoes = (("imgsz", args.imgsz), ("conf", args.conf), ("tracker", args.tracker))
    detector = {k: v for k, v in opcoes if v is not None}

    import ultralytics
    from ultralytics import YOLO

    nome_modelo = f"{args.modelo}@ultralytics{ultralytics.__version__}"
    db = abrir_banco(args.banco)
    publicado = float("-inf")
    esperando = False
    ultima_hora_clima = ultimo_backup = None
    while True:
        inicio = time.monotonic()
        if args.uma_vez and not dentro_janela(datetime.now(FUSO), janelas, not args.fim_de_semana):
            print("fora das janelas de coleta", args.janelas or "", flush=True)
            break
        if not dentro_janela(datetime.now(FUSO), janelas, not args.fim_de_semana):
            if not esperando:
                print("fora das janelas de coleta, aguardando", args.janelas, flush=True)
                esperando = True
            time.sleep(60)
            continue
        if esperando:
            print("janela aberta, coletando", flush=True)
            esperando = False
        for camera, cfg in CAMERAS.items():
            if "fonte" in cfg:  # ponto derivado: contado junto com o clipe da fonte
                continue
            try:
                # modelo novo por clipe: zera o rastreador entre clipes
                r = coletar(db, YOLO(args.modelo), camera, args.passo, nome_modelo, detector)
                print(camera, cfg["nome"], r or "clipe repetido", flush=True)
            except Exception as e:  # 503, timeout, clipe corrompido: segue o laço
                print(camera, cfg["nome"], "ERRO", repr(e), flush=True)
        if args.publicar and time.monotonic() - publicado >= 300:
            agora_utc = datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds")
            if agora_utc[:13] != ultima_hora_clima:  # uma vez por hora
                try:
                    n = historia.atualizar_clima(db, agora_utc)
                    ultima_hora_clima = agora_utc[:13]
                    print("clima atualizado", n, "horas", flush=True)
                except Exception as e:  # previsão do tempo fora do ar não para a coleta
                    print("ERRO no clima", repr(e), flush=True)
            dia = datetime.now(FUSO).date().isoformat()
            if dia != ultimo_backup:  # uma vez por dia (e a cada reinício)
                try:
                    print(
                        "cópia do banco:",
                        historia.copiar_banco(args.banco, args.publicar, dia),
                        flush=True,
                    )
                    ultimo_backup = dia
                except Exception as e:
                    print("ERRO na cópia do banco", repr(e), flush=True)
            try:
                from exportar import exportar

                checar_cameras(db, agora_utc)
                exportar(args.banco, enviar=args.publicar)
                publicado = time.monotonic()
                print("painel atualizado", flush=True)
            except Exception as e:  # hospedagem fora do ar não derruba a coleta
                print("ERRO ao publicar", repr(e), flush=True)
        if args.uma_vez:
            break
        time.sleep(max(0, max(args.intervalo, 60) - (time.monotonic() - inicio)))


if __name__ == "__main__":
    main()
