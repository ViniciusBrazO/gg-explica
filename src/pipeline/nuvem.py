"""Modo nuvem (GitHub Actions): o kit roda sem o computador ligado.

Cada rodada do workflow (.github/workflows/kit.yml) faz `paginas nuvem plano` antes de instalar o
pesado (ffmpeg, navegador, Claude Code, biblioteca oficial). Rodada leve: só radar, botões do Telegram
e publicação do que já está pronto. Rodada pesada: quando há o que renderizar ou pedir ao Claude.
Assim cabe nos 2.000 minutos grátis por mês do GitHub.

O estado (pautas, fila, Telegram, radar, métricas, catálogo) volta para o repositório a cada rodada;
os arquivos pesados (vídeos, slides, imagens oficiais) ficam no cache do Actions.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from .marca import RAIZ

ALERTAS_PENDENTES = RAIZ / "saida" / "radar" / "alertas_pendentes.json"


def guardar_alerta(resumo: str) -> None:
    """Notícia quente numa rodada leve (sem o Claude instalado): fica para a próxima rodada pesada."""
    lista = json.loads(ALERTAS_PENDENTES.read_text(encoding="utf-8")) if ALERTAS_PENDENTES.exists() else []
    lista.append({"resumo": resumo, "quando": datetime.now().isoformat(timespec="minutes")})
    ALERTAS_PENDENTES.parent.mkdir(parents=True, exist_ok=True)
    ALERTAS_PENDENTES.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")


def tirar_alertas() -> list[str]:
    if not ALERTAS_PENDENTES.exists():
        return []
    lista = json.loads(ALERTAS_PENDENTES.read_text(encoding="utf-8"))
    ALERTAS_PENDENTES.unlink()
    return [a["resumo"] for a in lista]


def ler_marca_de_tempo(arq: Path) -> datetime | None:
    """Hora gravada dentro do arquivo (a data do arquivo muda a cada checkout do git)."""
    try:
        return datetime.fromisoformat(arq.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def motivos_para_pesado(hoje: date | None = None, telegram=None, agora: datetime | None = None) -> list[str]:
    """O que pede a rodada pesada. Lista vazia = rodada leve."""
    from .modelos import Pauta
    from .radar import config
    from . import telegram as tgmod

    hoje = hoje or date.today()
    agora = agora or datetime.now()
    cfg = config()
    motivos: list[str] = []

    pendentes = tgmod._carregar(tgmod.ARQ_PENDENTES, {})
    limite = hoje + timedelta(days=cfg["telegram"].get("enviar_dias_a_frente", 1))
    for arq in tgmod.pautas_de_trabalho():
        for v in Pauta.carregar(arq).videos:
            if v.data < hoje:
                continue
            if v.status == "aprovado":
                motivos.append(f"renderizar {v.id}")
            elif v.status == "rascunho" and v.data <= limite:
                if tgmod.MARCADOR_AJUSTE in (v.notas_revisao or ""):
                    motivos.append(f"ajuste de {v.id}")
                elif telegram is not None:
                    info = pendentes.get(tgmod._token(arq, v.id), {})
                    if info.get("impressao") != tgmod._impressao(v):
                        motivos.append(f"prévia de {v.id}")
                    elif info.get("situacao") == "aguardando" and tgmod.modo_aprovacao() == "automatica":
                        motivos.append(f"agendar {v.id}")
                    elif info.get("situacao") == "bloqueado":     # reconfere de 3 em 3 horas
                        conferido = info.get("conferido")
                        if not conferido or agora - datetime.fromisoformat(conferido) >= timedelta(hours=3):
                            motivos.append(f"reconferir {v.id}")

    if telegram is not None:
        offset = int(tgmod.ARQ_OFFSET.read_text()) if tgmod.ARQ_OFFSET.exists() else 0
        try:
            if telegram.atualizacoes(offset):      # só olha: confirma no ciclo, com offset maior
                motivos.append("respostas no Telegram")
        except Exception as e:                     # Telegram fora do ar não trava a publicação
            print(f"aviso: Telegram não respondeu ({e})")

    if ALERTAS_PENDENTES.exists():
        motivos.append("notícia quente para o Claude")

    from .ciclo import ULTIMA_BIBLIOTECA
    horas = cfg.get("biblioteca", {}).get("verificar_a_cada_horas", 24)
    ultima = ler_marca_de_tempo(ULTIMA_BIBLIOTECA)
    if ultima is None or agora - ultima >= timedelta(hours=horas):
        motivos.append("conferir a biblioteca oficial")
    return motivos


def plano() -> int:
    from .telegram import Telegram
    motivos = motivos_para_pesado(telegram=Telegram.do_ambiente())
    pesado = bool(motivos)
    print("rodada pesada: " + "; ".join(motivos) if pesado else "rodada leve")
    saida = os.environ.get("GITHUB_OUTPUT")
    if saida:
        with open(saida, "a", encoding="utf-8") as f:
            f.write(f"pesado={'true' if pesado else 'false'}\n")
    return 0
