"""O ciclo que roda sozinho a cada 15 minutos (`paginas ciclo`).

Ordem: gravações novas -> radar de notícias -> respostas do Telegram -> ajustes pedidos ->
prévias para aprovar -> publicação do Instagram. Cada etapa é independente: se uma falha,
as outras seguem e você recebe o erro no Telegram.
"""
from __future__ import annotations

import os
import time
import traceback
from argparse import Namespace
from datetime import datetime
from pathlib import Path

from .marca import RAIZ
from .radar import config

TRAVA = RAIZ / "saida" / "ciclo.trava"
ULTIMO_RADAR = RAIZ / "saida" / "radar" / "ultimo.txt"
ULTIMA_BIBLIOTECA = RAIZ / "saida" / "biblioteca_ultimo.txt"


def _log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}", flush=True)


def _travar() -> bool:
    if TRAVA.exists() and time.time() - TRAVA.stat().st_mtime < 30 * 60:
        return False
    TRAVA.parent.mkdir(parents=True, exist_ok=True)
    TRAVA.write_text(str(os.getpid()))
    return True


def _passou(arq: Path, segundos: float) -> bool:
    """A hora fica escrita dentro do arquivo: a data do arquivo muda a cada checkout (modo nuvem)."""
    from .nuvem import ler_marca_de_tempo
    ultima = ler_marca_de_tempo(arq)
    return ultima is None or (datetime.now() - ultima).total_seconds() >= segundos


def _radar_na_hora(intervalo_min: int) -> bool:
    return _passou(ULTIMO_RADAR, intervalo_min * 60)


def rodar(publicar: bool = True) -> int:
    if not _travar():
        _log("outro ciclo ainda está rodando; saindo")
        return 0
    from . import biblioteca, claude_cli, radar, telegram, vigia

    cfg = config()
    tg = telegram.Telegram.do_ambiente()
    erros = 0

    def etapa(nome, funcao):
        nonlocal erros
        try:
            funcao()
        except Exception as e:   # uma etapa não derruba as outras
            erros += 1
            _log(f"ERRO em {nome}: {e}")
            with (RAIZ / "saida" / "ciclo_erros.log").open("a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M}] {nome}\n{traceback.format_exc()}")
            if tg:
                try:
                    tg.texto(f"❌ Falha em {nome}: {str(e)[:500]}")
                except Exception:
                    pass

    def clipes():
        movidos, novos = vigia.processar(cfg["clipes"])
        if movidos:
            _log(f"{len(movidos)} gravação(ões) organizada(s); {len(novos)} no catálogo")
        if novos and cfg["clipes"].get("etiquetar_com_claude") and claude_cli.disponivel():
            ex = claude_cli.rodar("catalogo")
            _log(f"Claude etiquetou os clipes: {'ok' if ex.ok else ex.resumo[:200]}")

    def material_oficial():
        horas = cfg.get("biblioteca", {}).get("verificar_a_cada_horas", 24)
        oficial = biblioteca.PASTA_OFICIAL
        vazia = not oficial.exists() or not any(p.is_dir() for p in oficial.iterdir())
        if not _passou(ULTIMA_BIBLIOTECA, horas * 3600) and not vazia:
            return            # (na nuvem, se o cache da biblioteca sumiu, baixa de novo na hora)
        ULTIMA_BIBLIOTECA.parent.mkdir(parents=True, exist_ok=True)
        ULTIMA_BIBLIOTECA.write_text(datetime.now().isoformat())
        novos = biblioteca.atualizar(mostrar=_log)
        if not novos:
            return
        if tg:
            tg.texto(f"🆕 A Rockstar publicou {len(novos)} arquivo(s) novo(s) na página de mídia. "
                     "Material novo oficial costuma virar post na hora.")
        if claude_cli.disponivel():
            ex = claude_cli.rodar("catalogo")
            _log(f"Claude etiquetou o material oficial: {'ok' if ex.ok else ex.resumo[:200]}")
            ex = claude_cli.rodar("alerta", contexto=f"A Rockstar publicou {len(novos)} arquivo(s) novos na página "
                                  "oficial de mídia de GTA VI (veja clipes/oficial e o catálogo). Faça um RADAR "
                                  "mostrando o que há de novo, com as imagens novas.")
            _log(f"Claude escreveu o RADAR do material novo: {'ok' if ex.ok else ex.resumo[:200]}")

    def noticias():
        if not _radar_na_hora(cfg["radar"].get("intervalo_min", 30)):
            return
        novas, quentes = radar.rodar()
        ULTIMO_RADAR.parent.mkdir(parents=True, exist_ok=True)
        ULTIMO_RADAR.write_text(datetime.now().isoformat())
        _log(f"radar: {len(novas)} notícia(s) nova(s), {len(quentes)} alerta(s)")
        for grupo in quentes:
            resumo = radar.resumo_alerta(grupo)
            if tg:
                tg.texto("🔥 Notícia quente\n" + resumo)
            so_oficial = cfg["radar"].get("claude_so_com_fonte_oficial", False)
            if so_oficial and not any(n.selo_sugerido == "confirmado" for n in grupo):
                continue      # economia: o Claude só escreve na hora quando a fonte é oficial
            if cfg["radar"].get("acionar_claude_no_alerta"):
                if claude_cli.disponivel():
                    ex = claude_cli.rodar("alerta", contexto=resumo)
                    _log(f"Claude escreveu o RADAR: {'ok' if ex.ok else ex.resumo[:200]}")
                else:                      # rodada leve na nuvem: o Claude escreve na próxima
                    from .nuvem import guardar_alerta
                    guardar_alerta(resumo)

    def alertas_guardados():
        if not claude_cli.disponivel():
            return
        from .nuvem import tirar_alertas
        for resumo in tirar_alertas():
            ex = claude_cli.rodar("alerta", contexto=resumo)
            _log(f"Claude escreveu o RADAR guardado: {'ok' if ex.ok else ex.resumo[:200]}")

    def respostas():
        if tg:
            for f in telegram.processar_respostas(tg):
                _log(f"telegram: {f}")

    def ajustes():
        if telegram.ha_ajustes_pendentes() and claude_cli.disponivel():
            ex = claude_cli.rodar("ajustes")
            _log(f"Claude refez os vídeos pedidos: {'ok' if ex.ok else ex.resumo[:200]}")

    def previas():
        if os.environ.get("RODADA") == "leve":
            return            # sem navegador e ffmpeg nesta rodada: a próxima rodada pesada agenda
        if tg:
            n = telegram.enviar_para_aprovacao(tg, cfg["telegram"].get("enviar_dias_a_frente", 1))
            if n:
                _log(f"{n} prévia(s) enviada(s) para aprovação")

    def trechos_de_video():
        """Descreve (Gemini) uns 70 planos dos vídeos oficiais por rodada pesada, até acabar."""
        if os.environ.get("RODADA") == "leve":
            return
        from .catalogo import etiquetar_momentos
        from .gemini import disponivel
        if disponivel():
            etiquetar_momentos(mostrar=_log)

    def gameplay():
        """Gravação nova na pasta do Drive: o Gemini acha os momentos, o kit corta e o Claude escreve
        o roteiro de cada corte (só texto, gasta pouco). Rodada pesada só."""
        if os.environ.get("RODADA") == "leve":
            return
        from . import gameplay as gp
        if not gp.ligado():
            return
        gp.marcar_usados()
        try:
            gp.processar(mostrar=_log)
        except Exception as e:  # noqa: BLE001
            falhas = gp.registrar_falha(str(e))
            _log(f"gameplay: {str(e)[:200]} (falha {falhas})")
        if gp.precisa_roteiro():
            from .claude_cli import rodar
            gp.marcar_pedido_roteiro()
            r = rodar("gameplay")
            _log(f"gameplay: roteiros {'escritos' if r.ok else 'falharam'}: {r.resumo[-300:]}")

    def instagram():
        from .cli import cmd_publicar
        cmd_publicar(Namespace(simular=False))

    try:
        etapa("material salvo", clipes)
        etapa("biblioteca oficial", material_oficial)
        etapa("trechos de vídeo", trechos_de_video)
        etapa("gameplay", gameplay)
        etapa("radar", noticias)
        etapa("notícias guardadas", alertas_guardados)
        etapa("respostas do Telegram", respostas)
        etapa("ajustes", ajustes)
        etapa("prévias", previas)
        if publicar:
            etapa("publicação no Instagram", instagram)
    finally:
        TRAVA.unlink(missing_ok=True)
    return 1 if erros else 0
