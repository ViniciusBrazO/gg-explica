"""Diagnóstico da voz do Gemini (tarefa `diag-voz`): gera o áudio de um roteiro real, roda o whisper e
mostra o que ele ouviu. O áudio vai para o ramo amostras-voz. Não publica nada."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pipeline import voz as v  # noqa: E402
from pipeline.marca import carregar_marca  # noqa: E402

pauta = json.loads((RAIZ / "pautas" / "radar_2026-11-17_gg_explica.json").read_text(encoding="utf-8"))
cenas = pauta["videos"][0]["cenas"]
texto = " ".join(v.texto_para_fala(c["narracao"]) for c in cenas)
print("ROTEIRO:", texto)
saida = RAIZ / "saida" / "amostras_voz"
saida.mkdir(parents=True, exist_ok=True)
g = v.Gemini(carregar_marca("gg_explica").voz["gemini"])
wav = g._audio(texto, saida / "diag.wav")
with open(wav, "rb") as f:
    print("cabeçalho:", f.read(16))
print("duração:", v._duracao_audio(wav))
ouvidas = v._ouvir(wav, texto)
print("OUVIU:", " ".join(f"{p.texto}[{p.inicio:.1f}]" for p in ouvidas))
print("motivo:", v.fala_incompleta(texto, v._duracao_audio(wav), ouvidas) or "ok")
shutil.copy2(wav, saida / "diag_gemini.wav")
