"""Lê duração, resolução e faixas de um arquivo de mídia.

Usa o ffprobe quando existe; senão, lê a saída do `ffmpeg -i` (o runner da nuvem pode cair no
ffmpeg do pip, que não traz ffprobe).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


def _pelo_ffmpeg(arquivo: Path) -> dict:
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(arquivo)],
                       capture_output=True, text=True)
    texto = r.stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", texto)
    if not m and "Stream #" not in texto:
        raise RuntimeError(f"não deu para ler {arquivo}: {texto[-300:]}")
    formato = {}
    if m:
        h, mi, s = m.groups()
        formato["duration"] = str(int(h) * 3600 + int(mi) * 60 + float(s))
    faixas = []
    for linha in texto.splitlines():
        t = re.search(r"Stream #.*?:\s*(Video|Audio):", linha)
        if not t:
            continue
        faixa = {"codec_type": t.group(1).lower()}
        if faixa["codec_type"] == "video":
            d = re.search(r",\s*(\d{2,5})x(\d{2,5})", linha)
            if d:
                faixa["width"], faixa["height"] = int(d.group(1)), int(d.group(2))
        faixas.append(faixa)
    return {"streams": faixas, "format": formato}


def sondar(arquivo: Path | str) -> dict:
    """{"streams": [{"codec_type", "width", "height"}], "format": {"duration"}}, como o ffprobe."""
    arquivo = Path(arquivo)
    if shutil.which("ffprobe"):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type,width,height:format=duration", "-of", "json", str(arquivo)],
                           capture_output=True, text=True, check=True)
        return json.loads(r.stdout)
    return _pelo_ffmpeg(arquivo)


def video(arquivo: Path | str) -> dict:
    """Primeira faixa de vídeo (width, height)."""
    for f in sondar(arquivo).get("streams", []):
        if f.get("codec_type") == "video":
            return f
    raise RuntimeError(f"{arquivo}: sem faixa de vídeo")


def duracao(arquivo: Path | str) -> float:
    return float(sondar(arquivo)["format"]["duration"])
