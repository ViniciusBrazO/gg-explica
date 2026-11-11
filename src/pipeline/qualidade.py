"""Checagens automáticas antes de renderizar e depois de renderizar."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml

from .catalogo import resolver_midia
from .marca import RAIZ, Marca
from .modelos import SELOS_COM_FONTE, Video

REGRAS = yaml.safe_load((RAIZ / "config" / "regras.yaml").read_text(encoding="utf-8"))

# "confirmado", "confirmou"... que não venha logo depois de "não", "nunca" ou "sem".
_AFIRMA_CONFIRMACAO = re.compile(r"(?<!não )(?<!nao )(?<!nunca )(?<!sem )\bconfirm(ad[oa]s?|ou|aram|a)\b",
                                 flags=re.IGNORECASE)
LIMITE_PROGRAMA_CRIADORES_S = 60


def caminho_midia(midia: str) -> Path:
    """Caminho da mídia de uma cena: relativo à pasta do kit, ou absoluto."""
    p = Path(midia)
    return p if p.is_absolute() else RAIZ / p


def _textos(video: Video) -> list[str]:
    t = [video.legenda_post]
    for c in video.cenas:
        t += [c.narracao, c.titulo, c.texto, c.kicker, c.rotulo, c.rodape, *c.itens]
    return [x for x in t if x]


def voz_disponivel() -> bool:
    import os
    return bool(os.environ.get("AZURE_SPEECH_KEY") or os.environ.get("ELEVENLABS_API_KEY"))


def so_carrossel() -> bool:
    """Sem voz de IA, todo post sai como carrossel (que também vira Reel). `auto`: liga sozinho a
    narração assim que a chave da voz existir no ambiente."""
    from .radar import config
    valor = (config().get("conteudo") or {}).get("so_carrossel", False)
    if valor == "auto":
        return not voz_disponivel()
    return bool(valor)


def checar_pauta(marca: Marca, video: Video) -> tuple[list[str], list[str]]:
    """Devolve (bloqueios, avisos)."""
    bloqueios, avisos = list(video.pendencias()), []
    tudo = "\n".join(_textos(video))
    for padrao in REGRAS["frases_proibidas"]:
        if re.search(padrao, tudo, flags=re.IGNORECASE):
            bloqueios.append(f"frase proibida: /{padrao}/")
    for padrao in REGRAS["atencao"]:
        if re.search(padrao, tudo, flags=re.IGNORECASE):
            avisos.append(f"revise o uso de /{padrao}/")
    serie = marca.series.get(video.serie)
    if serie is None:
        bloqueios.append(f"série '{video.serie}' não existe em {marca.id}.yaml")
    elif not serie.get("leva_link", True) and video.publi:
        bloqueios.append(f"a série {serie['nome']} não leva link de produto")
    if "MODELO" in tudo:
        bloqueios.append("ainda há texto 'MODELO' no vídeo")
    if video.formato != "carrossel" and so_carrossel():
        bloqueios.append("sem voz configurada (conteudo.so_carrossel em config/automacao.yaml): "
                         "faça este post como carrossel")
    from .variedade import repetidas
    bloqueios += repetidas(video)
    b, a = _checar_selos_e_midia(marca, video)
    bloqueios += b
    avisos += a
    palavras = sum(len(c.narracao.split()) for c in video.cenas)
    estimativa = palavras / 2.6
    if estimativa > marca.video["duracao_max_s"]:
        avisos.append(f"narração longa: cerca de {estimativa:.0f}s (máximo {marca.video['duracao_max_s']}s)")
    if video.usa_midia_de_terceiros and estimativa > LIMITE_PROGRAMA_CRIADORES_S:
        avisos.append(f"vídeo com trecho de jogo passa de {LIMITE_PROGRAMA_CRIADORES_S}s (cerca de "
                      f"{estimativa:.0f}s): entra no programa de criadores do TikTok, e a Rockstar trata "
                      "ganho com gravação como uso comercial. Encurte ou troque o trecho por visual próprio")
    return bloqueios, avisos


def _checar_selos_e_midia(marca: Marca, video: Video) -> tuple[list[str], list[str]]:
    bloqueios, avisos = [], []
    selos = marca.dados.get("selos", {})
    for i, c in enumerate(video.cenas, start=1):
        if c.selo:
            if c.selo not in selos:
                bloqueios.append(f"cena {i}: a marca {marca.id} não tem o selo '{c.selo}'")
            if c.selo in SELOS_COM_FONTE and not c.fonte.strip():
                bloqueios.append(f"cena {i}: selo {c.selo.upper()} sem fonte (de onde veio e quando)")
            if c.selo == "confirmado" and not c.fonte_url.strip():
                avisos.append(f"cena {i}: CONFIRMADO sem fonte_url; ponha o link oficial para conferir antes de aprovar")
            if c.selo in ("rumor", "teoria"):
                fala = " ".join([c.narracao, c.titulo, c.texto, c.kicker, *c.itens])
                if _AFIRMA_CONFIRMACAO.search(fala):
                    bloqueios.append(f"cena {i}: marcada como {c.selo.upper()} mas diz que está confirmado")
        if not c.usa_midia:
            continue
        for campo, valor in (("midia", c.midia), ("fundo_clipe", c.fundo_clipe)):
            if not valor:
                continue
            escolha = resolver_midia(valor)
            if escolha is None:
                bloqueios.append(f"cena {i}: nenhum clipe do catálogo combina com '{valor}' "
                                 "(rode `paginas catalogar` e preencha as tags)")
            elif not escolha.caminho.exists():
                bloqueios.append(f"cena {i}: arquivo de mídia não encontrado: {valor}")
        if c.midia_terceiros and not c.credito.strip():
            bloqueios.append(f"cena {i}: imagem de terceiros sem crédito (ex.: 'Imagens: Rockstar Games')")
        if c.midia_terceiros and c.midia_fim is not None and c.midia_fim - c.midia_inicio > 8:
            avisos.append(f"cena {i}: trecho de {c.midia_fim - c.midia_inicio:.0f}s; prefira cortes de até 6s "
                          "com a sua análise por cima")
    return bloqueios, avisos


def checar_arquivo(marca: Marca, arquivo: Path) -> list[str]:
    """Confere resolução, duração e áudio do vídeo final."""
    from .sonda import sondar
    info = sondar(arquivo)
    problemas = []
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not video or (video["width"], video["height"]) != (1080, 1920):
        problemas.append("resolução diferente de 1080x1920")
    if not any(s["codec_type"] == "audio" for s in info["streams"]):
        problemas.append("sem faixa de áudio")
    dur = float(info["format"]["duration"])
    if not marca.video["duracao_min_s"] <= dur <= marca.video["duracao_max_s"]:
        problemas.append(f"duração de {dur:.1f}s fora do intervalo da marca")
    return problemas
