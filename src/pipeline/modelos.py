"""Formato das pautas: o arquivo JSON que o Claude escreve toda semana e o pipeline lê.

Uma pauta tem vários vídeos; cada vídeo tem cenas. Cada cena vira um cartão na tela,
um trecho de narração e um pedaço de legenda.
"""
from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TipoCena = Literal[
    "gancho",       # manchete de abertura
    "texto",        # uma afirmação curta
    "lista",        # itens numerados
    "produto",      # cartão de produto com preço
    "comparativo",  # duas colunas, linha a linha
    "veredito",     # selo aprova/reprova
    "contagem",     # número grande (dias, preço, porcentagem)
    "cta",          # chamada final
    "midia",        # clipe ou imagem horizontal no centro, com título em cima e crédito
    "tela_cheia",   # clipe ou imagem ocupando a tela toda, com barra de título compacta
]
TIPOS_COM_MIDIA = ("midia", "tela_cheia")

# Selo de confiança mostrado junto do fato (marcas que definem `selos` no YAML).
Selo = Literal["confirmado", "relato", "rumor", "teoria", "falso"]
SELOS_COM_FONTE = ("confirmado", "relato", "falso")

Status = Literal["rascunho", "aprovado", "renderizado", "publicado", "descartado"]


class Produto(BaseModel):
    nome: str
    loja: Literal["shopee", "mercado_livre", "amazon", "tiktok_shop", "outra"]
    link_afiliado: str = ""
    preco: Optional[float] = None
    preco_referencia: Optional[float] = None   # média ou preço anterior, com fonte
    fonte_preco: str = ""                        # de onde veio o preço e em que data
    imagem: str = ""                             # caminho local ou URL da foto do anúncio
    loja_oficial: bool = False


class Cena(BaseModel):
    tipo: TipoCena
    narracao: str = Field(default="", description="O que a voz fala nesta cena, escrito como se fala (vazio no carrossel).")
    estilo: Literal["cartao", "manchete", "tabela"] = "cartao"   # manchete: título grande sobre a imagem; tabela: lista de dados no carrossel
    # Campos visuais; cada tipo usa os que precisa.
    kicker: str = ""
    titulo: str = ""            # use *palavra* para destacar
    texto: str = ""
    itens: list[str] = []
    numero: str = ""
    rotulo: str = ""
    rodape: str = ""
    coluna_a: str = ""
    coluna_b: str = ""
    linhas: list[list[str]] = []   # [rótulo, valor A, valor B, vencedor "a"|"b"|""]
    aprovado: Optional[bool] = None
    produto: Optional[int] = None  # índice em Video.produtos
    broll: str = ""                # termo de busca de vídeo de fundo (opcional)
    # Selo de confiança e fonte do fato mostrado nesta cena.
    selo: Optional[Selo] = None
    fonte: str = ""                # "Rockstar Newswire · 15/10"; obrigatória em confirmado, relato e falso
    fonte_url: str = ""            # link da fonte, para conferir antes de aprovar (não aparece no vídeo)
    # Cenas "midia" e "tela_cheia": clipe (mp4, mov...) ou imagem (jpg, png).
    midia: str = ""                # clipes/2026-11-19_praia.mp4, ou "busca:praia pôr do sol" (catálogo)
    midia_inicio: float = 0.0      # segundo do clipe em que o trecho começa
    midia_fim: Optional[float] = None
    midia_recorte: list[float] = []   # zoom num detalhe: [x, y, largura, altura] em frações de 0 a 1
    midia_animacao: Literal["nenhuma", "aproximar"] = "nenhuma"   # aproximar: do quadro inteiro ao recorte
    midia_destaque: list[float] = []  # anel no detalhe: [x, y, raio] em frações do quadro inteiro
    foco_x: float = 0.5            # tela cheia e fundo: que parte da largura aparece (0 = esquerda, 1 = direita)
    panoramica: bool = False       # tela cheia: a câmera passeia da esquerda para a direita
    # Fundo em movimento atrás de qualquer cartão: um clipe (ou imagem) do jogo.
    fundo_clipe: str = ""          # caminho ou "busca:..."; o cartão fica por cima, com o véu da marca
    fundo_inicio: float = 0.0
    midia_terceiros: bool = True   # True = imagem do jogo, trailer ou de outra pessoa (pede crédito)
    credito: str = ""              # "Imagens: Rockstar Games"

    @model_validator(mode="after")
    def _campos_minimos(self) -> "Cena":
        precisa = {
            "gancho": ["titulo"],
            "texto": ["texto"],
            "lista": ["itens"],
            "produto": ["produto"],
            "comparativo": ["coluna_a", "coluna_b", "linhas"],
            "veredito": [] if self.selo else ["aprovado"],
            "contagem": ["numero", "rotulo"],
            "cta": ["texto"],
            "midia": ["midia"],
            "tela_cheia": ["midia"],
        }[self.tipo]
        faltando = [c for c in precisa if getattr(self, c) in (None, "", [])]
        if faltando:
            raise ValueError(f"cena '{self.tipo}' sem {', '.join(faltando)}")
        if self.midia_recorte:
            valido = len(self.midia_recorte) == 4
            if valido:
                x, y, w, h = self.midia_recorte
                valido = 0 <= x < 1 and 0 <= y < 1 and 0 < w and 0 < h and x + w <= 1.0001 and y + h <= 1.0001
            if not valido:
                raise ValueError("midia_recorte deve ser [x, y, largura, altura] em frações dentro da imagem")
        if self.midia_fim is not None and self.midia_fim <= self.midia_inicio:
            raise ValueError("midia_fim precisa ser maior que midia_inicio")
        if self.midia_animacao == "aproximar" and self.tipo != "midia":
            raise ValueError("midia_animacao 'aproximar' é só para a cena 'midia' (na caixa)")
        if self.midia_animacao == "aproximar" and not self.midia_recorte:
            raise ValueError("midia_animacao 'aproximar' precisa de midia_recorte (onde a câmera chega)")
        if self.midia_destaque and (len(self.midia_destaque) != 3
                                    or not all(0 <= v <= 1 for v in self.midia_destaque)):
            raise ValueError("midia_destaque deve ser [x, y, raio] em frações de 0 a 1")
        if not 0 <= self.foco_x <= 1:
            raise ValueError("foco_x vai de 0 (esquerda) a 1 (direita)")
        if self.fundo_clipe and self.tipo in TIPOS_COM_MIDIA:
            raise ValueError("cena de mídia já ocupa o fundo; use fundo_clipe só nos cartões")
        return self

    @property
    def usa_midia(self) -> bool:
        return self.tipo in TIPOS_COM_MIDIA or bool(self.fundo_clipe)

    @property
    def usa_midia_de_terceiros(self) -> bool:
        return self.usa_midia and self.midia_terceiros


class Video(BaseModel):
    id: str
    serie: str
    status: Status = "rascunho"
    data: date
    horario: time
    formato: Literal["reel", "carrossel"] = "reel"     # carrossel: cada cena vira um slide 4:5
    gerar_reel: bool = True     # carrossel: false quando o post tem um Reel narrado próprio (outro vídeo da pauta)
    plataformas: list[Literal["instagram", "tiktok", "facebook", "youtube", "kwai"]] = [
        "instagram", "tiktok", "facebook", "youtube", "kwai"]
    legenda_post: str
    hashtags: list[str] = []
    publi: bool = False
    voz_ia: bool = True
    produtos: list[Produto] = []
    cenas: list[Cena]
    notas_revisao: str = ""

    @field_validator("id")
    @classmethod
    def _id_simples(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("id deve ter só letras, números, - e _")
        return v

    @model_validator(mode="after")
    def _coerencia(self) -> "Video":
        for i, c in enumerate(self.cenas):
            if c.produto is not None and not (0 <= c.produto < len(self.produtos)):
                raise ValueError(f"cena {i} aponta para produto {c.produto}, que não existe")
        if self.publi and not self.produtos:
            raise ValueError("vídeo marcado como publi mas sem produto")
        if self.produtos and not self.publi:
            raise ValueError("vídeo com produto precisa ter publi=true")
        if self.cenas[0].tipo != "gancho":
            raise ValueError("a primeira cena precisa ser um gancho")
        if self.formato == "reel":
            sem_fala = [i for i, c in enumerate(self.cenas, start=1) if not c.narracao.strip()]
            if sem_fala:
                raise ValueError(f"no reel toda cena tem narração (faltando nas cenas {sem_fala})")
        elif not 2 <= len(self.cenas) <= 20:
            raise ValueError("carrossel tem de 2 a 20 slides")
        if self.publi and any(c.usa_midia_de_terceiros for c in self.cenas):
            raise ValueError("trecho de jogo ou imagem de terceiros não entra em vídeo com link (publi)")
        return self

    @property
    def usa_midia_de_terceiros(self) -> bool:
        return any(c.usa_midia_de_terceiros for c in self.cenas)

    def creditos(self) -> list[str]:
        """Créditos das imagens de terceiros, sem repetir, na ordem em que aparecem."""
        vistos: list[str] = []
        for c in self.cenas:
            if c.usa_midia_de_terceiros and c.credito and c.credito not in vistos:
                vistos.append(c.credito)
        return vistos

    def pendencias(self) -> list[str]:
        """O que ainda impede este vídeo de ir ao ar."""
        p = []
        for i, prod in enumerate(self.produtos):
            if not prod.link_afiliado:
                p.append(f"produto {i} ({prod.nome}) sem link de afiliado")
            if prod.preco is None:
                p.append(f"produto {i} ({prod.nome}) sem preço do dia")
            if prod.preco is not None and not prod.fonte_preco:
                p.append(f"produto {i} ({prod.nome}) sem fonte do preço")
        return p


class Pauta(BaseModel):
    marca: str
    semana: str
    videos: list[Video]

    @classmethod
    def carregar(cls, caminho: str | Path) -> "Pauta":
        return cls.model_validate(json.loads(Path(caminho).read_text(encoding="utf-8")))

    def salvar(self, caminho: str | Path) -> None:
        Path(caminho).write_text(
            self.model_dump_json(indent=2, exclude_defaults=False), encoding="utf-8"
        )
