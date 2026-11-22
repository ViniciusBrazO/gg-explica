"""Chama o Claude Code sem janela (`claude -p`) para as tarefas que pedem raciocínio:
escrever o RADAR de uma notícia, montar a pauta da semana, etiquetar clipes, refazer um vídeo.

Cada tarefa é um arquivo em prompts/. As ferramentas liberadas ficam em config/automacao.yaml:
ler e editar arquivos do kit, pesquisar na web e rodar só comandos do próprio kit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .marca import RAIZ
from .radar import config

TAREFAS = {
    "radar": "radar_do_dia.md",        # todo dia de manhã
    "pauta": "pauta_semanal.md",       # segunda de manhã
    "alerta": "alerta_radar.md",       # quando o radar acha notícia quente
    "catalogo": "catalogar_clipes.md",  # quando chegam gravações novas
    "ajustes": "ajustes.md",           # quando você pede ajuste pelo Telegram
    "traducao": "traducao.md",         # versão em espanhol das pautas novas
    "resumo": "resumo_do_dia.md",
    "gameplay": "gameplay.md",         # cortes novos da gravação do Vinicius: roteiro de cada Reel      # 23h30: o que saiu hoje e músicas em alta para trocar no app
}
PASTA_LOG = RAIZ / "saida" / "claude"


@dataclass
class Execucao:
    ok: bool
    resumo: str
    custo_usd: float | None = None


def montar_prompt(tarefa: str, contexto: str = "", hoje: datetime | None = None) -> str:
    hoje = hoje or datetime.now()
    texto = (RAIZ / "prompts" / TAREFAS[tarefa]).read_text(encoding="utf-8")
    texto = texto.replace("{data de hoje}", hoje.strftime("%d/%m/%Y (%A)")).replace("{hoje}", hoje.date().isoformat())
    if contexto:
        texto += f"\n\n## Contexto desta execução\n\n{contexto}\n"
    return texto


def montar_comando(prompt: str) -> list[str]:
    cfg = config()["claude"]
    cmd = [cfg.get("comando", "claude"), "-p", prompt, "--output-format", "json",
           "--allowedTools", cfg["ferramentas"], "--permission-mode", cfg.get("modo_permissao", "acceptEdits")]
    if cfg.get("sem_perguntas", True):
        cmd += ["--permission-prompts", "none"]
    return cmd


def usa_gemini() -> bool:
    """`redator: gemini` em config/automacao.yaml e a chave no ambiente: escreve sem gastar o Claude."""
    from .gemini import disponivel as tem_chave
    return config().get("redator", "claude") == "gemini" and tem_chave()


def disponivel() -> bool:
    if usa_gemini():
        return True
    return shutil.which(config()["claude"].get("comando", "claude")) is not None


def rodar(tarefa: str, contexto: str = "", executar=subprocess.run) -> Execucao:
    if tarefa not in TAREFAS:
        raise ValueError(f"tarefa desconhecida: {tarefa}. Opções: {', '.join(TAREFAS)}")
    if usa_gemini() and executar is subprocess.run:
        from .redator import rodar as rodar_gemini
        return rodar_gemini(tarefa, contexto)
    cfg = config()["claude"]
    if tarefa in ("radar", "alerta"):
        try:
            from .dossie import montar
            assuntos, lidas = montar()
            contexto = (contexto + "\n\n" if contexto else "") + (
                f"Dossiê: `saida/radar/dossie.md` tem o texto de {lidas} matéria(s) de {assuntos} assunto(s) "
                "ainda não postados. Leia antes de escrever.")
        except Exception as e:      # sem dossiê, o Claude pesquisa sozinho como antes
            print(f"(dossiê não montado: {e})")
    cmd = montar_comando(montar_prompt(tarefa, contexto))
    # O Claude chama `paginas validar`: o comando do kit precisa estar no PATH dele.
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    try:
        r = executar(cmd, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", env=env,
                     timeout=cfg.get("limite_minutos", 20) * 60)
    except FileNotFoundError:
        return Execucao(False, "não achei o comando `claude`: instale o Claude Code e faça login")
    except subprocess.TimeoutExpired:
        return Execucao(False, f"a tarefa {tarefa} passou de {cfg.get('limite_minutos', 20)} min e foi parada")
    PASTA_LOG.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    (PASTA_LOG / f"{carimbo}_{tarefa}.json").write_text(r.stdout or r.stderr or "", encoding="utf-8")
    try:
        dados = json.loads(r.stdout)
        resumo, custo = str(dados.get("result", "")), dados.get("total_cost_usd")
    except (json.JSONDecodeError, TypeError):
        resumo, custo = (r.stdout or r.stderr or "").strip()[-1500:], None
    if bateu_limite(resumo):
        return plano_b(tarefa, contexto, resumo)
    return Execucao(r.returncode == 0, resumo, custo)


LIMITE_DO_PLANO = ("hit your weekly limit", "hit your limit", "usage limit", "limit reached", "rate limit",
                   "out of extra usage")


def bateu_limite(texto: str) -> bool:
    t = (texto or "").lower()
    return any(x in t for x in LIMITE_DO_PLANO)


def plano_b(tarefa: str, contexto: str, motivo: str) -> Execucao:
    """O plano do Claude bateu o limite (semanal ou de 5 h): o Gemini escreve esta rodada para os Reels do
    dia não deixarem de sair. Avisa no Telegram uma vez."""
    print(f"Claude sem limite agora ({motivo.strip()[:120]}); o Gemini escreve esta rodada")
    try:
        from .telegram import Telegram
        tg = Telegram.do_ambiente()
        if tg:
            tg.texto("⚠️ O plano do Claude bateu o limite de uso. Os Reels desta rodada vão ser escritos pelo "
                     f"Gemini (gratuito) até o limite voltar.\n\n{motivo.strip()[:200]}")
    except Exception as e:  # noqa: BLE001
        print(f"  Telegram: {str(e)[:80]}")
    from .redator import rodar as rodar_gemini
    from .gemini import disponivel as tem_chave
    if not tem_chave():
        return Execucao(False, f"Claude sem limite e sem GEMINI_API_KEY: {motivo.strip()[:200]}")
    return rodar_gemini(tarefa, contexto)
