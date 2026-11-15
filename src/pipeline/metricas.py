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


RESUMO = RAIZ / "saida" / "metricas_resumo.md"


def coletar_conta(marca_id: str = "gg_explica", limite: int = 40, sessao=None) -> list[dict]:
    """Todos os posts da conta (inclusive os postados pelo app), com as métricas de cada um."""
    s = sessao or requests.Session()
    cred = Credenciais.da_marca(marca_id)
    r = s.get(f"{GRAPH}/{cred.versao}/{cred.ig_user_id}/media", params={
        "fields": "id,caption,media_product_type,permalink,timestamp", "limit": limite,
        "access_token": cred.token}, timeout=30)
    r.raise_for_status()
    posts = []
    for m in r.json().get("data", []):
        valores = {}
        for metrica in METRICAS:
            q = s.get(f"{GRAPH}/{cred.versao}/{m['id']}/insights",
                      params={"metric": metrica, "access_token": cred.token}, timeout=30)
            if q.ok and q.json().get("data"):
                valores[metrica] = q.json()["data"][0].get("values", [{}])[0].get("value")
        titulo = (m.get("caption") or "").strip().split("\n")[0][:90]
        posts.append({"titulo": titulo, "tipo": m.get("media_product_type", ""), "quando": m.get("timestamp", "")[:16],
                      "link": m.get("permalink", ""), **valores})
    return posts


def _pontos(p: dict) -> float:
    """Engajamento ponderado: envio e salvamento valem mais que curtida (é o que o Instagram mais empurra)."""
    n = lambda k: float(p.get(k) or 0)
    return n("likes") + 3 * n("comments") + 5 * n("shares") + 4 * n("saved")


def escrever_resumo(posts: list[dict]) -> str:
    """saida/metricas_resumo.md: o que o radar lê para repetir o que funcionou ("aprender com os números")."""
    reels = [p for p in posts if p.get("tipo") == "REELS"]
    linhas = ["# Números da página (Reels, mais recentes primeiro na coleta)", "",
              "views | retenção média (s) | curtidas | coment. | envios | salvos | manchete", "--- | --- | --- | --- | --- | --- | ---"]
    for p in sorted(reels, key=lambda p: -(float(p.get("views") or 0))):
        ret = round(float(p.get("ig_reels_avg_watch_time") or 0) / 1000, 1)
        linhas.append(f"{p.get('views', 0)} | {ret} | {p.get('likes', 0)} | {p.get('comments', 0)} | "
                      f"{p.get('shares', 0)} | {p.get('saved', 0)} | {p['titulo']}")
    if reels:
        melhor_view = max(reels, key=lambda p: float(p.get("views") or 0))
        melhor_eng = max(reels, key=_pontos)
        media_ret = sum(float(p.get("ig_reels_avg_watch_time") or 0) for p in reels) / len(reels) / 1000
        linhas += ["", f"- Mais visto: {melhor_view['titulo']} ({melhor_view.get('views', 0)} views)",
                   f"- Mais engajado (envio e salvamento pesam mais): {melhor_eng['titulo']}",
                   f"- Retenção média: {media_ret:.1f} s. Abaixo de 5 s = o gancho não segura; o primeiro "
                   "segundo precisa mostrar a promessa do vídeo."]
    texto = "\n".join(linhas) + "\n"
    RESUMO.parent.mkdir(parents=True, exist_ok=True)
    RESUMO.write_text(texto, encoding="utf-8")
    return texto
