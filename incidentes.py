"""Veículo parado e incidente.

1. `parados`: trajetórias cujo pé da caixa fica no mesmo lugar por PARADO_S ou mais.
2. `registrar`: grava cada parado; quando o mesmo lugar já tinha parado no clipe
   anterior (até EMENDA_MIN antes), abre um incidente e pede a um modelo de visão
   local (Ollama) que o classifique (acidente, enguiço, estacionado, fila, bloqueio,
   indeterminado). Incidente já aberto no mesmo lugar só é estendido, sem nova chamada.

Os quadros não saem do notebook nem são guardados; o banco recebe apenas texto
(tipo, confiança, descrição).
"""

import base64
import json
import urllib.request
from datetime import datetime, timedelta

# ponytail: limiares escolhidos a olho; calibrar com incidentes reais (ver STEPS.md)
PARADO_S = 20  # parado por pelo menos isso dentro do clipe
TOLERANCIA = 0.3  # deslocamento máximo do pé da caixa, em alturas da caixa
MESMO_LUGAR_PX = 40  # dois parados a até essa distância são o mesmo veículo/incidente
EMENDA_MIN = 5  # clipes até essa distância no tempo são "seguidos"
QUADRO_A_CADA = 10  # guarda 1 quadro em 10 (1 por segundo a 10 qps) para a classificação

# ponytail: modelo pequeno que cabe na RTX 3050 (6 GB); sobe para qwen3-vl:8b se errar muito
MODELO_VLM = "qwen3-vl:4b-instruct"
OLLAMA_URL = "http://localhost:11434/api/chat"
TIPOS = ("acidente", "enguico", "estacionado", "fila", "bloqueio", "indeterminado")
PUBLICAVEIS = ("acidente", "enguico", "bloqueio")  # o que o painel mostra

INSTRUCOES = """Você analisa quadros de uma câmera pública de trânsito de Niterói (RJ).
As três primeiras imagens são o início, o meio e o fim de um período em que o veículo
marcado com a caixa vermelha ficou parado; a quarta é uma ampliação da vizinhança dele.
Ele também estava parado no mesmo lugar no clipe anterior, cerca de 1 minuto antes.
Primeiro decida se o veículo está sobre a pista de rolamento ou fora dela. Posto de
combustível, calçada, estacionamento, recuo e área ao lado da via são fora da pista.
Classifique a situação desse veículo:

- acidente: sinais de colisão: veículos encostados ou em ângulo anormal, dano visível,
  destroços na pista, moto caída, pessoas na pista em volta dos veículos.
- enguico: veículo parado SOBRE a faixa de rolamento, sem sinal de colisão, com o trânsito
  desviando dele; pisca-alerta, capô aberto ou triângulo reforçam. Só vale se for claro
  que ele está na pista.
- estacionado: fora da faixa de rolamento (meio-fio, vaga, recuo, posto de combustível,
  estacionamento), ou ônibus/táxi em ponto. Se o trânsito segue normalmente na pista e o
  veículo está fora dela, é estacionado, não enguiço.
- fila: o trânsito em volta também está parado (congestionamento ou semáforo fechado).
- bloqueio: obra, cones, viatura, guincho ou interdição da via.
- indeterminado: a imagem não permite decidir (escuro, chuva, oclusão, caixa no lugar errado).

Prefira "indeterminado" a adivinhar. Use confiança "alta" só com sinais claros nos quadros.
A descrição é uma frase em português, de até 160 caracteres, sobre o que se vê na via.
Comece pelo tipo do veículo marcado, o mais específico que a imagem permitir (carro, SUV,
picape, van, utilitário, moto, ônibus, caminhão), e pela cor (ex.: "SUV prata parado...",
"Ônibus branco parado..."), para quem lê achá-lo na imagem; o que não der para ver, omita.
Não descreva pessoas nem leia placas."""


def parados(historico, classes, fps, parado_s=PARADO_S, tolerancia=TOLERANCIA):
    """historico: {id: [(quadro, x, y, largura, altura)]}, com (x, y) o pé da caixa.
    Devolve um dict por trajetória que ficou parada ao menos `parado_s` segundos
    (o trecho parado mais longo dela), com `vizinhos` = outros parados próximos."""
    achados = []
    for tid, pts in historico.items():
        melhor, ancora = None, 0
        for j in range(1, len(pts) + 1):
            # o trecho termina quando o veículo sai da tolerância em torno da âncora
            if j < len(pts):
                _, ax, ay, _, ah = pts[ancora]
                _, x, y, _, _ = pts[j]
                if abs(x - ax) <= tolerancia * ah and abs(y - ay) <= tolerancia * ah:
                    continue
            dur = (pts[j - 1][0] - pts[ancora][0]) / fps
            if dur >= parado_s and (melhor is None or dur > melhor[2]):
                melhor = (ancora, j - 1, dur)
            ancora = j
        if melhor:
            i, f, dur = melhor
            _, x, y, w, h = pts[f]  # onde terminou parado (a âncora pode ser a frenagem)
            achados.append(
                {
                    "id": tid,
                    "classe": classes.get(tid, "carro"),
                    "x": round(x),
                    "y": round(y),
                    "w": round(w),
                    "h": round(h),
                    "quadro_ini": pts[i][0],
                    "quadro_fim": pts[f][0],
                    "segundos": round(dur),
                }
            )
    for a in achados:
        a["vizinhos"] = sum(
            1 for b in achados if b is not a and _perto(a, b, 2 * max(a["h"], b["h"]))
        )
    return achados


def _perto(a, b, limite=MESMO_LUGAR_PX):
    return abs(a["x"] - b["x"]) <= limite and abs(a["y"] - b["y"]) <= limite


def observador():
    """Callback para `coletor.rastrear(ao_quadro=...)` que guarda o histórico de cada
    trajetória e 1 quadro por segundo em JPEG (só em memória).
    Devolve (callback, historico, quadros, contagem de quadros)."""
    import cv2

    historico, quadros, n = {}, {}, [0]

    def ao_quadro(r, _pontos):
        q = n[0]
        n[0] += 1
        if r.boxes.id is not None:
            for tid, (x1, y1, x2, y2) in zip(
                r.boxes.id.int().tolist(), r.boxes.xyxy.tolist(), strict=True
            ):
                historico.setdefault(tid, []).append((q, (x1 + x2) / 2, y2, x2 - x1, y2 - y1))
        if q % QUADRO_A_CADA == 0:
            quadros[q] = cv2.imencode(".jpg", r.orig_img)[1].tobytes()

    return ao_quadro, historico, quadros, n


def imagens(quadros, parado):
    """Três quadros (início, meio, fim do trecho parado) com a caixa do veículo, mais uma
    ampliação da vizinhança dele no quadro do meio (o veículo longe da câmera tem ~35 px)."""
    import cv2
    import numpy as np

    if not quadros:
        return []
    ini, fim = parado["quadro_ini"], parado["quadro_fim"]
    alvos = (ini, (ini + fim) // 2, fim)
    escolhidos = sorted({min(quadros, key=lambda q, a=a: abs(q - a)) for a in alvos})
    x, y, w, h = parado["x"], parado["y"], parado["w"], parado["h"]
    saida, meio = [], None
    for q in escolhidos:
        img = cv2.imdecode(np.frombuffer(quadros[q], np.uint8), cv2.IMREAD_COLOR)
        cv2.rectangle(img, (x - w // 2 - 4, y - h - 4), (x + w // 2 + 4, y + 4), (0, 0, 255), 2)
        saida.append(cv2.imencode(".jpg", img)[1].tobytes())
        meio = img
    lado = max(160, 4 * max(w, h))  # janela quadrada em volta do veículo, dentro do quadro
    altura, largura = meio.shape[:2]
    x0 = min(max(x - lado // 2, 0), max(largura - lado, 0))
    y0 = min(max(y - h // 2 - lado // 2, 0), max(altura - lado, 0))
    corte = meio[y0 : y0 + lado, x0 : x0 + lado]
    corte = cv2.resize(corte, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    saida.append(cv2.imencode(".jpg", corte)[1].tobytes())
    return saida


ESQUEMA = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": list(TIPOS)},
        "confianca": {"type": "string", "enum": ["baixa", "media", "alta"]},
        "descricao": {"type": "string"},
    },
    "required": ["tipo", "confianca", "descricao"],
}


def classificar_vlm(jpgs, parado):
    """Pergunta ao modelo de visão local (Ollama) o que é o veículo parado.
    Devolve {tipo, confianca, descricao}; resposta fora do esquema vira indeterminado."""
    corpo = {
        "model": MODELO_VLM,
        "stream": False,
        "think": False,
        "keep_alive": "30m",  # mantém o modelo na GPU entre incidentes
        "format": ESQUEMA,
        "options": {"temperature": 0, "num_ctx": 8192},  # 4 imagens passam dos 4096 padrão
        "messages": [
            {"role": "system", "content": INSTRUCOES},
            {
                "role": "user",
                "content": f"Veículo marcado: {parado['classe']}, parado há pelo menos "
                f"{parado['segundos']} s neste clipe. Outros veículos parados perto dele: "
                f"{parado['vizinhos']}.",
                "images": [base64.b64encode(j).decode() for j in jpgs],
            },
        ],
    }
    req = urllib.request.Request(
        OLLAMA_URL, json.dumps(corpo).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
        texto = json.load(r)["message"]["content"]
    try:
        out = json.loads(texto)
        if out["tipo"] in TIPOS and out["confianca"] in ("baixa", "media", "alta"):
            return {**out, "descricao": str(out["descricao"])[:200]}
    except (ValueError, KeyError, TypeError):
        pass
    return {"tipo": "indeterminado", "confianca": "baixa", "descricao": "resposta fora do esquema"}


def criar_tabelas(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS parados (camera TEXT, clipe_utc TEXT, classe TEXT,"
        " x INTEGER, y INTEGER, segundos INTEGER, vizinhos INTEGER)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY, camera TEXT,"
        " inicio_utc TEXT, fim_utc TEXT, clipes INTEGER, classe TEXT, x INTEGER, y INTEGER,"
        " tipo TEXT, confianca TEXT, descricao TEXT, modelo TEXT)"
    )


def registrar(db, camera, clipe_utc, achados, quadros, classificar=classificar_vlm):
    """Grava os parados do clipe e abre ou estende incidentes. Devolve os novos."""
    criar_tabelas(db)
    desde = (datetime.fromisoformat(clipe_utc) - timedelta(minutes=EMENDA_MIN)).isoformat()
    novos = []
    for p in achados:
        db.execute(
            "INSERT INTO parados VALUES (?, ?, ?, ?, ?, ?, ?)",
            (camera, clipe_utc, p["classe"], p["x"], p["y"], p["segundos"], p["vizinhos"]),
        )
        aberto = next(
            (
                (i, fim)
                for i, x, y, fim in db.execute(
                    "SELECT id, x, y, fim_utc FROM incidentes WHERE camera=? AND fim_utc>=?",
                    (camera, desde),
                )
                if _perto(p, {"x": x, "y": y})
            ),
            None,
        )
        if aberto:  # mesmo incidente: estende (uma vez por clipe), sem nova classificação
            if aberto[1] < clipe_utc:
                db.execute(
                    "UPDATE incidentes SET fim_utc=?, clipes=clipes+1 WHERE id=?",
                    (clipe_utc, aberto[0]),
                )
            continue
        antes = [
            utc
            for utc, x, y in db.execute(
                "SELECT clipe_utc, x, y FROM parados WHERE camera=? AND clipe_utc>=?"
                " AND clipe_utc<?",
                (camera, desde, clipe_utc),
            )
            if _perto(p, {"x": x, "y": y})
        ]
        if not antes:
            continue  # primeira vez parado aqui: pode ser só o semáforo
        # O modelo de visão leva de ~14 s a ~2 min: grava antes, para não segurar a trava de
        # escrita do banco (e bloquear a publicação e qualquer outro programa) esse tempo todo.
        db.commit()
        try:
            r = classificar(imagens(quadros, p), p)
        except Exception as e:  # sem chave, sem rede: o incidente fica sem classificação
            r = {"tipo": "indeterminado", "confianca": "baixa", "descricao": f"erro: {e!r}"[:200]}
        db.execute(
            "INSERT INTO incidentes (camera, inicio_utc, fim_utc, clipes, classe, x, y, tipo,"
            " confianca, descricao, modelo) VALUES (?, ?, ?, 2, ?, ?, ?, ?, ?, ?, ?)",
            (
                camera,
                min(antes),
                clipe_utc,
                p["classe"],
                p["x"],
                p["y"],
                r["tipo"],
                r["confianca"],
                r["descricao"],
                MODELO_VLM,
            ),
        )
        novos.append({**p, **r})
    db.commit()
    return novos
