"""Coleta as métricas dos Reels publicados e grava em saida/metricas.csv.

O Claude lê esse CSV toda semana para decidir o que repetir e o que cortar.
Métricas pedidas uma a uma: se a Meta renomear ou remover alguma, as outras continuam vindo.
"""
from __future__ import annotations

import csv
from datetime import datetime

import requests

from .fila import FUSO, carregar
from .instagram import Credenciais, GRAPH
from .marca import RAIZ

ARQUIVO = RAIZ / "saida" / "metricas.csv"
METRICAS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
            "ig_reels_avg_watch_time"]


def coletar() -> int:
    linhas = []
    agora = datetime.now(FUSO).isoformat(timespec="minutes")
    for item in carregar():
        if item.status != "publicado" or not item.media_id or item.plataforma != "instagram":
            continue
        cred = Credenciais.da_marca(item.marca)
        valores = {}
        for m in METRICAS:
            r = requests.get(f"{GRAPH}/{cred.versao}/{item.media_id}/insights",
                             params={"metric": m, "access_token": cred.token}, timeout=30)
            if r.ok:
                dados = r.json().get("data", [])
                if dados:
                    valores[m] = dados[0].get("values", [{}])[0].get("value")
        linhas.append({"coletado_em": agora, "marca": item.marca, "video": item.id,
                       "publicado_para": item.quando, "permalink": item.permalink, **valores})
    if not linhas:
        return 0
    novo = not ARQUIVO.exists()
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    campos = ["coletado_em", "marca", "video", "publicado_para", "permalink", *METRICAS]
    with open(ARQUIVO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if novo:
            w.writeheader()
        w.writerows(linhas)
    return len(linhas)
