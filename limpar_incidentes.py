"""Limpa do painel os incidentes publicáveis gerados antes do gate de identidade.

Os incidentes `acidente`, `enguico` e `bloqueio` foram classificados por um modelo
de visão que ainda não teve a precisão medida e, até 21/11/2026, abria incidente
só pela posição (fila de semáforo virava "enguiço"). Este script marca esses
incidentes como `indeterminado` — fora do painel — sem apagar `parados`, as
descrições nem o histórico. Idempotente: rodar de novo não muda nada.

Uso:  uv run limpar_incidentes.py
"""

import sqlite3

CAMINHO = "fluxo.db"
PUBLICAVEIS = ("acidente", "enguico", "bloqueio")
MARCA = " [reclassificado indeterminado na limpeza de 21/11/2026]"


def main():
    db = sqlite3.connect(CAMINHO, timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    lugar = ", ".join("?" * len(PUBLICAVEIS))
    antes = db.execute(
        f"SELECT COUNT(*) FROM incidentes WHERE tipo IN ({lugar})", PUBLICAVEIS
    ).fetchone()[0]
    db.execute(
        f"UPDATE incidentes SET tipo='indeterminado', confianca='baixa',"
        f" descricao = descricao || ? WHERE tipo IN ({lugar})",
        (MARCA, *PUBLICAVEIS),
    )
    db.commit()
    depois = db.execute(
        f"SELECT COUNT(*) FROM incidentes WHERE tipo IN ({lugar})", PUBLICAVEIS
    ).fetchone()[0]
    print(f"incidentes publicáveis marcados como indeterminado: {antes}")
    print(f"restam publicáveis: {depois}")


if __name__ == "__main__":
    main()
