"""Entrada de material: trechos de trailer gravados, prints e imagens salvos em clipes/entrada/.

1. Espera o arquivo parar de crescer (gravação terminada).
2. Move para clipes/AAAA-MM/ com nome de data e hora; .mkv e .mov viram .mp4 sem perder qualidade.
3. Atualiza o catálogo (folha de contato e cortes de cena).
"""
from __future__ import annotations

import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .catalogo import EXT_IMAGENS, EXTENSOES, PASTA_CLIPES, catalogar
from .marca import RAIZ


def _terminado(arquivo: Path, segundos: float, agora: float) -> bool:
    return agora - arquivo.stat().st_mtime >= segundos


def organizar_entrada(entrada: Path, destino_base: Path = PASTA_CLIPES, segundos_parado: float = 45,
                      agora: float | None = None) -> list[Path]:
    agora = agora or time.time()
    movidos = []
    if not entrada.exists():
        entrada.mkdir(parents=True, exist_ok=True)
        return movidos
    for arq in sorted(entrada.iterdir()):
        sufixo = arq.suffix.lower()
        if sufixo not in EXTENSOES | EXT_IMAGENS or not _terminado(arq, segundos_parado, agora):
            continue
        quando = datetime.fromtimestamp(arq.stat().st_mtime)
        if sufixo in EXT_IMAGENS:    # imagem salva à mão (print oficial, foto de divulgação)
            pasta = destino_base / "oficial" / quando.strftime("%Y-%m")
            pasta.mkdir(parents=True, exist_ok=True)
            destino = pasta / arq.name
            shutil.move(str(arq), destino)
            movidos.append(destino)
            continue
        pasta = destino_base / quando.strftime("%Y-%m")
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{quando:%Y-%m-%d_%H%M%S}_{arq.stem[:40]}.mp4"
        if arq.suffix.lower() == ".mp4":
            shutil.move(str(arq), destino)
        else:
            r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(arq), "-c", "copy",
                                "-movflags", "+faststart", str(destino)], capture_output=True, text=True)
            if r.returncode == 0:
                arq.unlink()
            else:   # se a cópia direta falhar, guarda o original como está
                destino = destino.with_suffix(arq.suffix.lower())
                shutil.move(str(arq), destino)
        movidos.append(destino)
    return movidos


def processar(cfg: dict) -> tuple[list[Path], list[dict]]:
    entrada = RAIZ / cfg.get("pasta_entrada", "clipes/entrada")
    movidos = organizar_entrada(entrada, PASTA_CLIPES, cfg.get("segundos_parado", 45))
    novos = catalogar(PASTA_CLIPES) if movidos or not (PASTA_CLIPES / "catalogo.json").exists() else []
    return movidos, novos
