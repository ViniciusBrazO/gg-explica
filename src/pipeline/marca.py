"""Carrega a identidade de cada página (config/marcas/*.yaml)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
PASTA_MARCAS = RAIZ / "config" / "marcas"
PASTA_FONTES = RAIZ / "assets" / "fontes"


@dataclass(frozen=True)
class Marca:
    dados: dict[str, Any]

    @property
    def id(self) -> str:
        return self.dados["id"]

    @property
    def nome(self) -> str:
        return self.dados["nome"]

    @property
    def cores(self) -> dict[str, str]:
        return self.dados["cores"]

    @property
    def fontes(self) -> dict[str, Any]:
        return self.dados["fontes"]

    @property
    def legenda(self) -> dict[str, Any]:
        return self.dados["legenda"]

    @property
    def voz(self) -> dict[str, Any]:
        return self.dados["voz"]

    @property
    def video(self) -> dict[str, Any]:
        return self.dados["video"]

    @property
    def post(self) -> dict[str, Any]:
        return self.dados["post"]

    @property
    def series(self) -> dict[str, Any]:
        return self.dados["series"]

    @property
    def pasta_assets(self) -> Path:
        return RAIZ / "assets" / "marcas" / self.id

    def nome_serie(self, serie: str) -> str:
        return self.series.get(serie, {}).get("nome", serie.upper())


@lru_cache(maxsize=None)
def carregar_marca(marca_id: str) -> Marca:
    caminho = PASTA_MARCAS / f"{marca_id}.yaml"
    if not caminho.exists():
        disponiveis = ", ".join(p.stem for p in PASTA_MARCAS.glob("*.yaml"))
        raise FileNotFoundError(f"marca '{marca_id}' não existe. Disponíveis: {disponiveis}")
    return Marca(yaml.safe_load(caminho.read_text(encoding="utf-8")))
