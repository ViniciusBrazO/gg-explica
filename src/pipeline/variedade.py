"""Cada post único: imagens e capas que não se repetem entre posts próximos.

- `saida/escolhas.json` guarda, por post, as imagens que entraram e o estilo da capa.
- A busca no catálogo (`busca:...`) evita as imagens dos outros posts dos últimos 14 dias.
- Imagem por caminho direto já usada em outro post próximo bloqueia o post (`paginas validar`).
- O estilo da capa gira entre 4 modelos e nunca repete o dos 2 posts anteriores.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .marca import RAIZ
from .modelos import Pauta, Video

ARQ_ESCOLHAS = RAIZ / "saida" / "escolhas.json"
JANELA_DIAS = 14
ESTILOS_CAPA = ["base", "topo", "faixa", "impacto"]


def chave(video: Video) -> str:
    return f"{video.data.isoformat()}|{video.id}"


def _carregar() -> dict:
    if ARQ_ESCOLHAS.exists():
        return json.loads(ARQ_ESCOLHAS.read_text(encoding="utf-8"))
    return {}


def _salvar(dados: dict) -> None:
    ARQ_ESCOLHAS.parent.mkdir(parents=True, exist_ok=True)
    ARQ_ESCOLHAS.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _perto(dia: str | date, ref: date, dias: int = JANELA_DIAS) -> bool:
    d = date.fromisoformat(dia) if isinstance(dia, str) else dia
    return abs((d - ref).days) <= dias


def _caminhos_diretos(video: Video) -> list[str]:
    caminhos = []
    for c in video.cenas:
        for m in (c.midia, c.fundo_clipe):
            if m and not m.startswith("busca:"):
                caminhos.append(Path(m).as_posix())
    return caminhos


def _outros_posts(video: Video):
    """Os outros posts das pautas (menos os descartados) perto da data deste."""
    for arq in sorted((RAIZ / "pautas").glob("*.json")):
        if arq.name.startswith(("exemplo_", "demo_")):
            continue
        try:
            pauta = Pauta.carregar(arq)
        except Exception:
            continue
        for v in pauta.videos:
            if v.status == "descartado" or chave(v) == chave(video) or not _perto(v.data, video.data):
                continue
            yield v


def imagens_de_outros(video: Video) -> set[str]:
    usadas: set[str] = set()
    for k, info in _carregar().items():
        if k != chave(video) and _perto(info.get("data", "1970-01-01"), video.data):
            usadas.update(info.get("imagens", []))
    for v in _outros_posts(video):
        usadas.update(_caminhos_diretos(v))
    return usadas


def registrar(video: Video, imagens: list[str], estilo: str) -> None:
    dados = _carregar()
    hoje = date.today()
    dados = {k: v for k, v in dados.items() if _perto(v.get("data", "1970-01-01"), hoje, 60)}  # limpa os velhos
    dados[chave(video)] = {"data": video.data.isoformat(), "horario": video.horario.strftime("%H:%M"),
                           "imagens": imagens, "estilo_capa": estilo,
                           "registrado": datetime.now().isoformat(timespec="minutes")}
    _salvar(dados)


def estilo_capa(video: Video) -> str:
    """Gira os modelos de capa: nunca o mesmo dos 2 posts anteriores (pela data e hora)."""
    quando = datetime.combine(video.data, video.horario)
    anteriores = []
    for k, info in _carregar().items():
        if k == chave(video) or "estilo_capa" not in info:
            continue
        t = datetime.fromisoformat(f"{info['data']}T{info.get('horario', '00:00')}")
        if quando - timedelta(days=3) <= t < quando:
            anteriores.append((t, info["estilo_capa"]))
    recentes = {e for _, e in sorted(anteriores)[-2:]}
    inicio = int(hashlib.sha1(chave(video).encode()).hexdigest(), 16) % len(ESTILOS_CAPA)
    for i in range(len(ESTILOS_CAPA)):
        estilo = ESTILOS_CAPA[(inicio + i) % len(ESTILOS_CAPA)]
        if estilo not in recentes:
            return estilo
    return ESTILOS_CAPA[inicio]


def repetidas(video: Video) -> list[str]:
    """Bloqueios: imagem por caminho direto repetida no próprio post ou já usada em outro post próximo."""
    problemas = []
    diretos = _caminhos_diretos(video)
    for c in sorted({c for c in diretos if diretos.count(c) > 1}):
        problemas.append(f"a imagem {c} aparece mais de uma vez neste post (uma imagem diferente por slide)")
    usados_fora: dict[str, str] = {}
    for v in _outros_posts(video):
        for c in _caminhos_diretos(v):
            usados_fora.setdefault(c, v.id)
    for c in sorted(set(diretos)):
        if c in usados_fora:
            problemas.append(f"a imagem {c} já está no post {usados_fora[c]}: troque por \"busca:...\" "
                             "com outras palavras (cada post com imagens próprias)")
    return problemas
