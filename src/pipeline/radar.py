"""Radar de notícias: lê o Google Notícias (RSS público) e avisa quando sai algo grande.

- Guarda cada notícia nova em saida/radar/AAAA-MM-DD.jsonl, com o selo sugerido pela fonte.
- "Alerta quente" = fonte oficial (Rockstar, Take-Two, PlayStation, Xbox...) ou o mesmo assunto em
  várias fontes sérias em poucas horas. Aí o kit avisa no Telegram e, se configurado, chama o
  Claude para escrever o vídeo RADAR do assunto.

Só lê feeds públicos e não raspa site nenhum; o Claude confere a fonte original antes de escrever.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse

import requests
import yaml

from .marca import RAIZ

PASTA_RADAR = RAIZ / "saida" / "radar"
CONFIG = RAIZ / "config" / "automacao.yaml"
IDIOMAS = {"pt": "hl=pt-BR&gl=BR&ceid=BR:pt-419", "en": "hl=en-US&gl=US&ceid=US:en"}


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


@dataclass
class Noticia:
    titulo: str
    link: str
    fonte: str
    dominio: str
    publicada: str           # ISO, UTC
    selo_sugerido: str = "rumor"
    consulta: str = ""
    id: str = field(default="")

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.sha1(_chave_titulo(self.titulo).encode()).hexdigest()[:16]


def _chave_titulo(titulo: str) -> str:
    sem_fonte = re.sub(r"\s+-\s+[^-]+$", "", titulo)       # o Google põe " - Nome do site" no fim
    return unicodedata.normalize("NFKD", sem_fonte.lower()).encode("ascii", "ignore").decode().strip()


# Palavras que aparecem em quase toda manchete do nicho e não dizem qual é o assunto.
_COMUNS = {"gta", "grand", "theft", "auto", "rockstar", "games", "game", "jogo", "jogos", "para", "com", "que",
           "the", "and", "for", "from", "with", "this", "that", "will", "has", "have", "are", "now", "new", "nova",
           "novo", "sobre", "mais", "após", "apos", "como", "your", "you", "sera", "pode", "diz", "says"}


def _palavras(titulo: str) -> set[str]:
    """Raízes das palavras que identificam o assunto ("preload"/"pre-load" e "moves"/"moved" batem)."""
    texto = _chave_titulo(titulo).replace("-", "")
    termos = set()
    for p in re.split(r"[^a-z0-9]+", texto):
        if p in _COMUNS or (len(p) < 3 and not (p.isdigit() and len(p) >= 2)):
            continue
        termos.add(p[:4])
    return termos


def url_feed(q: str, idioma: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(q + ' when:2d')}&{IDIOMAS[idioma]}"


def selo_por_dominio(dominio: str, fontes: dict) -> str:
    for selo in ("confirmado", "relato"):
        if any(dominio == d or dominio.endswith("." + d) for d in fontes.get(selo, [])):
            return selo
    return "rumor"


def ler_feed(xml_texto: str, fontes: dict, consulta: str = "") -> list[Noticia]:
    raiz = ET.fromstring(xml_texto)
    noticias = []
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        fonte_el = item.find("source")
        fonte = (fonte_el.text or "").strip() if fonte_el is not None else ""
        url_fonte = fonte_el.get("url", "") if fonte_el is not None else ""
        dominio = urlparse(url_fonte or link).netloc.lower().removeprefix("www.")
        try:
            data = parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(timezone.utc)
        except (TypeError, ValueError):
            data = datetime.now(timezone.utc)
        if titulo:
            noticias.append(Noticia(titulo, link, fonte, dominio, data.isoformat(),
                                    selo_por_dominio(dominio, fontes), consulta))
    return noticias


def alertas(noticias: list[Noticia], cfg_alerta: dict, agora: Optional[datetime] = None) -> list[list[Noticia]]:
    """Agrupa notícias parecidas e devolve os grupos que merecem alerta."""
    agora = agora or datetime.now(timezone.utc)
    janela = agora - timedelta(hours=cfg_alerta.get("janela_horas", 3))
    recentes = [n for n in noticias if datetime.fromisoformat(n.publicada) >= janela]
    grupos: list[list[Noticia]] = []
    for n in sorted(recentes, key=lambda x: x.publicada):
        for g in grupos:
            base = _palavras(g[0].titulo)
            outra = _palavras(n.titulo)
            if base and outra and len(base & outra) / len(base | outra) >= 0.4:
                g.append(n)
                break
        else:
            grupos.append([n])
    quentes = []
    for g in grupos:
        oficiais = any(n.selo_sugerido == "confirmado" for n in g)
        serias = {n.dominio for n in g if n.selo_sugerido in ("confirmado", "relato")}
        palavras = [p.lower() for p in cfg_alerta.get("palavras_quentes", [])]
        quente = serias and any(p in n.titulo.lower() for n in g for p in palavras)   # trailer, data, preço...
        if oficiais or quente or len(serias) >= cfg_alerta.get("fontes_diferentes", 3):
            quentes.append(g)
    return quentes


def _vistos() -> set[str]:
    arq = PASTA_RADAR / "vistos.json"
    return set(json.loads(arq.read_text(encoding="utf-8"))) if arq.exists() else set()


def _salvar_vistos(vistos: set[str]) -> None:
    PASTA_RADAR.mkdir(parents=True, exist_ok=True)
    (PASTA_RADAR / "vistos.json").write_text(json.dumps(sorted(vistos)[-5000:]), encoding="utf-8")


def rodar(sessao=None, agora: Optional[datetime] = None) -> tuple[list[Noticia], list[list[Noticia]]]:
    """Busca, guarda o que é novo e devolve (novas, grupos em alerta entre as novas)."""
    cfg = config()["radar"]
    sessao = sessao or requests.Session()
    todas: list[Noticia] = []
    for c in cfg["consultas"]:
        try:
            r = sessao.get(url_feed(c["q"], c.get("idioma", "pt")), timeout=20,
                           headers={"User-Agent": "paginas-nicho-radar/1.0"})
            if r.status_code != 200:
                continue
            todas += ler_feed(r.text, cfg["fontes"], c["q"])
        except (requests.RequestException, ET.ParseError):
            continue        # um feed fora do ar não derruba os outros
    vistos = _vistos()
    novas = [n for n in {n.id: n for n in todas}.values() if n.id not in vistos]
    if novas:
        PASTA_RADAR.mkdir(parents=True, exist_ok=True)
        dia = (agora or datetime.now()).date().isoformat()
        with open(PASTA_RADAR / f"{dia}.jsonl", "a", encoding="utf-8") as f:
            for n in novas:
                f.write(json.dumps(asdict(n), ensure_ascii=False) + "\n")
        _salvar_vistos(vistos | {n.id for n in novas})
    return novas, alertas(novas, cfg.get("alerta", {}), agora)


def resumo_alerta(grupo: list[Noticia]) -> str:
    selo = "CONFIRMADO" if any(n.selo_sugerido == "confirmado" for n in grupo) else "RELATO"
    fontes = ", ".join(sorted({n.fonte or n.dominio for n in grupo}))
    return f"[{selo}?] {grupo[0].titulo}\nFontes: {fontes}\n{grupo[0].link}"
