"""Estilo de Reel "notícia em tela cheia" (o padrão das páginas que crescem, como a Gamerize):

- o vídeo inteiro é imagem do jogo cobrindo a tela, trocando de tomada a cada 2 a 3 segundos;
- a MANCHETE do post fica parada no meio-baixo da tela do primeiro ao último segundo, em letra grossa,
  branca com as palavras de destaque na cor da marca, e o selo (RUMOR, RELATO...) logo acima;
- a legenda da narração entra 2 ou 3 palavras por vez, logo acima da manchete;
- nada de cartão, moldura ou caixa: a imagem respira.

Ligado por `video.estilo_reel: noticia` no YAML da marca.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .marca import RAIZ, Marca

SEGUNDOS_POR_TOMADA = 2.6
TOPO_MANCHETE = 1060        # onde a manchete começa (px, numa tela de 1920)
LARGURA_UTIL = 960
LEGENDA_MARGEM_TOPO = 760   # a legenda falada fica logo acima da manchete


def ligado(marca: Marca) -> bool:
    return marca.video.get("estilo_reel", "cartoes") == "noticia"


def tomadas_por_cena(duracao: float) -> int:
    return max(1, math.ceil(duracao / SEGUNDOS_POR_TOMADA))


def _fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    arquivos = {"Anton": "Anton-Regular.ttf", "Barlow": "Barlow-Bold.ttf", "Poppins": "Poppins-ExtraBold.ttf"}
    return ImageFont.truetype(str(RAIZ / "assets" / "fontes" / arquivos.get(nome, "Anton-Regular.ttf")), tamanho)


def _palavras_marcadas(titulo: str) -> list[tuple[str, bool]]:
    """'GTA 6 *lança* na quinta' -> [('GTA', False), ('6', False), ('LANÇA', True), ...]"""
    saida = []
    for m in re.finditer(r"\*([^*]+)\*|([^*]+)", titulo):
        pedaco, marcado = (m.group(1), True) if m.group(1) else (m.group(2), False)
        for p in pedaco.split():
            saida.append((p.upper(), marcado))
    return saida


def _quebrar(palavras: list[tuple[str, bool]], fonte, largura: int) -> list[list[tuple[str, bool]]]:
    linhas, atual = [], []
    for p in palavras:
        teste = " ".join(w for w, _ in atual + [p])
        if atual and fonte.getlength(teste) > largura:
            linhas.append(atual)
            atual = [p]
        else:
            atual.append(p)
    if atual:
        linhas.append(atual)
    return linhas


def desenhar_manchete(marca: Marca, titulo: str, selo: str | None, fonte_txt: str, credito: str,
                      destino: Path) -> Path:
    """PNG 1080x1920 transparente com sombra suave atrás, selo, manchete, fonte e crédito."""
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    # escurece de leve o terço de baixo, para a letra ler bem em qualquer imagem
    sombra = Image.new("L", (1, 1920), 0)
    for y in range(1920):
        a = 0 if y < 620 else min(170, int((y - 620) / 700 * 170))
        sombra.putpixel((0, y), a)
    preto = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
    preto.putalpha(sombra.resize((1080, 1920)))
    im = Image.alpha_composite(im, preto)
    d = ImageDraw.Draw(im)

    palavras = _palavras_marcadas(titulo)
    tamanho = 118
    while True:
        f = _fonte(marca.fontes.get("titulo", "Anton"), tamanho)
        linhas = _quebrar(palavras, f, LARGURA_UTIL)
        if len(linhas) <= 4 or tamanho <= 70:
            break
        tamanho -= 6
    altura_linha = int(tamanho * 1.08)
    y = TOPO_MANCHETE

    if selo and selo in marca.dados.get("selos", {}):
        s = marca.dados["selos"][selo]
        fs = _fonte(marca.fontes.get("corpo", "Barlow"), 34)
        rotulo = s["rotulo"] + (" · NÃO CONFIRMADO" if selo in ("rumor", "teoria") else "")
        w = int(fs.getlength(rotulo)) + 36
        x0 = (1080 - w) // 2
        d.rounded_rectangle((x0, y - 66, x0 + w, y - 16), radius=8, fill=s["cor"])
        d.text((1080 // 2, y - 41), rotulo, font=fs, fill=s["texto"], anchor="mm")

    for linha in linhas:
        largura = f.getlength(" ".join(w for w, _ in linha))
        x = (1080 - largura) / 2
        for palavra, marcada in linha:
            cor = marca.cores["destaque"] if marcada else "#FFFFFF"
            d.text((x, y), palavra, font=f, fill=cor, stroke_width=7, stroke_fill="#000000")
            x += f.getlength(palavra + " ")
        y += altura_linha

    fp = _fonte(marca.fontes.get("corpo", "Barlow"), 30)
    if fonte_txt:
        d.text((540, y + 36), f"Fonte: {fonte_txt}", font=fp, fill="#E6E9EE", anchor="mt",
               stroke_width=3, stroke_fill="#000000")
    if credito:
        d.text((48, 1800), credito, font=_fonte(marca.fontes.get("corpo", "Barlow"), 26), fill="#C9CED6",
               stroke_width=2, stroke_fill="#000000")
    im.save(destino)
    return destino


def moldura_vazia(destino: Path) -> Path:
    if not destino.exists():
        Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)).save(destino)
    return destino


SEGUNDOS_CARTAO_SEGUIR = 3.0
TOPO_CARTAO_SEGUIR = 330        # acima da legenda falada, longe da manchete


def desenhar_seguir(marca: Marca, chamada: str, destino: Path) -> Path:
    """Cartão dos últimos 3 s (22/11: os Reels salvam e enviam, mas quase ninguém segue): o @ da página em
    destaque e, se houver, o motivo concreto para seguir ("Amanhã: parte 2, o mapa dos cofres")."""
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    destaque = marca.cores.get("destaque", "#C8FF2E")
    arroba = (marca.dados.get("arroba") or "@gg.explica").upper()
    titulo = f"SEGUE A {arroba}"
    f = _fonte("Anton", 74)
    w = d.textlength(titulo, font=f)
    while w > 940 and f.size > 40:
        f = _fonte("Anton", f.size - 4)
        w = d.textlength(titulo, font=f)
    x0, y0 = (1080 - w) / 2 - 36, TOPO_CARTAO_SEGUIR
    d.rounded_rectangle((x0 + 6, y0 + 8, x0 + w + 78, y0 + f.size + 46), radius=26, fill=(0, 0, 0, 150))
    d.rounded_rectangle((x0, y0, x0 + w + 72, y0 + f.size + 38), radius=26, fill=destaque)
    d.text(((1080 - w) / 2, y0 + 14), titulo, font=f, fill="#0B0D12")
    if chamada.strip():
        fb = _fonte("Barlow", 46)
        linhas, linha = [], ""
        for palavra in chamada.strip().split():
            teste = f"{linha} {palavra}".strip()
            if d.textlength(teste, font=fb) > 900 and linha:
                linhas.append(linha)
                linha = palavra
            else:
                linha = teste
        linhas.append(linha)
        y = y0 + f.size + 70
        for linha in linhas[:2]:
            lw = d.textlength(linha, font=fb)
            d.text(((1080 - lw) / 2, y), linha, font=fb, fill="#FFFFFF", stroke_width=5, stroke_fill="#000000")
            y += 60
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino
