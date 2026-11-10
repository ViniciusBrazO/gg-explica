"""Desenha os cartões de cada cena (PNG 1080x1920 com fundo transparente).

Usa HTML + CSS (templates/) renderizado no Chromium do Playwright. Assim a tipografia
fica com qualidade de design, e mudar a identidade é só editar o CSS da marca.
"""
from __future__ import annotations

import html
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from playwright.sync_api import sync_playwright

from .marca import RAIZ, Marca
from .modelos import Cena, Produto

PASTA_TEMPLATES = RAIZ / "templates"
LARGURA, ALTURA = 1080, 1920
# Caixa onde o clipe da cena "midia" aparece (16:9). O ffmpeg desenha o clipe aqui e o
# cartão deixa este espaço livre; mude nos dois lugares só por esta constante.
CAIXA_MIDIA = {"x": 40, "y": 730, "l": 1000, "a": 562}


def _destaque(texto: str) -> Markup:
    """*palavra* vira <mark>palavra</mark>; o resto é escapado."""
    seguro = html.escape(texto or "")
    return Markup(re.sub(r"\*(.+?)\*", r"<mark>\1</mark>", seguro))


def _reais(valor: Optional[float]) -> str:
    if valor is None:
        return ""
    inteiro, centavos = f"{valor:,.2f}".split(".")
    inteiro = inteiro.replace(",", ".")
    return f"R$ {inteiro}" if centavos == "00" else f"R$ {inteiro},{centavos}"


def _ambiente() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(PASTA_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["destaque"] = _destaque
    env.filters["reais"] = _reais
    return env


def montar_html(marca: Marca, cena: Cena | dict, serie: str = "",
                produto: Produto | None = None, fundo_solido: bool = False,
                revelar: int | None = None, modo: str = "completo") -> str:
    """modo: 'completo' (prévia), 'moldura' (véu + topo, fixo no vídeo) ou 'cartao' (só o conteúdo)."""
    env = _ambiente()
    return env.get_template("cena.html").render(
        fontes=(RAIZ / "assets" / "fontes").as_uri(),
        estilo=(PASTA_TEMPLATES / "estilos" / f"{marca.id}.css").as_uri(),
        cores=marca.cores,
        marca_id=marca.id,
        marca_nome=marca.nome,
        arroba=marca.dados["arroba"],
        selo=marca.dados.get("selo", {"aprova": "APROVA", "reprova": "REPROVA"}),
        selos=marca.dados.get("selos", {}),
        estilo_carimbo=marca.dados.get("estilo_carimbo", "icone"),
        caixa=CAIXA_MIDIA,
        serie=serie,
        cena=cena,
        produto=produto,
        fundo_solido=fundo_solido,
        revelar=revelar,
        modo=modo,
        idioma=marca.dados.get("idioma", "pt"),
    )


class Desenhista:
    """Mantém um navegador aberto para desenhar vários cartões em sequência."""

    def __init__(self, pagina):
        self._pagina = pagina

    def desenhar(self, html_doc: str, saida: Path, transparente: bool = True) -> Path:
        saida.parent.mkdir(parents=True, exist_ok=True)
        tmp = saida.with_suffix(".html")
        tmp.write_text(html_doc, encoding="utf-8")
        self._pagina.goto(tmp.as_uri())
        self._pagina.evaluate("() => window.__ajustar && window.__ajustar()")
        self._pagina.screenshot(path=str(saida), omit_background=transparente, type="png")
        tmp.unlink(missing_ok=True)
        return saida


@contextmanager
def desenhista() -> Iterator[Desenhista]:
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=1)
        try:
            yield Desenhista(pagina)
        finally:
            navegador.close()


def desenhar_fundo(d: Desenhista, marca: Marca, saida: Path) -> Path:
    html_doc = montar_html(marca, {"tipo": "fundo"})
    return d.desenhar(html_doc, saida, transparente=False)
