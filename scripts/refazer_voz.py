"""Refaz Reels já agendados com a voz do Gemini, sem cair na reserva (tarefa `refazer-voz:<id>,<id>`).
O vídeo é regravado no mesmo arquivo, então a fila publica a versão nova no horário marcado."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pipeline.marca import carregar_marca  # noqa: E402
from pipeline.modelos import Pauta  # noqa: E402
from pipeline.producao import produzir  # noqa: E402

ids = [x.strip() for x in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if x.strip()]
falhas = 0
for vid in ids:
    achado = None
    for arq in sorted((RAIZ / "pautas").glob("*.json")):
        pauta = Pauta.carregar(arq)
        for v in pauta.videos:
            if v.id == vid:
                achado = (pauta, v)
    if not achado:
        print(f"{vid}: não achei em pautas/")
        falhas += 1
        continue
    pauta, v = achado
    marca = carregar_marca(pauta.marca)
    for tentativa in range(1, 4):
        try:
            r = produzir(marca, v, previa=True, voz="gemini")
        except Exception as e:  # noqa: BLE001
            print(f"{vid}: tentativa {tentativa} falhou: {str(e)[:300]}")
            continue
        if r.arquivo:
            print(f"{vid}: refeito com a voz do Gemini ({r.duracao_s} s) -> {r.arquivo}")
            break
        print(f"{vid}: não gerou: {r.pulado}")
    else:
        falhas += 1
sys.exit(1 if falhas else 0)
