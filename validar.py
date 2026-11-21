"""Validação da contagem (fase 2): contagem manual às cegas contra a automática.

uv run validar.py amostrar --condicao noite   guarda clipes para contar
uv run validar.py contar                      contador por teclado, por tipo e sentido
uv run validar.py comparar --todas            roda o contador automático e mostra os erros
uv run validar.py referencia                  conta os clipes com detector maior (sem pessoa)
uv run validar.py comparar --todas --contra referencia   compara com essa referência
uv run validar.py limpar                      apaga os vídeos já contados
uv run validar.py enquadramento 000026 A clipe.mp4 ...   miniaturas de um enquadramento
uv run validar.py sentidos                    foto de cada câmera para confirmar o sentido
"""

import argparse
import base64
import csv
import html
import json
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

import coletor
from coletor import (
    CAMERAS,
    FUSO,
    REGIAO,
    ROTULO_SENTIDO,
    SENTIDOS,
    VEICULOS,
    abrir_clipe,
    contar,
    cruzou,
    descritor,
    linha_do_clipe,
    rastrear,
)

PASTA = Path("validacao")
CLASSES = tuple(VEICULOS.values())
TODOS = "todos"
COLUNAS = [f"{c}_{s}" for c in CLASSES for s in SENTIDOS]
CAMPOS = ["arquivo", "camera", "condicao", *(f"manual_{c}" for c in COLUNAS), "obs"]
CAMPOS_EVENTO = ["arquivo", "quadro", "classe", "sentido"]
LIMIAR = 0.10  # erro aceitável proposto; ver "Dúvidas" em REQUIREMENTS.md
# Folga entre o instante em que a pessoa aperta a tecla e o cruzamento visto pelo sistema
# (reação humana + a pessoa julga pelo corpo do veículo, o sistema pelo pé da caixa).
TOLERANCIA_S = 2.0
AMARELO = (0, 255, 255)
# Folha de sentidos: uma cor por sentido da imagem (BGR), par legível para daltônicos.
COR_SENTIDO = {SENTIDOS[0]: (229, 135, 57), SENTIDOS[1]: (38, 89, 217)}  # azul, laranja
NOME_COR = {SENTIDOS[0]: "Azul", SENTIDOS[1]: "Laranja"}
EXPLICA_SENTIDO = {SENTIDOS[0]: "vêm em direção à câmera", SENTIDOS[1]: "se afastam da câmera"}
JANELA = "Contagem manual"

# Contador manual: fileira de números = desce, fileira de letras logo abaixo = sobe.
TECLAS = {
    **dict(zip("1234", ((c, SENTIDOS[0]) for c in CLASSES), strict=True)),
    **dict(zip("qwer", ((c, SENTIDOS[1]) for c in CLASSES), strict=True)),
}
AJUDA = (
    "desce: " + " ".join(f"{k}={c}" for k, (c, s) in TECLAS.items() if s == SENTIDOS[0]),
    "sobe:  " + " ".join(f"{k}={c}" for k, (c, s) in TECLAS.items() if s == SENTIDOS[1]),
    "espaco=pausa  a=volta 3 s  s=lento  z=desfaz  Enter=grava  Esc=sai sem gravar",
)

# Configurações do detector comparadas por `comparar --todas` (ver "Detecção de motos"
# em REQUIREMENTS.md). A primeira é a que o coletor usa hoje.
PERMISSIVO = {"conf": 0.10, "tracker": "rastreador_permissivo.yaml"}
CONFIGS = {"padrao": {}, "permissivo": PERMISSIVO, "permissivo960": PERMISSIVO | {"imgsz": 960}}


# ---------- planilhas ----------


def _ler(caminho):
    if not caminho.exists():
        return []
    with caminho.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _gravar(caminho, campos, linhas):
    PASTA.mkdir(exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8-sig") as f:
        planilha = csv.DictWriter(f, campos, delimiter=";", extrasaction="ignore", restval="")
        planilha.writeheader()
        planilha.writerows(linhas)


def ler_manual(nome="manual"):
    """Linhas de manual.csv (ou referencia.csv, mesmo formato), um clipe por linha."""
    return _ler(PASTA / f"{nome}.csv")


def gravar_manual(linhas):
    """Regrava manual.csv no formato atual (planilhas antigas, só com total por sentido,
    ganham as colunas por tipo)."""
    _gravar(PASTA / "manual.csv", CAMPOS, linhas)


def contada(linha):
    """Clipe contado = todas as colunas tipo × sentido preenchidas (zero vale)."""
    return all((linha.get(f"manual_{c}") or "").strip().isdigit() for c in COLUNAS)


def ler_eventos(nome="eventos"):
    """eventos.csv → {arquivo: [(quadro, classe, sentido), ...]}: um veículo por linha."""
    eventos = defaultdict(list)
    for e in _ler(PASTA / f"{nome}.csv"):
        eventos[e["arquivo"]].append((int(e["quadro"]), e["classe"], e["sentido"]))
    return eventos


def gravar_eventos(arquivo, eventos):
    """Troca os eventos desse clipe em eventos.csv (recontar substitui, não soma)."""
    todos = ler_eventos() | {arquivo: eventos}
    _gravar(
        PASTA / "eventos.csv",
        CAMPOS_EVENTO,
        [
            dict(zip(CAMPOS_EVENTO, (nome, *e), strict=True))
            for nome, lista in todos.items()
            for e in sorted(lista)
        ],
    )


def totais(eventos):
    """[(quadro, classe, sentido)] → {'carro_desce': n, ...} com todas as colunas."""
    n = Counter(f"{classe}_{sentido}" for _, classe, sentido in eventos)
    return {c: n[c] for c in COLUNAS}


# ---------- contas puras ----------


def parear(manual, auto, tolerancia):
    """Liga cada veículo contado à mão ao cruzamento automático mais próximo no tempo, no
    mesmo sentido. manual, auto: [(quadro, classe, sentido)]; tolerancia em quadros.
    Devolve [{tipo, quadro, sentido, manual, auto}], tipo em: acerto, classe_trocada,
    perdido (só a pessoa viu), a_mais (só o sistema contou: fantasma ou contagem dupla)."""
    # ponytail: pareamento guloso em ordem de tempo; em pelotão denso pode ligar ao vizinho
    # errado (troca a classe apontada), mas o número de perdidos e a mais continua certo.
    pares = []

    def par(tipo, quadro, sentido, m=None, a=None):
        pares.append({"tipo": tipo, "quadro": quadro, "sentido": sentido, "manual": m, "auto": a})

    for s in SENTIDOS:
        m = sorted(e for e in manual if e[2] == s)
        a = sorted(e for e in auto if e[2] == s)
        i = j = 0
        while i < len(m) and j < len(a):
            if abs(m[i][0] - a[j][0]) <= tolerancia:
                igual = m[i][1] == a[j][1]
                par("acerto" if igual else "classe_trocada", m[i][0], s, m[i][1], a[j][1])
                i, j = i + 1, j + 1
            elif m[i][0] < a[j][0]:
                par("perdido", m[i][0], s, m=m[i][1])
                i += 1
            else:
                par("a_mais", a[j][0], s, a=a[j][1])
                j += 1
        for e in m[i:]:
            par("perdido", e[0], s, m=e[1])
        for e in a[j:]:
            par("a_mais", e[0], s, a=e[1])
    return pares


def erros(linhas):
    """linhas: dicts com camera, condicao, auto_<tipo>_<sentido>, manual_<tipo>_<sentido>
    (inteiros) e, se houver contagem por evento, pares (saída de `parear`).
    Devolve {(camera, condicao, sentido, classe)}, classe = cada tipo e 'todos', com:
    clipes, auto, manual, erro_total (com sinal: + = automático contou a mais),
    erro_medio_abs (média do erro absoluto por clipe; None se manual = 0),
    perdidos, a_mais e trocados (contados na classe que a pessoa viu; a_mais, na do sistema)."""
    grupos = defaultdict(lambda: {"pares": [], "perdidos": 0, "a_mais": 0, "trocados": 0})
    for linha in linhas:
        base = linha["camera"], linha["condicao"]
        for s in SENTIDOS:
            auto = {c: linha[f"auto_{c}_{s}"] for c in CLASSES}
            manual = {c: linha[f"manual_{c}_{s}"] for c in CLASSES}
            for c in CLASSES:
                grupos[*base, s, c]["pares"].append((auto[c], manual[c]))
            grupos[*base, s, TODOS]["pares"].append((sum(auto.values()), sum(manual.values())))
        for p in linha.get("pares", ()):
            campo = {"perdido": "perdidos", "a_mais": "a_mais", "classe_trocada": "trocados"}.get(
                p["tipo"]
            )
            if campo:
                for c in (p["auto"] if p["tipo"] == "a_mais" else p["manual"], TODOS):
                    grupos[*base, p["sentido"], c][campo] += 1
    resultado = {}
    for chave, g in sorted(grupos.items()):
        pares = g.pop("pares")
        auto, manual = sum(a for a, _ in pares), sum(m for _, m in pares)
        por_clipe = [abs(a - m) / m for a, m in pares if m]
        resultado[chave] = g | {
            "clipes": len(pares),
            "auto": auto,
            "manual": manual,
            "erro_total": (auto - manual) / manual if manual else None,
            "erro_medio_abs": sum(por_clipe) / len(por_clipe) if por_clipe else None,
        }
    return resultado


# ---------- vídeo ----------


def _h264(caminho):
    """Reencoda para H.264 (abre em qualquer player) se houver ffmpeg."""
    if not shutil.which("ffmpeg"):
        return
    tmp = caminho.with_suffix(".tmp.mp4")
    subprocess.run(  # noqa: S603
        ["ffmpeg", "-v", "error", "-y", "-i", str(caminho), "-pix_fmt", "yuv420p", str(tmp)],  # noqa: S607
        check=True,
    )
    tmp.replace(caminho)


class _Video:
    """Escritor de vídeo que só abre no primeiro quadro (aí sabe o tamanho)."""

    def __init__(self, caminho, fps):
        self.caminho, self.fps, self.saida = Path(caminho), fps, None

    def escrever(self, img):
        import cv2

        if self.saida is None:
            h, w = img.shape[:2]
            self.saida = cv2.VideoWriter(
                str(self.caminho), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (w, h)
            )
        self.saida.write(img)

    def fechar(self):
        if self.saida is not None:
            self.saida.release()
            _h264(self.caminho)


def carregar(video):
    """Lê o clipe inteiro: (quadros em JPEG, quadros por segundo). Em memória para voltar
    e pausar no quadro exato; o índice é o mesmo que o contador automático usa."""
    import cv2

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    quadros = []
    while True:
        ok, img = cap.read()
        if not ok:
            break
        quadros.append(cv2.imencode(".jpg", img)[1])
    cap.release()
    return quadros, fps


def _fps(video):
    import cv2

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    cap.release()
    return fps


def _tela(jpeg, linha, eventos, i, total, fps, pausado, lento):
    """Quadro do contador manual: linha, contagem por sentido, últimos toques e ajuda."""
    import cv2

    def texto(msg, y, escala=0.45):
        cv2.putText(img, msg, (9, y + 1), cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), 3)
        cv2.putText(img, msg, (8, y), cv2.FONT_HERSHEY_SIMPLEX, escala, AMARELO, 1)

    img = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
    h = img.shape[0]
    a, b = (tuple(map(int, p)) for p in linha)
    cv2.line(img, a, b, AMARELO, 2)
    cv2.rectangle(img, (0, 0), (470, 64), (0, 0, 0), -1)  # fundo para o texto ficar legível
    cv2.rectangle(img, (0, h - 58), (570, h), (0, 0, 0), -1)
    n = totais(eventos)
    estado = ("  PAUSADO" if pausado else "") + ("  0,5x" if lento else "")
    texto(f"{i / fps:5.1f} s de {total / fps:.0f} s{estado}", 18, 0.55)
    for k, s in enumerate(SENTIDOS):
        texto(f"{s}: " + "  ".join(f"{c} {n[f'{c}_{s}']}" for c in CLASSES), 38 + 18 * k)
    recentes = [f"+ {c} {s}" for q, c, s in eventos if 0 <= i - q <= fps]
    for k, msg in enumerate(recentes[-4:]):
        texto(msg, 82 + 20 * k, 0.6)
    for k, msg in enumerate(AJUDA):
        texto(msg, h - 42 + 16 * k)
    return img


def sessao(quadros, linha, fps, ler_tecla, mostrar):
    """Laço do contador manual sobre um clipe. ler_tecla(ms) devolve o código da tecla
    (-1 se nenhuma); mostrar(imagem) exibe o quadro. Devolve os eventos
    [(quadro, classe, sentido)] em ordem de tempo, ou None se a pessoa saiu sem gravar."""
    eventos, i, pausado, lento = [], 0, False, False
    ultimo = len(quadros) - 1
    while True:
        mostrar(_tela(quadros[i], linha, eventos, i, len(quadros), fps, pausado, lento))
        codigo = ler_tecla(max(1, round(1000 / fps * (2 if lento else 1))))
        tecla = chr(codigo).lower() if 0 <= codigo < 256 else ""
        if tecla in TECLAS:
            eventos.append((i, *TECLAS[tecla]))
        elif tecla == " ":
            pausado = not pausado
        elif tecla == "s":
            lento = not lento
        elif tecla == "a":
            i = max(0, i - round(3 * fps))
        elif tecla == "z" and eventos:
            eventos.pop()  # desfaz o último toque, não o mais tardio no vídeo
        elif tecla == "\r":
            return sorted(eventos)
        elif tecla == "\x1b":
            return None
        if not pausado and i < ultimo:
            i += 1


def eventos_auto(video, camera, modelo, passo, diag=None, **detector):
    """Cruzamentos que o contador automático vê no clipe: [(quadro, classe, sentido)].
    Se diag for um caminho, grava vídeo com caixas, IDs e contagem acumulada."""
    import cv2

    linha, _, _ = linha_do_clipe(camera, video)
    a, b = (tuple(map(int, p)) for p in linha)
    saida = _Video(diag, _fps(video) / passo) if diag else None
    cruzamentos, quadro = {}, 0  # id da trajetória → (quadro, sentido) do 1º cruzamento

    def ao_quadro(r, pontos):
        nonlocal quadro
        for tid, pts in pontos.items():
            if tid not in cruzamentos and len(pts) > 1 and (s := cruzou(pts[-2], pts[-1], *linha)):
                cruzamentos[tid] = (quadro * passo, SENTIDOS[0] if s > 0 else SENTIDOS[1])
        quadro += 1
        if saida:
            img = r.plot(line_width=1)
            n = Counter(s for _, s in cruzamentos.values())
            cv2.line(img, a, b, AMARELO, 2)
            texto = "  ".join(f"{s} {n[s]}" for s in SENTIDOS)
            cv2.putText(
                img, texto, (10, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, AMARELO, 2
            )
            saida.escrever(img)

    trajetorias, _, _ = rastrear(video, modelo, passo, ao_quadro, **detector)
    if saida:
        saida.fechar()
    # a classe só fica definida no fim do clipe (a mais frequente da trajetória)
    eventos = sorted((q, trajetorias[tid][0], s) for tid, (q, s) in cruzamentos.items())
    # a validação tem de medir exatamente o que o coletor grava
    assert Counter(f"{c}_{s}" for _, c, s in eventos) == contar(trajetorias, linha)
    return eventos


# ---------- comandos ----------


def amostrar(args):
    linhas = ler_manual()
    for rodada in range(args.clipes):
        inicio = time.monotonic()
        for camera in CAMERAS:
            try:
                resp, utc = abrir_clipe(camera)
                nome = f"{camera}_{utc[:19].replace('-', '').replace(':', '')}"
                original = PASTA / f"{nome}.mp4"
                with resp:
                    if original.exists():
                        print(nome, "clipe repetido")
                        continue
                    PASTA.mkdir(exist_ok=True)
                    original.write_bytes(resp.read())
                linhas.append({"arquivo": nome, "camera": camera, "condicao": args.condicao})
                gravar_manual(linhas)
                print(nome, "guardado", flush=True)
            except Exception as e:  # servidor instável: segue para a próxima
                print(camera, "ERRO", repr(e), flush=True)
        if rodada < args.clipes - 1:  # o servidor renova o clipe a cada ~62 s
            time.sleep(max(0, 65 - (time.monotonic() - inicio)))


def contar_manual(_args):
    """Abre cada clipe ainda não contado no contador por teclado e grava o resultado."""
    import cv2

    def ler_tecla(ms):
        codigo = cv2.waitKey(ms)
        fechada = cv2.getWindowProperty(JANELA, cv2.WND_PROP_VISIBLE) < 1
        return 27 if fechada else codigo

    linhas = ler_manual()
    pendentes = [x for x in linhas if not contada(x) and (PASTA / f"{x['arquivo']}.mp4").exists()]
    if not pendentes:
        print("Nenhum clipe por contar. Guarde mais com: uv run validar.py amostrar")
        return
    for n, linha in enumerate(pendentes, 1):
        quadros, fps = carregar(PASTA / f"{linha['arquivo']}.mp4")
        cv2.namedWindow(JANELA, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(JANELA, 1200, 675)
        cv2.setWindowTitle(JANELA, f"{JANELA}: clipe {n} de {len(pendentes)}")
        eventos = sessao(
            quadros,
            linha_do_clipe(linha["camera"], PASTA / f"{linha['arquivo']}.mp4")[0],
            fps,
            ler_tecla,
            lambda img: cv2.imshow(JANELA, img),
        )
        if eventos is None:
            print(linha["arquivo"], "não gravado; parando")
            break
        gravar_eventos(linha["arquivo"], eventos)
        linha.update({f"manual_{c}": v for c, v in totais(eventos).items()})
        gravar_manual(linhas)
        print(linha["arquivo"], "gravado:", len(eventos), "veículos", flush=True)
    cv2.destroyAllWindows()


def _rodar(args, detector, manuais, eventos):
    """Roda uma configuração do detector sobre os clipes contados; grava resultado e
    divergências por clipe. Devolve as linhas para `erros`."""
    from ultralytics import YOLO

    # só o tracker é caminho; Path("0.1").stem daria "0" e confianças diferentes colidiriam
    etiqueta = "".join(
        f"_{k}{Path(v).stem if isinstance(v, str) else v}" for k, v in detector.items()
    )
    sufixo = f"{Path(args.modelo).stem}_passo{args.passo}{etiqueta}"
    if args.contra != "manual":
        sufixo += f"_contra_{args.contra}"
    linhas, divergencias = [], []
    for linha in manuais:
        nome = linha["arquivo"]
        original = PASTA / f"{nome}.mp4"
        if not original.exists():
            print(nome, "sem vídeo (já limpo?), ignorado")
            continue
        diag = PASTA / f"{nome}_diag{etiqueta}.mp4" if args.diag else None
        auto = eventos_auto(
            original, linha["camera"], YOLO(args.modelo), args.passo, diag, **detector
        )
        fps = _fps(original)
        # sem eventos (clipe contado direto na planilha) não há o que parear
        pares = parear(eventos[nome], auto, TOLERANCIA_S * fps) if nome in eventos else []
        divergencias += [
            {"arquivo": nome, "t_s": round(p["quadro"] / fps, 1)} | p
            for p in pares
            if p["tipo"] != "acerto"
        ]
        linhas.append(
            {
                "arquivo": nome,
                "camera": linha["camera"],
                "condicao": linha["condicao"],
                **{f"auto_{c}": n for c, n in totais(auto).items()},
                **{f"manual_{c}": int(linha[f"manual_{c}"]) for c in COLUNAS},
                "pares": pares,
            }
        )
        print(sufixo, nome, "ok", flush=True)
    if linhas:
        parametros = {
            "modelo": args.nome_modelo,
            "passo": args.passo,
            "detector": str(detector),
        }
        campos = [k for k in linhas[0] if k != "pares"] + [*parametros, "linha"]
        _gravar(
            PASTA / f"resultado_{sufixo}.csv",
            campos,
            [
                x
                | parametros
                | {"linha": linha_do_clipe(x["camera"], PASTA / f"{x['arquivo']}.mp4")[0]}
                for x in linhas
            ],
        )
        _gravar(
            PASTA / f"divergencias_{sufixo}.csv",
            ["arquivo", "t_s", "quadro", "sentido", "tipo", "manual", "auto"],
            divergencias,
        )
    return linhas


def comparar(args):
    import ultralytics

    args.nome_modelo = f"{args.modelo}@ultralytics{ultralytics.__version__}"
    manuais = list(filter(contada, ler_manual(args.contra)))
    if not manuais:
        print(f"Nenhum clipe em {args.contra}.csv. Rode: uv run validar.py", COMANDO[args.contra])
        return
    configs = CONFIGS if args.todas else {"escolhida": _detector(args)}
    eventos = ler_eventos("eventos" if args.contra == "manual" else f"eventos_{args.contra}")
    tabela = defaultdict(dict)  # (câmera, condição, sentido, classe) → {configuração: erro}
    for nome, detector in configs.items():
        for chave, e in erros(_rodar(args, detector, manuais, eventos)).items():
            tabela[chave][nome] = e

    def pct(x):
        return "n/d" if x is None else f"{x:+.1%}"

    print(f"\n{args.nome_modelo}, passo {args.passo}. Detalhe por clipe em {PASTA}/resultado_*.csv")
    if args.contra != "manual":
        print(
            f"ATENÇÃO: a coluna 'manual' é {args.contra}.csv (outro detector), não contagem humana."
        )
    print("e veículo a veículo em divergencias_*.csv (t_s = segundo do clipe).")
    print(
        f"{'câmera':<7} {'condição':<10} {'sentido':<6} {'tipo':<9} {'configuração':<14}"
        f" {'auto':>5} {'manual':>6} {'erro':>8} {'erro/clipe':>10}"
        f" {'perdidos':>8} {'a mais':>6} {'trocados':>8}"
    )
    for (camera, condicao, sentido, classe), por_config in sorted(tabela.items()):
        for nome, e in por_config.items():
            if not e["auto"] and not e["manual"]:
                continue
            acima = e["erro_total"] is not None and abs(e["erro_total"]) > LIMIAR
            print(
                f"{camera:<7} {condicao:<10} {sentido:<6} {classe:<9} {nome:<14}"
                f" {e['auto']:>5} {e['manual']:>6} {pct(e['erro_total']):>8}"
                f" {pct(e['erro_medio_abs']):>10}"
                f" {e['perdidos']:>8} {e['a_mais']:>6} {e['trocados']:>8}"
                f"{'  ACIMA DO LIMIAR' if acima else ''}"
            )


COMANDO = {"manual": "contar", "referencia": "referencia --modelo yolo11x.pt --imgsz 1280"}


def _detector(args):
    opcoes = (("imgsz", args.imgsz), ("conf", args.conf), ("tracker", args.tracker))
    return {k: v for k, v in opcoes if v is not None}


def referencia(args):
    """Conta todos os clipes guardados com um detector mais forte e grava referencia.csv e
    eventos_referencia.csv no formato da contagem manual. Não é verdade de campo: mede
    quanto a contagem do coletor muda com mais modelo e resolução, não o erro real.
    Grava a cada clipe e, se rodar de novo com o mesmo detector, pula os clipes já feitos
    (o yolo11x a 1280 px leva de 2 a 4 min por clipe)."""
    from ultralytics import YOLO

    detector = _detector(args)
    obs = f"referência {args.modelo} {detector}"
    feitas = {x["arquivo"]: x for x in ler_manual("referencia") if x["obs"] == obs}
    eventos = ler_eventos("eventos_referencia")
    for linha in ler_manual():
        nome = linha["arquivo"]
        video = PASTA / f"{nome}.mp4"
        if nome in feitas or not video.exists():
            print(nome, "já feito" if nome in feitas else "sem vídeo", "- pulado")
            continue
        eventos[nome] = eventos_auto(video, linha["camera"], YOLO(args.modelo), 1, **detector)
        feitas[nome] = (
            linha | {f"manual_{c}": n for c, n in totais(eventos[nome]).items()} | {"obs": obs}
        )
        _gravar(PASTA / "referencia.csv", CAMPOS, feitas.values())
        _gravar(
            PASTA / "eventos_referencia.csv",
            CAMPOS_EVENTO,
            [
                dict(zip(CAMPOS_EVENTO, (n, *e), strict=True))
                for n in feitas
                for e in eventos.get(n, ())
            ],
        )
        print(nome, len(eventos[nome]), "veículos", flush=True)


def enquadramento(args):
    """Acrescenta miniaturas (descritores) de clipes ao enquadramento `nome` da câmera em
    enquadramentos.json. Cada clipe contribui com o quadro do meio e o primeiro."""
    import cv2

    caminho = coletor.ENQUADRAMENTOS
    todas = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    lista = todas.setdefault(args.camera, {}).setdefault(args.nome, [])
    for arquivo in args.clipes:
        cap = cv2.VideoCapture(arquivo)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for i in (0, n // 2):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, quadro = cap.read()
            if ok:
                lista.append([int(round(x * 10)) for x in descritor(quadro)])
        cap.release()
    caminho.write_text(json.dumps(todas, separators=(",", ":")), encoding="utf-8")
    coletor._referencias.cache_clear()
    print(args.camera, args.nome, len(lista), "miniaturas em", caminho.name)


# ---------- folha de sentidos ----------


def sentido_de(pontos, linha):
    """Sentido do primeiro cruzamento da trajetória com a linha (o mesmo de contar), ou None."""
    for p0, p1 in zip(pontos, pontos[1:], strict=False):
        if s := cruzou(p0, p1, *linha):
            return SENTIDOS[0] if s > 0 else SENTIDOS[1]
    return None


def desenhar_sentidos(quadro, linha, trajetorias):
    """Quadro escurecido com a linha de contagem e cada trajetória que a cruzou, na cor do
    sentido e com seta no fim. Devolve (imagem, Counter de veículos por sentido)."""
    import cv2
    import numpy as np

    img = (quadro * 0.45).astype(quadro.dtype)
    n = Counter()
    for _, pontos in trajetorias.values():
        if not (s := sentido_de(pontos, linha)):
            continue
        n[s] += 1
        cor, pts = COR_SENTIDO[s], [tuple(map(int, p)) for p in pontos]
        cv2.polylines(img, [np.array(pts)], False, cor, 2, cv2.LINE_AA)
        fim = pts[-1]
        ini = next(
            (p for p in reversed(pts) if np.hypot(p[0] - fim[0], p[1] - fim[1]) >= 30), pts[0]
        )
        comp = max(1.0, float(np.hypot(ini[0] - fim[0], ini[1] - fim[1])))
        cv2.arrowedLine(img, ini, fim, cor, 3, cv2.LINE_AA, tipLength=min(1.0, 16 / comp))
    a, b = (tuple(map(int, p)) for p in linha)
    cv2.line(img, a, b, AMARELO, 2, cv2.LINE_AA)
    return img, n


def pagina_sentidos(fichas):
    """HTML local com a foto de cada câmera (embutida, a página abre sozinha em qualquer
    lugar) e a pergunta: para onde vai cada cor?"""
    from datetime import datetime

    local = {p["id"]: p for p in REGIAO}
    blocos = []
    for f in fichas:
        cam, cfg = f["camera"], CAMERAS[f["camera"]]
        hora = datetime.fromisoformat(f["utc"]).astimezone(FUSO).strftime("%d/%m %H:%M")
        enq = f" · enquadramento {f['enquadramento']}" if f["enquadramento"] else ""
        cores = "".join(
            f'<li><b style="color:#{"".join(f"{c:02x}" for c in COR_SENTIDO[s][::-1])}">'
            f"{NOME_COR[s]}</b>: "
            f"{f[s]} veículos que {EXPLICA_SENTIDO[s]} (no sistema, “{s}”). "
            f"Hoje o painel chama de “{ROTULO_SENTIDO[s]}”.</li>"
            for s in SENTIDOS
        )
        estado = "confirmado" if cfg["sentido_confirmado"] else "ainda não confirmado"
        lat, lon = local[cam]["lat"], local[cam]["lon"]
        blocos.append(
            f"<section><h2>{html.escape(cfg['nome'])} <small>{cam} · clipe de {hora}{enq}"
            f"</small></h2><img src='data:image/jpeg;base64,{base64.b64encode(f['jpg']).decode()}' "
            f"alt='Quadro da câmera {cam} "
            f"com as trajetórias coloridas'><ul>{cores}</ul><p>Sentido {estado}. "
            f"<a href='https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}'>"
            "Ver o local no mapa</a> (posição aproximada).</p></section>"
        )
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Sentidos das câmeras</title><style>"
        "body{background:#040b09;color:#e6fff6;font:16px/1.5 system-ui,sans-serif;"
        "max-width:900px;margin:0 auto;padding:16px}h2{font-size:20px;margin:32px 0 8px}"
        "small{color:#9fc4b8;font-weight:400;font-size:14px}img{width:100%;border-radius:3px}"
        "a{color:#2ee6b6}li{margin:4px 0}</style></head><body>"
        "<h1>Para onde vai cada cor?</h1><p>Cada linha é um veículo que cruzou a linha amarela "
        "de contagem no último clipe; a seta aponta para onde ele foi. Responda por câmera: "
        "“certo”, “invertido” ou para onde vão o azul e o laranja (por exemplo, "
        "“azul vai para a ponte”).</p>" + "".join(blocos) + "</body></html>"
    )


def sentidos(args):
    """Baixa o clipe atual de cada câmera, desenha as trajetórias que cruzaram a linha e
    monta validacao/sentidos/index.html. O vídeo é apagado; fica só o quadro desenhado."""
    import cv2
    from ultralytics import YOLO

    pasta = PASTA / "sentidos"
    pasta.mkdir(parents=True, exist_ok=True)
    modelo = YOLO(args.modelo)
    fichas = []
    for camera in args.cameras or CAMERAS:
        video = pasta / f"{camera}.mp4"
        try:
            resp, utc = abrir_clipe(camera)
            with resp:
                video.write_bytes(resp.read())
            linha, enq, _ = linha_do_clipe(camera, video)
            trajetorias, _, _ = rastrear(video, modelo, 1, **CONFIGS["permissivo960"])
            cap = cv2.VideoCapture(str(video))
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
            ok, quadro = cap.read()
            cap.release()
            if not ok:
                raise ValueError("clipe sem quadro legível")
            img, n = desenhar_sentidos(quadro, linha, trajetorias)
            jpg = cv2.imencode(".jpg", img)[1].tobytes()
            (pasta / f"{camera}.jpg").write_bytes(jpg)
            fichas.append(
                {"camera": camera, "utc": utc, "enquadramento": enq, "jpg": jpg}
                | {s: n[s] for s in SENTIDOS}
            )
            print(camera, dict(n), flush=True)
        except Exception as e:  # servidor instável: segue para a próxima
            print(camera, "ERRO", repr(e), flush=True)
        finally:
            video.unlink(missing_ok=True)
    (pasta / "index.html").write_text(pagina_sentidos(fichas), encoding="utf-8")
    print("abra", (pasta / "index.html").resolve())


def limpar(_args):
    """Apaga os vídeos dos clipes já contados; os números ficam nos CSV."""
    for linha in filter(contada, ler_manual()):
        for video in PASTA.glob(f"{linha['arquivo']}*.mp4"):
            video.unlink()
            print("apagado", video.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    a = sub.add_parser("amostrar", help="guarda clipes para contagem manual")
    a.add_argument("--condicao", required=True, help="ex.: dia, noite, pico-tarde, chuva")
    a.add_argument("--clipes", type=int, default=1, help="clipes seguidos por câmera")
    a.set_defaults(func=amostrar)
    m = sub.add_parser("contar", help="contador manual por teclado")
    m.set_defaults(func=contar_manual)
    c = sub.add_parser("comparar", help="automático contra manual")
    c.add_argument("--todas", action="store_true", help=f"compara {', '.join(CONFIGS)}")
    c.add_argument("--passo", type=int, default=1)
    c.add_argument("--modelo", default="yolo11n.pt")
    c.add_argument("--imgsz", type=int, help="resolução do detector (padrão: 640)")
    c.add_argument("--conf", type=float, help="confiança mínima (padrão: 0,25)")
    c.add_argument("--tracker", help="yaml do rastreador, ex.: rastreador_permissivo.yaml")
    c.add_argument("--diag", action="store_true", help="grava vídeo com caixas e IDs")
    c.add_argument("--contra", choices=tuple(COMANDO), default="manual", help="base da comparação")
    c.set_defaults(func=comparar)
    r = sub.add_parser("referencia", help="contagem por detector mais forte, sem pessoa")
    r.add_argument("--modelo", default="yolo11x.pt")
    r.add_argument("--imgsz", type=int, default=1280)
    r.add_argument("--conf", type=float)
    r.add_argument("--tracker")
    r.set_defaults(func=referencia)
    e = sub.add_parser("enquadramento", help="guarda miniaturas de um enquadramento da câmera")
    e.add_argument("camera")
    e.add_argument("nome", help="ex.: A (duas pistas) ou B (só a pista que se afasta)")
    e.add_argument("clipes", nargs="+", help="vídeos .mp4 desse enquadramento")
    e.set_defaults(func=enquadramento)
    sub.add_parser("limpar", help="apaga vídeos já contados").set_defaults(func=limpar)
    t = sub.add_parser("sentidos", help="foto de cada câmera com as trajetórias por sentido")
    t.add_argument("cameras", nargs="*", help="padrão: todas as câmeras contadas")
    t.add_argument("--modelo", default="yolo11s.pt")
    t.set_defaults(func=sentidos)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
