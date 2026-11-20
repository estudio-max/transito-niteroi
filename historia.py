"""Guardar história para poder prever: chuva por hora e cópia diária do banco.

Os dois rodam no laço do coletor, junto da publicação; falha aqui não para a contagem.
"""

import json
import sqlite3
import subprocess
import tempfile
import urllib.request
from pathlib import Path

# Centro de Niterói, perto da saída da Ponte.
LAT, LON = -22.885, -43.115
URL_CLIMA = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&hourly=precipitation,temperature_2m&past_days=2&forecast_days=1&timezone=UTC"
)
PASTA_BACKUP = "backup-transito"  # no servidor, fora da pasta pública do site


def criar_tabela_clima(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS clima (hora_utc TEXT PRIMARY KEY, chuva_mm REAL,"
        " temperatura_c REAL, fonte TEXT)"
    )


def horas_clima(resposta, agora_utc):
    """Do JSON do Open-Meteo, as horas já passadas: [(hora_utc ISO, chuva, temperatura)].
    Horas futuras são previsão e não entram."""
    h = resposta["hourly"]
    saida = []
    for t, chuva, temp in zip(h["time"], h["precipitation"], h["temperature_2m"], strict=True):
        hora = f"{t}:00+00:00"  # "2026-11-19T15:00" → ISO com fuso, como clipe_utc
        if hora <= agora_utc and chuva is not None:
            saida.append((hora, chuva, temp))
    return saida


def atualizar_clima(db, agora_utc, buscar=None):
    """Grava (ou corrige) chuva e temperatura das últimas 48 h. O Open-Meteo é gratuito,
    sem chave; o valor é a estimativa do modelo meteorológico para o ponto, não uma
    estação. Devolve quantas horas gravou."""

    def _buscar():
        req = urllib.request.Request(
            URL_CLIMA.format(lat=LAT, lon=LON), headers={"User-Agent": "fluxo-niteroi"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    linhas = horas_clima((buscar or _buscar)(), agora_utc)
    criar_tabela_clima(db)
    db.executemany(
        "INSERT OR REPLACE INTO clima VALUES (?, ?, ?, 'open-meteo')",
        linhas,
    )
    db.commit()
    return len(linhas)


def copiar_banco(banco, destino_scp, dia, executar=subprocess.run):
    """Cópia consistente do banco (API de backup do SQLite, segura com o coletor
    gravando) enviada ao servidor como backup-transito/fluxo-AAAA-MM-DD.db.
    destino_scp é o mesmo de --publicar ("host:pasta"); só o host é usado.
    ponytail: guarda uma cópia por dia, sem apagar as antigas; o banco é pequeno."""
    host = destino_scp.split(":", 1)[0]
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / f"fluxo-{dia}.db"
        origem = sqlite3.connect(banco)
        alvo = sqlite3.connect(copia)
        origem.backup(alvo)
        alvo.close()
        origem.close()
        executar(
            ["ssh", "-o", "BatchMode=yes", host, "mkdir", "-p", PASTA_BACKUP],
            check=True,
            timeout=60,
        )
        executar(
            ["scp", "-q", "-o", "BatchMode=yes", str(copia), f"{host}:{PASTA_BACKUP}/"],
            check=True,
            timeout=120,
        )
    return f"{host}:{PASTA_BACKUP}/fluxo-{dia}.db"
