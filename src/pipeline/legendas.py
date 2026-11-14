"""Legenda na tela no estilo karaokê: blocos de 2 a 3 palavras, a palavra falada acende.

Gera um arquivo .ass (Advanced SubStation Alpha), que o ffmpeg queima no vídeo com a
fonte da marca. Muita gente assiste sem som, por isso a legenda é parte do design.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .marca import Marca
from .voz import Palavra


@dataclass
class Bloco:
    palavras: list[Palavra]

    @property
    def inicio(self) -> float:
        return self.palavras[0].inicio

    @property
    def fim(self) -> float:
        return self.palavras[-1].fim


def _cor_ass(hex_cor: str, alfa: int = 0) -> str:
    """#RRGGBB -> &HAABBGGRR (formato de cor do ASS)."""
    h = hex_cor.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def _tempo(t: float) -> str:
    t = max(0.0, t)
    h, resto = divmod(t, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _limpar(texto: str) -> str:
    return texto.replace("{", "(").replace("}", ")").replace("\\", "/").replace("*", "")


def agrupar(palavras: list[Palavra], max_palavras: int = 3, max_caracteres: int = 18) -> list[Bloco]:
    """Agrupa palavras em blocos curtos, quebrando em pontuação e em pausas."""
    blocos: list[Bloco] = []
    atual: list[Palavra] = []
    for p in palavras:
        tamanho = sum(len(x.texto) + 1 for x in atual) + len(p.texto)
        pausa = atual and (p.inicio - atual[-1].fim) > 0.35
        if atual and (len(atual) >= max_palavras or tamanho > max_caracteres or pausa):
            blocos.append(Bloco(atual))
            atual = []
        atual.append(p)
        if p.texto[-1:] in ".,!?;:":
            blocos.append(Bloco(atual))
            atual = []
    if atual:
        blocos.append(Bloco(atual))
    return blocos


def gerar_ass(marca: Marca, palavras: list[Palavra], saida: Path, topo: int | None = None) -> Path:
    cfg = marca.legenda
    cores = marca.cores
    caixa_alta = marca.fontes.get("legenda_caixa_alta", False)
    fonte = marca.fontes["legenda"]
    caixa = cfg.get("caixa", False)

    texto_cor = _cor_ass(cores["texto"])
    destaque = _cor_ass(cores["destaque"])
    if caixa:
        # legenda dentro de uma faixa clara (BorderStyle 3 usa a cor de contorno como caixa)
        estilo = (f"Style: Base,{fonte},{cfg['tamanho']},{texto_cor},{texto_cor},"
                  f"{_cor_ass(cores['superficie'])},{_cor_ass('#000000', 255)},0,0,0,0,100,100,0,0,3,"
                  f"{cfg.get('contorno', 18)},0,2,80,140,470,1")
    else:
        estilo = (f"Style: Base,{fonte},{cfg['tamanho']},{texto_cor},{texto_cor},"
                  f"{_cor_ass(cores['fundo'])},{_cor_ass('#000000', 120)},0,0,0,0,100,100,0,0,1,"
                  f"{cfg.get('contorno', 6)},{cfg.get('sombra', 0)},2,80,140,470,1")

    if topo is not None:     # estilo notícia: legenda no alto do meio, acima da manchete parada
        estilo = estilo.replace(",2,80,140,470,1", f",8,80,80,{topo},1")
    cabecalho = "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        estilo,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])

    blocos = agrupar(palavras, cfg.get("max_palavras", 3), cfg.get("max_caracteres", 18))
    eventos = []
    for bi, bloco in enumerate(blocos):
        proximo = blocos[bi + 1].inicio if bi + 1 < len(blocos) else bloco.fim + 0.6
        fim_bloco = min(proximo, bloco.fim + 0.45)
        textos = [_limpar(p.texto.upper() if caixa_alta else p.texto) for p in bloco.palavras]
        for wi, p in enumerate(bloco.palavras):
            ini = p.inicio if wi else bloco.inicio
            fim = bloco.palavras[wi + 1].inicio if wi + 1 < len(bloco.palavras) else fim_bloco
            partes = []
            for wj, t in enumerate(textos):
                if wj == wi:
                    partes.append(f"{{\\c{destaque}\\fscx106\\fscy106}}{t}{{\\r}}")
                else:
                    partes.append(t)
            entrada = "{\\fscx90\\fscy90\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
            eventos.append(f"Dialogue: 0,{_tempo(ini)},{_tempo(fim)},Base,,0,0,0,,{entrada}{' '.join(partes)}")

    saida.write_text(cabecalho + "\n" + "\n".join(eventos) + "\n", encoding="utf-8")
    return saida
