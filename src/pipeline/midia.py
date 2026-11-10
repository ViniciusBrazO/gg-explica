"""Imagens e vídeos de apoio: fundo em vídeo (Pexels) e foto do produto.

Pexels: banco gratuito com licença que permite uso comercial sem atribuição.
API grátis com limite de 200 pedidos por hora e 20 mil por mês.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

import requests

from .marca import RAIZ

CACHE = RAIZ / "saida" / "cache"
USADOS = CACHE / "pexels_usados.json"


def _usados() -> set[int]:
    try:
        return set(json.loads(USADOS.read_text()))
    except (FileNotFoundError, ValueError):
        return set()


def _marcar_usado(video_id: int) -> None:
    u = _usados()
    u.add(video_id)
    USADOS.parent.mkdir(parents=True, exist_ok=True)
    USADOS.write_text(json.dumps(sorted(u)))


def buscar_broll(termo: str) -> Optional[Path]:
    """Baixa um vídeo vertical do Pexels para o termo. Sem chave, devolve None (usa o fundo da marca)."""
    chave = os.environ.get("PEXELS_API_KEY")
    if not chave or not termo:
        return None
    r = requests.get(
        "https://api.pexels.com/videos/search",
        params={"query": termo, "orientation": "portrait", "size": "medium", "per_page": 20},
        headers={"Authorization": chave}, timeout=30,
    )
    r.raise_for_status()
    usados = _usados()
    for v in r.json().get("videos", []):
        if v["id"] in usados or v.get("duration", 0) < 5:
            continue
        arquivos = [f for f in v["video_files"]
                    if f.get("width") and f.get("height") and f["height"] > f["width"] and f["height"] >= 1280]
        if not arquivos:
            continue
        arq = min(arquivos, key=lambda f: abs(f["height"] - 1920))
        destino = CACHE / "broll" / f"pexels_{v['id']}.mp4"
        if not destino.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(arq["link"], stream=True, timeout=120) as d:
                d.raise_for_status()
                with open(destino, "wb") as f:
                    for pedaco in d.iter_content(1 << 20):
                        f.write(pedaco)
        _marcar_usado(v["id"])
        return destino
    return None


def imagem_produto(origem: str) -> str:
    """Devolve um endereço file:// para a foto do produto (baixa se for URL)."""
    if not origem:
        return ""
    if origem.startswith(("http://", "https://")):
        nome = hashlib.sha1(origem.encode()).hexdigest()[:16]
        destino = CACHE / "produtos" / f"{nome}.img"
        if not destino.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            r = requests.get(origem, timeout=60)
            r.raise_for_status()
            destino.write_bytes(r.content)
        return destino.as_uri()
    caminho = Path(origem)
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    return caminho.as_uri()
