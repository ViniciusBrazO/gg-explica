"""Biblioteca oficial: baixa os pacotes que a própria Rockstar oferece na página de mídia de GTA VI
("Download and share trailers, imagery, and more") e cataloga tudo.

- trailers e clipes oficiais (cada plano vira um trecho catalogado);
- screenshots, artes e wallpapers oficiais.

Só baixa de novo quando o pacote muda (tamanho ou data no servidor). Os links ficam em
config/automacao.yaml; se a Rockstar mudar a página, atualize ali.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from .catalogo import EXT_IMAGENS, EXTENSOES, PASTA_CLIPES, catalogar
from .marca import RAIZ
from .radar import config

PASTA_OFICIAL = PASTA_CLIPES / "oficial"
ESTADO = RAIZ / "saida" / "biblioteca.json"


def _estado() -> dict:
    return json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}


def extrair(zip_path: Path, destino: Path) -> list[Path]:
    """Extrai só imagens e vídeos, sem subpastas e sem deixar caminho escapar da pasta."""
    destino.mkdir(parents=True, exist_ok=True)
    extraidos = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            nome = Path(info.filename).name
            if info.is_dir() or not nome or Path(nome).suffix.lower() not in EXTENSOES | EXT_IMAGENS:
                continue
            alvo = destino / nome
            if alvo.exists() and alvo.stat().st_size == info.file_size:
                continue
            with z.open(info) as origem, open(alvo, "wb") as saida:
                shutil.copyfileobj(origem, saida, 1024 * 1024)
            extraidos.append(alvo)
    return extraidos


def atualizar(sessao=None, so: Optional[str] = None, mostrar=print) -> list[Path]:
    """Baixa os pacotes novos ou alterados e cataloga. `so` filtra pelo nome do pacote."""
    cfg = config().get("biblioteca", {})
    sessao = sessao or requests.Session()
    estado = _estado()
    novos: list[Path] = []
    for pacote in cfg.get("pacotes", []):
        if so and so not in pacote["nome"]:
            continue
        url = pacote["url"]
        cab = sessao.head(url, timeout=30, allow_redirects=True)
        if cab.status_code >= 400:
            mostrar(f"  {pacote['nome']}: o servidor respondeu {cab.status_code} (o link mudou?)")
            continue
        assinatura = f"{cab.headers.get('Content-Length', '')}|{cab.headers.get('Last-Modified', '')}"
        pasta = PASTA_OFICIAL / pacote["nome"]
        tem_arquivos = pasta.exists() and any(pasta.iterdir())
        if estado.get(url, {}).get("assinatura") == assinatura and tem_arquivos:
            mostrar(f"  {pacote['nome']}: sem novidade")
            continue
        tamanho_mb = int(cab.headers.get("Content-Length", 0) or 0) / 1e6
        mostrar(f"  {pacote['nome']}: baixando {tamanho_mb:.0f} MB...")
        zips = PASTA_OFICIAL / "_zips"
        zips.mkdir(parents=True, exist_ok=True)
        arq_zip = zips / f"{pacote['nome']}.zip"
        with sessao.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(arq_zip, "wb") as f:
                for pedaco in r.iter_content(1024 * 1024):
                    f.write(pedaco)
        extraidos = extrair(arq_zip, PASTA_OFICIAL / pacote["nome"])
        arq_zip.unlink(missing_ok=True)       # o zip ocupa espaço à toa depois de extraído
        if estado.get(url, {}).get("assinatura") != assinatura:
            novos += extraidos                # só pacote que mudou é novidade (baixar de novo não é)
        estado[url] = {"assinatura": assinatura, "atualizado": datetime.now().isoformat(),
                       "arquivos": len(extraidos)}
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
        mostrar(f"  {pacote['nome']}: {len(extraidos)} arquivo(s) novo(s)")
    # vídeo do player oficial não é "material novo da Rockstar": não dispara alerta nem post
    baixar_videos(cfg.get("videos", []), sessao, mostrar)
    catalogar(PASTA_CLIPES)        # também refaz as folhas quando a biblioteca foi baixada de novo
    return novos


def baixar_videos(videos: list[dict], sessao, mostrar=print) -> list[Path]:
    """Vídeos oficiais servidos pelo CDN de vídeos da própria Rockstar (rockstargames.com/videos):
    baixa uma vez para clipes/oficial/trailers e cataloga plano a plano."""
    pasta = PASTA_OFICIAL / "trailers"
    novos = []
    for v in videos:
        destino = pasta / f"{v['nome']}.mp4"
        if destino.exists() and destino.stat().st_size > 1_000_000:
            continue
        pasta.mkdir(parents=True, exist_ok=True)
        mostrar(f"  {v['nome']}: baixando do site oficial da Rockstar...")
        with sessao.get(v["url"], stream=True, timeout=120) as r:
            if r.status_code >= 400:
                mostrar(f"  {v['nome']}: o servidor respondeu {r.status_code}")
                continue
            with open(destino, "wb") as f:
                for pedaco in r.iter_content(1024 * 1024):
                    f.write(pedaco)
        mostrar(f"  {v['nome']}: {destino.stat().st_size / 1e6:.0f} MB")
        novos.append(destino)
        # entra no estado da biblioteca: a chave do cache muda e o vídeo fica guardado para as próximas rodadas
        estado = _estado()
        estado[v["url"]] = {"assinatura": str(destino.stat().st_size), "atualizado": datetime.now().isoformat(),
                            "arquivos": 1}
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    return novos
