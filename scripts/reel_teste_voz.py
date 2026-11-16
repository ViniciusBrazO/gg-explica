"""Renderiza um Reel de teste com a voz da marca (tarefa `reel-voz`). Não publica nem entra na fila:
o vídeo vai para saida/amostras_voz/ e para o ramo amostras-voz."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pipeline.marca import carregar_marca  # noqa: E402
from pipeline.modelos import Pauta  # noqa: E402
from pipeline.producao import produzir  # noqa: E402

pauta = Pauta.carregar(RAIZ / "pautas" / "radar_2026-11-16_gg_explica.json")
marca = carregar_marca(pauta.marca)
base = next(v for v in pauta.videos if v.id == "radar_2026-11-16_plano_ate_quinta_reel")
video = base.model_copy(update={"id": "teste_voz_storyteller"})
r = produzir(marca, video, previa=True)
if r.arquivo is None:
    print(f"não gerou: {r.pulado}")
    raise SystemExit(1)
destino = RAIZ / "saida" / "amostras_voz"
destino.mkdir(parents=True, exist_ok=True)
shutil.copy2(r.arquivo, destino / "reel_teste_voz_storyteller.mp4")
print(f"gerado: {r.arquivo} ({r.duracao_s}s)")
