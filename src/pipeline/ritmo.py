"""Freio de publicação: quantos posts por dia e com que intervalo, por rede.

A API do Instagram aceita até 100 posts em 24 h, mas uma conta e um app novos publicando em rajada
parecem robô para a Meta (foi o que levou à checagem de "atividade incomum" em 11/11/2026). O freio
segura o post na fila até a próxima rodada; nada se perde.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .radar import config

PADRAO = {"max_24h": 6, "minutos_entre_posts": 90}


def limites(plataforma: str) -> dict:
    cfg = config().get("publicacao", {})
    return PADRAO | cfg.get("padrao", {}) | cfg.get(plataforma, {})


def _saiu_em(item) -> datetime | None:
    if item.status != "publicado":
        return None
    try:
        return datetime.fromisoformat(item.publicado_em or item.quando)
    except ValueError:
        return None


def motivo_para_segurar(item, itens, agora: datetime) -> str:
    """'' se pode sair agora; senão, o motivo de esperar."""
    if getattr(item, "furar_freio", False):
        return ""
    lim = limites(item.plataforma)
    saidas = sorted(t for i in itens if i.plataforma == item.plataforma and i.marca == item.marca
                    and (t := _saiu_em(i)))
    ultimas_24h = [t for t in saidas if agora - t < timedelta(hours=24)]
    if len(ultimas_24h) >= lim["max_24h"]:
        libera = ultimas_24h[0] + timedelta(hours=24)
        return f"limite de {lim['max_24h']} posts em 24 h (libera às {libera:%H:%M})"
    if saidas and agora - saidas[-1] < timedelta(minutes=lim["minutos_entre_posts"]):  # inclui o desta rodada
        return f"o último saiu às {saidas[-1]:%H:%M}; intervalo mínimo de {lim['minutos_entre_posts']} min"
    return ""
