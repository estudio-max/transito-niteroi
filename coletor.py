"""Coletor de fluxo: baixa o último clipe de cada câmera da NitTrans, conta os
veículos que cruzam uma linha e grava só os números em SQLite.

Uso:  uv run coletor.py            (laço, a cada 60 s)
      uv run coletor.py --uma-vez
      uv run coletor.py --janelas 06:30-09:30,17:00-20:00   (só nesses horários, dias úteis)
"""

import argparse
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
    "000026": {
        "nome": "Jansen sent. Ponte",
        "linha": ((290, 300), (590, 300)),
        # só se vê o fluxo que se afasta da câmera, que pelo nome é o sentido Ponte
        "sentido_confirmado": False,
    },
    "000018": {
        "nome": "Jansen x Mal. Deodoro",
        "linha": ((150, 250), (799, 250)),
        # confirmado pelo autor em 12/11/2026: lado esquerdo da imagem = da ponte para Icaraí
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
# em direção à câmera ("desce" na imagem) vai da ponte para Icaraí; o que se afasta
# ("sobe") vai para a ponte.
ROTULO_SENTIDO = {"desce": "da ponte para Icaraí", "sobe": "para a ponte"}

COLUNAS = [f"{v}_{s}" for v in VEICULOS.values() for s in SENTIDOS]
PARAMETROS = ["modelo", "passo", "linha", "detector"]


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


def gravar_passagens(db, camera, clipe_utc, lista):
    db.executemany(
        "INSERT INTO passagens (camera, clipe_utc, segundo, classe, sentido, vel_rel)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [(camera, clipe_utc, *p) for p in lista],
    )
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
    db = sqlite3.connect(caminho)
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
    return db


def ja_processado(db, camera, clipe_utc):
    return (
        db.execute(
            "SELECT 1 FROM clipes WHERE camera=? AND clipe_utc=?", (camera, clipe_utc)
        ).fetchone()
        is not None
    )


def gravar(db, camera, clipe_utc, duracao, ocupacao, contagem, parametros=None):
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
    linha = CAMERAS[camera]["linha"]
    contagem = contar(trajetorias, linha)
    parametros = {
        "modelo": nome_modelo,
        "passo": str(passo),
        "linha": str(linha),
        "detector": str(detector or {}),
    }
    gravar(db, camera, clipe_utc, duracao, ocupacao, contagem, parametros)
    fps = n_quadros[0] / duracao if duracao else 10
    classes = {t: c for t, (c, _) in trajetorias.items()}
    gravar_passagens(db, camera, clipe_utc, passagens(historico, classes, linha, fps))
    achados = incidentes.parados(historico, {t: c for t, (c, _) in trajetorias.items()}, fps)
    novos = incidentes.registrar(db, camera, clipe_utc, achados, quadros)
    for i in novos:
        print(camera, "INCIDENTE", i["tipo"], i["confianca"], i["descricao"], flush=True)
    return clipe_utc, round(ocupacao, 1), dict(contagem), f"{len(achados)} parados"


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
