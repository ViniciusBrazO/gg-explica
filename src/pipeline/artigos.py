"""Lê o texto de uma matéria (só os parágrafos), para o redator escrever com base na fonte.

Só abre o link da própria notícia que o radar achou, uma vez, e guarda em cache (saida/artigos/).
"""
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import requests

from .marca import RAIZ

PASTA = RAIZ / "saida" / "artigos"
LIMITE = 7000


class _Paragrafos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes: list[str] = []
        self._em_p = 0
        self._pular = 0
        self.titulo = ""
        self._no_titulo = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "aside", "form"):
            self._pular += 1
        elif tag in ("p", "h1", "h2", "li") and not self._pular:
            self._em_p += 1
            self.partes.append("")
        elif tag == "title":
            self._no_titulo = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "aside", "form") and self._pular:
            self._pular -= 1
        elif tag in ("p", "h1", "h2", "li") and self._em_p:
            self._em_p -= 1
        elif tag == "title":
            self._no_titulo = False

    def handle_data(self, data):
        if self._no_titulo:
            self.titulo += data
        elif self._em_p and not self._pular and self.partes:
            self.partes[-1] += data


def texto_de_html(html: str) -> tuple[str, str]:
    p = _Paragrafos()
    p.feed(html)
    linhas = [re.sub(r"\s+", " ", x).strip() for x in p.partes]
    linhas = [x for x in linhas if len(x) > 40]          # tira menus, botões e legendas curtas
    return p.titulo.strip(), "\n".join(linhas)[:LIMITE]


def ler(url: str, sessao=None) -> dict:
    """{"url", "titulo", "texto"}; texto vazio se não abriu (o redator só usa o título, então)."""
    PASTA.mkdir(parents=True, exist_ok=True)
    cache = PASTA / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    dados = {"url": url, "titulo": "", "texto": ""}
    if "news.google.com" not in url:
        try:
            s = sessao or requests.Session()
            r = s.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (paginas-nicho-redator)",
                                                 "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
            if r.status_code == 200 and "html" in r.headers.get("Content-Type", ""):
                dados["url"] = r.url
                dados["titulo"], dados["texto"] = texto_de_html(r.text)
        except requests.RequestException:
            pass
    cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados
