"""Comandos do dia a dia.

  paginas validar   pautas/2026-W46_gg_explica.json
  paginas aprovar   pautas/2026-W46_gg_explica.json
  paginas renderizar pautas/2026-W46_gg_explica.json [--video ID] [--voz silencio]
  paginas publicar  [--simular]          # roda a cada 15 min pelo agendador do sistema
  paginas fila                           # mostra o que está agendado
  paginas metricas                       # coleta métricas dos Reels publicados
  paginas catalogar [clipes]             # folhas de contato das suas gravações de jogo

Automação (o agendador do Windows roda estes sozinho, veja scripts/instalar_automacao.ps1):
  paginas ciclo                          # a cada 15 min: gravações, radar, Telegram, Instagram
  paginas claude radar|pauta|alerta|catalogo|ajustes|traducao   # tarefas do Claude Code sem janela
  paginas radar                          # só o radar de notícias
  paginas clipes                         # só organizar clipes/entrada e catalogar
  paginas telegram teste|enviar|ouvir    # aprovação pelo celular
  paginas oficial <url> [<url>...]       # baixa imagens oficiais escolhidas para clipes/oficial
  paginas biblioteca                     # baixa os pacotes oficiais da Rockstar (trailers e imagens)
  paginas youtube autorizar --marca ID   # liga o canal do YouTube (uma vez)
"""
from __future__ import annotations

import argparse
import json
import shutil
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import ValidationError

from .marca import RAIZ, carregar_marca
from .modelos import Pauta

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def _carregar_env() -> None:
    load_dotenv(RAIZ / ".env")


def cmd_validar(args) -> int:
    from .qualidade import checar_pauta

    pauta = Pauta.carregar(args.pauta)
    marca = carregar_marca(pauta.marca)
    erros = 0
    for v in pauta.videos:
        bloqueios, avisos = checar_pauta(marca, v)
        marcador = "OK " if not bloqueios else "XX "
        print(f"{marcador} {v.data} {v.horario.strftime('%H:%M')}  {v.id}  [{v.status}]")
        for b in bloqueios:
            print(f"      bloqueio: {b}")
        for a in avisos:
            print(f"      aviso:    {a}")
        erros += bool(bloqueios) and v.status == "aprovado"
    return 1 if erros else 0


def cmd_aprovar(args) -> int:
    from .qualidade import checar_pauta

    pauta = Pauta.carregar(args.pauta)
    marca = carregar_marca(pauta.marca)
    hoje = datetime.now().date()
    for v in pauta.videos:
        if v.status != "rascunho" or (args.desde_hoje and v.data < hoje):
            continue
        bloqueios, avisos = checar_pauta(marca, v)
        print(f"\n{v.data} {v.horario.strftime('%H:%M')}  {v.id}  ({marca.nome_serie(v.serie)})")
        print("  " + v.cenas[0].titulo.replace("*", ""))
        for a in avisos:
            print(f"  aviso: {a}")
        if bloqueios:
            print("  não dá para aprovar ainda: " + "; ".join(bloqueios))
            continue
        if args.todos or input("  aprovar? [s/N] ").strip().lower() == "s":
            v.status = "aprovado"
    pauta.salvar(args.pauta)
    print(f"\nPauta salva em {args.pauta}")
    return 0


def cmd_renderizar(args) -> int:
    from .producao import produzir

    pauta = Pauta.carregar(args.pauta)
    marca = carregar_marca(pauta.marca)
    feitos = 0
    hoje = datetime.now().date()
    for v in pauta.videos:
        if args.video and v.id != args.video:
            continue
        if args.desde_hoje and v.data < hoje:
            continue
        if v.status != "aprovado" and not args.previa:
            continue
        print(f"renderizando {v.id}...", flush=True)
        r = produzir(marca, v, previa=args.previa, voz=args.voz)
        if r.arquivo is None:
            print(f"  pulando {v.id}: {r.pulado}")
            continue
        if r.problemas:
            print("  atenção: " + "; ".join(r.problemas))
        if args.previa:
            print(f"  prévia pronta: {r.arquivo}")
            continue
        feitos += 1
        print(f"  pronto: {r.arquivo.name} ({r.duracao_s}s)")
    if not args.previa:
        pauta.salvar(args.pauta)
    print(f"{feitos} vídeo(s) na fila.")
    return 0


def ja_no_ar(item, recentes: list[dict]) -> str:
    """Link do post igual (mesma legenda e mesmo tipo) publicado nas últimas 36 horas, ou ""."""
    from datetime import timedelta
    def chave(t: str) -> str:
        return " ".join((t or "").split())[:160]
    tipo = "CAROUSEL_ALBUM" if item.tipo == "carrossel" else "REELS"
    limite = datetime.now(FUSO_BR) - timedelta(hours=36)
    for m in recentes:
        quando = datetime.fromisoformat(m.get("timestamp", "1970-01-01T00:00:00+0000").replace("+0000", "+00:00"))
        mesmo_tipo = (m.get("media_product_type") == "REELS") == (tipo == "REELS") and \
            ((m.get("media_type") == "CAROUSEL_ALBUM") == (tipo == "CAROUSEL_ALBUM"))
        if quando >= limite and mesmo_tipo and chave(m.get("caption")) == chave(item.legenda):
            return m.get("permalink", "") or "?"
    return ""


def avisar_publicado(item) -> None:
    """Aviso no Telegram com o link; a resposta vira orientação para os próximos posts."""
    try:
        from .fila import _titulo
        from .telegram import Telegram
        tg = Telegram.do_ambiente()
        if tg is None:
            return
        rede = {"instagram": "Instagram", "facebook": "Facebook", "youtube": "YouTube"}.get(item.plataforma, item.plataforma)
        tipo = "Carrossel" if item.tipo == "carrossel" else "Reel"
        tg.texto(f"✅ No ar ({tipo} no {rede}): {_titulo(item.legenda)}\n{item.permalink}\n\n"
                 "Quer mudar algo? Responda esta mensagem dizendo o quê: eu anoto e vale para os próximos posts.")
    except Exception as e:      # aviso nunca derruba a publicação
        print(f"  aviso no Telegram falhou: {e}")


CODIGOS_FALHA_VIDEO = ("ProcessingFailedError", "2207076", "2207027", "2207053", "2207052")


def falha_da_meta_no_video(erro: str) -> bool:
    """Erros do processamento de vídeo do lado da Meta (não são do arquivo): vale tentar mais tarde."""
    return any(c in (erro or "") for c in CODIGOS_FALHA_VIDEO)


def reels_manuais() -> bool:
    from .radar import config
    return config().get("publicacao", {}).get("instagram_reels", "api") == "manual"


def link_do_reel_no_facebook(item) -> str:
    """Link público do mesmo Reel já publicado na Página do Facebook (o arquivo fica no CDN da Meta)."""
    from .fila import carregar
    from .meta import hospedeiro_da_marca, versao, GRAPH
    fb = next((i for i in carregar() if i.id == item.id and i.plataforma == "facebook"
               and i.status == "publicado" and i.media_id), None)
    if fb is None:
        return ""
    try:
        h = hospedeiro_da_marca(item.marca)
        r = h.s.get(f"{GRAPH}/{versao()}/{fb.media_id}", params={"fields": "source",
                                                                 "access_token": h.token_pagina}, timeout=30)
        return r.json().get("source", "")
    except Exception as e:
        print(f"  link do Reel do Facebook: {str(e)[:80]}")
        return ""


def entregar_reel_manual(item) -> bool:
    """Manda no Telegram o vídeo, a capa e a legenda prontos para postar o Reel pelo app.
    O vídeo vai primeiro (é o que costuma falhar: o Telegram às vezes dá Gateway Timeout); só depois do
    vídeo entregue vão a capa e a legenda, para não repetir mensagem a cada tentativa."""
    import html
    import time
    from .telegram import Telegram
    tg = Telegram.do_ambiente()
    if not tg:
        print("  sem Telegram: o Reel ficou só na fila")
        return False
    nome = item.id.split("_", 2)[-1]
    leve = Path(item.video).with_name(Path(item.video).stem + "_tg.mp4")
    if not leve.exists() and shutil.which("ffmpeg"):     # vídeo renderizado antes da cópia leve existir
        from .montagem import copia_para_telegram
        copia_para_telegram(Path(item.video))
    chamada = (f"🎬 Hora de postar o Reel \"{nome}\" no Instagram pelo app: salve o vídeo e a capa, cole a "
               "legenda e ligue o rótulo de IA (Configurações avançadas).")
    enviado = False
    url = link_do_reel_no_facebook(item)      # primeiro o link (o envio de arquivo ao Telegram anda falhando)
    if url:
        try:
            tg.video_por_link(url, chamada)
            enviado = True
            print("  vídeo entregue pelo link do Reel do Facebook")
        except Exception as e:
            print(f"  Telegram não baixou pelo link: {str(e)[:80]}")
    for tentativa, metodo in enumerate(() if enviado else ("video", "documento")):
        try:
            if metodo == "video":
                tg.video(Path(item.video), chamada, [])
            else:
                tg.documento(Path(item.video), chamada)
            enviado = True
            break
        except Exception as e:              # Gateway Timeout etc.: espera um pouco e tenta de outro jeito
            print(f"  Telegram não recebeu o vídeo ({metodo}): {str(e)[:80]}")
            time.sleep(15 * (tentativa + 1))
    if not enviado:
        return False
    for envio in (lambda: tg.foto(Path(item.capa), "Capa (Editar capa > Adicionar do rolo da câmera)")
                  if item.capa and Path(item.capa).exists() else None,
                  lambda: tg.texto(f"<code>{html.escape(item.legenda)}</code>", parse_mode="HTML")):
        try:
            envio()
        except Exception as e:
            print(f"  Telegram: {str(e)[:80]}")
    print("  Reel entregue no Telegram para postar pelo app")
    return True


def avisar_video_recusado(item, quando) -> None:
    from .telegram import Telegram
    tg = Telegram.do_ambiente()
    if tg:
        tg.texto(f"⚠️ O Instagram não está processando vídeos agora (erro da Meta). O Reel "
                 f"\"{item.id.split('_', 2)[-1]}\" vai ser tentado de novo às {quando:%H:%M}, sozinho. Se quiser "
                 f"que saia já, salve o vídeo da prévia aqui no Telegram e poste pelo app com a legenda da prévia.")


def publicar_reel_com_capa(pub, item) -> dict:
    """Usa a capa feita para o Reel (capa_reel.jpg) quando dá para hospedá-la; senão, um quadro do vídeo."""
    from .meta import ErroMeta, hospedeiro_da_marca, pode_hospedar
    capa = Path(item.capa) if item.capa else None
    if not (capa and capa.is_absolute() and capa.exists() and pode_hospedar(item.marca)):
        return pub.publicar_reel(Path(item.video), item.legenda)
    hosp = None
    try:
        hosp = hospedeiro_da_marca(item.marca)
        url = hosp.hospedar(capa)
    except (ErroMeta, OSError) as e:
        print(f"  capa do Reel não subiu ({e}); usando um quadro do vídeo")
        url = ""
    try:
        try:
            return pub.publicar_reel(Path(item.video), item.legenda, capa_url=url)
        except Exception as e:
            if not url or "ProcessingFailedError" in str(e):
                raise
            print(f"  o Instagram recusou com a capa ({str(e)[:120]}); tentando sem ela")
            return pub.publicar_reel(Path(item.video), item.legenda)
    finally:
        if hosp is not None:
            hosp.limpar()


def cmd_nuvem(args) -> int:
    from .nuvem import plano
    return plano()


def cmd_meta(args) -> int:
    from .meta import ErroMeta, conferir
    try:
        for linha in conferir(args.marca):
            print(linha)
    except (ErroMeta, OSError) as e:
        print(f"erro: {e}")
        return 1
    return 0


def cmd_publicar(args) -> int:
    from .fila import FUSO, carregar, salvar
    from .instagram import Credenciais, ErroInstagram, Publicador

    agora = datetime.now(FUSO)
    itens = carregar()
    publicados = 0
    no_ar: dict[str, list[dict]] = {}     # posts recentes de cada conta, contra publicação repetida
    from .ritmo import motivo_para_segurar
    # no mesmo horário, o Facebook antes: o Reel publicado lá dá o link para a entrega manual do Instagram
    for item in sorted(itens, key=lambda i: (i.quando, i.plataforma == "instagram")):
        if item.status != "pendente" or datetime.fromisoformat(item.quando) > agora:
            continue
        if item.tentativas >= (8 if falha_da_meta_no_video(item.erro) else 3):
            continue
        espera = motivo_para_segurar(item, itens, datetime.now(FUSO))
        if espera:
            print(f"  {item.plataforma} {item.id}: espera ({espera})")
            continue
        print(f"publicando {item.plataforma}: {item.marca}/{item.id} (agendado para {item.quando})")
        if args.simular:
            print("  simulação: nada foi enviado")
            continue
        if item.plataforma == "instagram" and item.tipo == "reel" and reels_manuais():
            # a API do Instagram está recusando vídeo: o Reel vai pronto para o Telegram e o Vinicius posta pelo app
            if entregar_reel_manual(item):
                item.status = "manual"
                item.publicado_em = datetime.now(FUSO).isoformat(timespec="seconds")
            else:
                item.tentativas += 1
                item.erro = "Telegram não recebeu o vídeo"
            continue
        try:
            if item.plataforma == "facebook":
                from .facebook import CredenciaisFacebook, PublicadorFacebook
                cred = CredenciaisFacebook.da_marca(item.marca)
                if cred is None:
                    raise ErroInstagram(f"faltam FB_PAGE_ID/FB_PAGE_TOKEN de {item.marca} no .env")
                res = PublicadorFacebook(cred).publicar_reel(Path(item.video), item.legenda)
            elif item.plataforma == "youtube":
                from .youtube import CredenciaisYouTube, PublicadorYouTube
                cred = CredenciaisYouTube.da_marca(item.marca)
                if cred is None:
                    raise ErroInstagram(f"faltam YT_CLIENT_ID/YT_CLIENT_SECRET/YT_REFRESH_TOKEN de {item.marca} no .env")
                tags = [t for t in re.findall(r"#\w+", item.legenda) if t.lower() != "#publi"]
                idioma = carregar_marca(item.marca).dados.get("idioma", "pt")
                res = PublicadorYouTube(cred).publicar_short(Path(item.video), item.legenda, idioma, tags)
            elif item.tipo == "carrossel":
                from .meta import hospedeiro_da_marca
                hosp = hospedeiro_da_marca(item.marca)
                if hosp is None:
                    raise ErroInstagram(f"faltam META_TOKEN/FB_PAGE_ID de {item.marca} no .env (carrossel)")
                slides = sorted(Path(item.video).glob("[0-9][0-9].jpg"))
                pub = Publicador(Credenciais.da_marca(item.marca))
                repetido = ja_no_ar(item, no_ar.setdefault(item.marca, pub.recentes()))
                if repetido:
                    hosp.limpar()
                    item.status, item.permalink = "publicado", repetido
                    print(f"  já estava no ar ({repetido}); não publiquei de novo")
                    continue
                res = pub.publicar_carrossel(slides, item.legenda, hosp)
            else:
                from .meta import hospedeiro_da_marca
                pub = Publicador(Credenciais.da_marca(item.marca), hospedeiro=hospedeiro_da_marca(item.marca))
                repetido = ja_no_ar(item, no_ar.setdefault(item.marca, pub.recentes()))
                if repetido:
                    item.status, item.permalink = "publicado", repetido
                    print(f"  já estava no ar ({repetido}); não publiquei de novo")
                    continue
                res = publicar_reel_com_capa(pub, item)
            item.status, item.media_id, item.permalink = "publicado", res["media_id"], res["permalink"]
            item.publicado_em = datetime.now(FUSO).isoformat(timespec="seconds")
            publicados += 1
            print(f"  no ar: {item.permalink}")
            avisar_publicado(item)
            if item.produtos_para_marcar:
                print(f"  marque no app: {', '.join(item.produtos_para_marcar)}")
        except (ErroInstagram, OSError, RuntimeError) as e:
            item.tentativas += 1
            item.erro = str(e)[:500]
            if item.plataforma == "instagram" and falha_da_meta_no_video(item.erro) and item.tentativas < 8:
                # o processamento de vídeo da Meta está instável: tenta de novo mais tarde, sem travar a fila
                novo = datetime.now(FUSO) + timedelta(minutes=60 * min(item.tentativas, 3))
                item.quando = novo.isoformat(timespec="seconds")
                print(f"  a Meta não processou o vídeo; nova tentativa às {novo:%H:%M} ({item.tentativas}/8)")
                if item.tentativas == 1:
                    avisar_video_recusado(item, novo)
                continue
            if item.tentativas >= 3:
                item.status = "erro"
            print(f"  erro: {item.erro}")
    salvar(itens)
    return 0


def cmd_fila(args) -> int:
    from .fila import carregar

    for i in carregar():
        print(f"{i.quando[:16]}  {i.status:9}  {i.marca:15}  {i.id}  {i.permalink or i.erro[:60]}")
    return 0


def cmd_metricas(args) -> int:
    from .metricas import ARQUIVO, coletar

    n = coletar()
    print(f"{n} linha(s) adicionadas em {ARQUIVO}")
    try:
        from .metricas import coletar_conta, escrever_resumo
        print(escrever_resumo(coletar_conta()))
    except Exception as e:
        print(f"resumo da conta: {e}")
    return 0


def publicados_hoje(hoje=None) -> list:
    from .fila import _titulo, carregar
    hoje = (hoje or datetime.now().date()).isoformat()
    vistos, lista = set(), []
    for i in sorted(carregar(), key=lambda x: x.quando):
        if i.status != "publicado" or i.plataforma != "instagram" or not i.quando.startswith(hoje):
            continue
        if i.id in vistos:
            continue
        vistos.add(i.id)
        lista.append({"tipo": "Carrossel" if i.tipo == "carrossel" else "Reel", "titulo": _titulo(i.legenda),
                      "link": i.permalink, "quando": i.quando[11:16]})
    return lista


def cmd_resumo(args) -> int:
    """23h30: o Claude monta o resumo do dia com músicas em alta e o kit manda no Telegram."""
    from . import claude_cli
    from .telegram import Telegram
    hoje = datetime.now().date()
    posts = publicados_hoje(hoje)
    contexto = "\n".join(f"- {p['quando']} {p['tipo']}: {p['titulo']} {p['link']}" for p in posts) or "(nenhum)"
    arq = RAIZ / "saida" / "telegram" / f"resumo_{hoje.isoformat()}.md"
    if posts and claude_cli.disponivel():
        ex = claude_cli.rodar("resumo", contexto=contexto)
        print(f"Claude: {'ok' if ex.ok else ex.resumo[:300]}")
    if arq.exists():
        texto = arq.read_text(encoding="utf-8")
    else:
        reels = sum(p["tipo"] == "Reel" for p in posts)
        texto = (f"📊 Resumo de {hoje:%d/%m}: {reels} Reels e {len(posts) - reels} carrosséis no ar\n\n"
                 + "\n".join(f"{n}) {p['titulo']} ({p['tipo']})\n{p['link']}" for n, p in enumerate(posts, 1)))
    tg = Telegram.do_ambiente()
    if tg is None:
        print(texto)
        return 0
    for k in range(0, len(texto), 3900):
        tg.texto(texto[k:k + 3900], disable_web_page_preview="true")
    print("resumo enviado no Telegram")
    return 0


def cmd_teste_voz(args) -> int:
    """Gera o Reel narrado de teste (pautas/demo_teste_voz.json) e manda no Telegram. Não publica.
    Com --vozes, manda um trecho curto com cada voz da Azure, para comparar."""
    import copy
    import dataclasses
    from .producao import produzir
    from .telegram import Telegram
    pauta = Pauta.carregar(RAIZ / "pautas" / "demo_teste_voz.json")
    marca = carregar_marca(pauta.marca)
    tg = Telegram.do_ambiente()
    if args.vozes:
        base = pauta.videos[0]
        for n, nome in enumerate(args.vozes.split(","), start=1):
            dados = copy.deepcopy(marca.dados)
            dados["voz"]["provedor"] = "azure"
            dados["voz"]["azure"].update({"voz": nome.strip(), "velocidade": args.velocidade, "tom": args.tom})
            m = dataclasses.replace(marca, dados=dados)
            v = base.model_copy(update={"id": f"teste_voz_{n}", "cenas": base.cenas[:3]})
            r = produzir(m, v, previa=True)
            if r.arquivo is None:
                print(f"{nome}: não gerou ({r.pulado})")
                continue
            curto = nome.replace("pt-BR-", "").replace("Neural", "")
            print(f"opção {n}: {curto} ({r.duracao_s}s)")
            if tg:
                tg.video(r.arquivo, f"🎙️ Opção {n}: {curto} (velocidade {args.velocidade}, tom {args.tom}). "
                         f"Responda com o número da que gostou.", [])
        return 0
    r = produzir(marca, pauta.videos[0], previa=True)
    if r.arquivo is None:
        print(f"não gerou: {r.pulado}")
        return 1
    print(f"gerado: {r.arquivo} ({r.duracao_s}s)")
    if tg:
        tg.video(r.arquivo, "🎙️ Teste do Reel narrado (não vai ao ar). Gostou da voz? Responda aqui "
                 "\"mais rápida\", \"mais lenta\", \"outra voz\" ou \"aprovada\".", [])
    return 0


def cmd_gemini(args) -> int:
    """Mostra os modelos que a chave do Gemini enxerga e testa cada um com um pedido mínimo."""
    import requests
    from .gemini import API, _chave, modelos_candidatos
    for nome in modelos_candidatos():
        r = requests.post(f"{API}/models/{nome}:generateContent", params={"key": _chave()}, timeout=60,
                          json={"contents": [{"parts": [{"text": "Responda só: ok"}]}]})
        print(f"{nome}: HTTP {r.status_code} {r.text[:120].replace(chr(10), ' ') if r.status_code != 200 else 'ok'}")
    return 0


def cmd_comentarios(args) -> int:
    from .comentarios import rodar
    rodar()
    return 0


def cmd_catalogar(args) -> int:
    from .catalogo import PASTA_CLIPES, catalogar

    pasta = Path(args.pasta) if args.pasta else PASTA_CLIPES
    if not pasta.exists():
        print(f"a pasta {pasta} não existe: crie e coloque as gravações nela")
        return 1
    novos = catalogar(pasta, args.intervalo)
    for n in novos:
        print(f"  {n['arquivo']}  ({n['duracao_s']}s)  folha: {n['folha']}")
    print(f"{len(novos)} clipe(s) novo(s) no catálogo {pasta / 'catalogo.json'}")
    if novos:
        print("Peça ao Claude: \"leia clipes/catalogo.json e as folhas em clipes/_folhas e preencha os campos vazios\".")
    return 0


def cmd_ciclo(args) -> int:
    from .ciclo import rodar

    return rodar(publicar=not args.sem_publicar)


def cmd_claude(args) -> int:
    from .claude_cli import rodar
    from .radar import config

    if args.tarefa == "traducao" and not config().get("traducao", {}).get("ativa", False):
        print("Página em espanhol desligada: mude traducao.ativa para true em config/automacao.yaml.")
        return 0
    ex = rodar(args.tarefa, contexto=args.contexto or "")
    print(ex.resumo)
    if ex.custo_usd is not None:
        print(f"(custo estimado: US$ {ex.custo_usd:.2f})")
    return 0 if ex.ok else 1


def cmd_radar(args) -> int:
    from .radar import resumo_alerta, rodar

    novas, quentes = rodar()
    for n in novas:
        print(f"[{n.selo_sugerido:10}] {n.titulo}  ({n.fonte})")
    for g in quentes:
        print("\nALERTA\n" + resumo_alerta(g))
    print(f"{len(novas)} nova(s), {len(quentes)} alerta(s)")
    return 0


def cmd_diagnostico_reel(args) -> int:
    """Envia variações de um Reel ao Instagram sem publicar, para achar o que ele recusa."""
    import subprocess
    from .instagram import Credenciais, Publicador
    from .montagem import parametros_instagram
    from .sonda import duracao
    orig = Path(args.arquivo)
    pasta = orig.parent / "_diag"
    pasta.mkdir(exist_ok=True)
    d = duracao(orig)
    variacoes = {
        "original": None,
        "primeiros_40s": ["-t", "40"],
        "30fps": ["-r", "30"],
        "sem_audio": ["-an"],
        "ultimos_40s": ["-ss", f"{max(d - 40, 0):.2f}"],
    }
    pub = Publicador(Credenciais.da_marca(args.marca))
    for nome, extra in variacoes.items():
        arq = orig if extra is None else pasta / f"{nome}.mp4"
        if extra is not None:
            params = parametros_instagram()
            if "-an" in extra:
                params = [p for k, p in enumerate(params) if p not in ("-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2")]
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *(extra if extra[0] == "-ss" else []),
                            "-i", str(orig), *(extra if extra[0] != "-ss" else []), *params, str(arq)], check=True)
        print(f"{nome:14s} {arq.stat().st_size / 1e6:5.1f} MB -> {pub.testar_envio(arq)}", flush=True)
    return 0


def cmd_nova_capa(args) -> int:
    """Troca a capa de um Reel por outra imagem oficial que não repete rosto/lugar de capa recente."""
    from .carrossel import capa_do_reel
    from .catalogo import buscar_clipe
    from .fila import carregar, salvar
    from .marca import carregar_marca
    from .modelos import Pauta
    from .telegram import Telegram
    from . import variedade
    video = next((v for arq in sorted((RAIZ / "pautas").glob("*.json"))
                  for v in _videos_da_pauta(arq) if v.id == args.video_id), None)
    if video is None:
        print(f"não achei {args.video_id} nas pautas")
        return 1
    marca = carregar_marca(video.marca if hasattr(video, "marca") else args.marca)
    evitar = variedade.imagens_de_outros(video) | variedade.assuntos_de_capas(video) | set(
        variedade._carregar().get(variedade.chave(video), {}).get("imagens", [])[:1])
    escolha = buscar_clipe(args.busca, evitar=evitar, semente=video.id + "|capa2")
    if escolha is None:
        print("nenhuma imagem livre para essa busca")
        return 1
    estilo = variedade.estilo_capa(video)
    itens = carregar()
    alvo = next((i for i in itens if i.id == args.video_id and i.capa), None)
    destino = Path(alvo.capa).with_name(Path(alvo.capa).stem + "_2.jpg") if alvo else \
        RAIZ / "saida" / f"{args.video_id}_capa_2.jpg"
    capa = capa_do_reel(marca, video, (str(escolha.caminho), escolha.inicio), destino, estilo)
    for i in itens:
        if i.id == args.video_id and i.status == "pendente":
            i.capa = str(capa.resolve())
    salvar(itens)
    print(f"capa nova: {escolha.entrada['arquivo']} -> {capa}")
    tg = Telegram.do_ambiente()
    if tg:
        tg.foto(capa, f"Capa nova do Reel {args.video_id.split('_', 2)[-1]} "
                      f"({Path(escolha.entrada['arquivo']).stem}). Ao postar pelo app: Editar capa > Adicionar do rolo da câmera.")
    return 0


def _videos_da_pauta(arq: Path):
    from .modelos import Pauta
    try:
        return Pauta.carregar(arq).videos
    except Exception:
        return []


def cmd_dossie(args) -> int:
    from .dossie import ARQUIVO, montar
    assuntos, lidas = montar()
    print(f"{assuntos} assunto(s), {lidas} matéria(s) com texto em {ARQUIVO}")
    for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
        if linha.startswith(("## ", "### ", "Link:")) or "só a manchete" in linha:
            print(linha[:160])
    return 0


def cmd_clipes(args) -> int:
    from .radar import config
    from .vigia import processar

    movidos, novos = processar(config()["clipes"])
    for m in movidos:
        print(f"  organizado: {m.relative_to(RAIZ)}")
    print(f"{len(movidos)} gravação(ões) organizada(s), {len(novos)} nova(s) no catálogo")
    return 0


def cmd_youtube(args) -> int:
    from .youtube import ErroYouTube, autorizar

    cid, segredo = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET")
    if not cid or not segredo:
        print("Preencha YT_CLIENT_ID e YT_CLIENT_SECRET no .env (Manual, passo do YouTube) e rode de novo.")
        return 1
    print(f"Entre com a conta Google dona do canal da marca {args.marca}.")
    try:
        token = autorizar(cid, segredo, porta=args.porta)
    except (ErroYouTube, OSError) as e:
        print(f"Não deu certo: {e}")
        return 1
    print(f"\nCole esta linha no .env (é segredo, não mande para ninguém):\n"
          f"YT_REFRESH_TOKEN_{args.marca.upper()}={token}")
    return 0


def cmd_biblioteca(args) -> int:
    from .biblioteca import atualizar

    novos = atualizar(so=args.so)
    print(f"{len(novos)} arquivo(s) novo(s) na biblioteca oficial (clipes/oficial). Catálogo atualizado.")
    if novos:
        print("Para etiquetar agora: paginas claude catalogo")
    return 0


def cmd_oficial(args) -> int:
    from .catalogo import baixar_oficial

    erros = 0
    for url in args.urls:
        try:
            print(f"  salvo: {baixar_oficial(url, credito=args.credito).relative_to(RAIZ)}")
        except Exception as e:
            erros += 1
            print(f"  não deu ({url}): {e}")
    return 1 if erros else 0


def cmd_telegram(args) -> int:
    from .radar import config
    from .telegram import Telegram, enviar_para_aprovacao, processar_respostas

    from .telegram import chat_salvo
    if args.acao == "teste" and not os.environ.get("TELEGRAM_CHAT_ID") and not chat_salvo():
        import requests
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            print("Falta TELEGRAM_BOT_TOKEN no .env (crie o bot com o @BotFather).")
            return 1
        r = requests.get(f"https://api.telegram.org/bot{token.strip()}/getUpdates", timeout=30).json()
        if not r.get("ok"):
            print(f"O Telegram recusou o token do bot: {r.get('description', '?')} (confira TELEGRAM_BOT_TOKEN)")
            return 1
        if r.get("result") == []:
            info = requests.get(f"https://api.telegram.org/bot{token.strip()}/getWebhookInfo", timeout=30).json()
            if (info.get("result") or {}).get("url"):
                print("O bot tem um webhook ligado, que engole as mensagens.")
        chats = {str(u["message"]["chat"]["id"]): u["message"]["chat"].get("first_name", "")
                 for u in r.get("result", []) if "message" in u}
        if not chats:
            eu = requests.get(f"https://api.telegram.org/bot{token.strip()}/getMe", timeout=30).json()
            nome = (eu.get("result") or {}).get("username", "?")
            print(f"Mande um 'oi' para o seu bot @{nome} no Telegram e rode de novo.")
            return 1
        privados = {str(u["message"]["chat"]["id"]) for u in r.get("result", [])
                    if "message" in u and u["message"]["chat"].get("type") == "private"}
        if len(privados) == 1:     # um só chat falou com o bot: é o dono; grava e já testa
            from .telegram import ARQ_CHAT, Telegram as Tg
            cid = privados.pop()
            ARQ_CHAT.parent.mkdir(parents=True, exist_ok=True)
            ARQ_CHAT.write_text(cid, encoding="utf-8")
            Tg(token.strip(), cid).texto("✅ GG Explica conectado. Daqui saem as prévias para aprovar.")
            print(f"chat do dono gravado ({chats.get(cid, '')}) e mensagem de teste enviada")
            return 0
        for cid, nome in chats.items():
            print(f"TELEGRAM_CHAT_ID={cid}   ({nome})  <- mais de um chat: copie o seu para o .env")
        return 0
    tg = Telegram.do_ambiente()
    if tg is None:
        print("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env.")
        return 1
    if args.acao == "teste":
        tg.texto("✅ GG Explica conectado. Daqui saem as prévias para aprovar.")
        print("mensagem enviada")
    elif args.acao == "enviar":
        n = enviar_para_aprovacao(tg, args.dias if args.dias is not None else
                                  config()["telegram"].get("enviar_dias_a_frente", 1))
        print(f"{n} prévia(s) enviada(s)")
    else:
        for f in processar_respostas(tg):
            print(f)
    return 0


def main(argv: list[str] | None = None) -> int:
    _carregar_env()
    ap = argparse.ArgumentParser(prog="paginas", description="Pipeline das páginas de nicho")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validar", help="confere a pauta sem renderizar")
    p.add_argument("pauta")
    p.set_defaults(func=cmd_validar)

    p = sub.add_parser("aprovar", help="aprova os rascunhos sem pendência")
    p.add_argument("pauta")
    p.add_argument("--todos", action="store_true", help="aprova todos que não tiverem bloqueio")
    p.add_argument("--desde-hoje", action="store_true", help="ignora posts de dias que já passaram")
    p.set_defaults(func=cmd_aprovar)

    p = sub.add_parser("renderizar", help="gera os vídeos aprovados e coloca na fila")
    p.add_argument("pauta")
    p.add_argument("--video", help="só este id")
    p.add_argument("--voz", choices=["gemini", "elevenlabs", "azure", "silencio"], help="troca o provedor de voz")
    p.add_argument("--previa", action="store_true", help="gera mesmo rascunho, sem colocar na fila")
    p.add_argument("--desde-hoje", action="store_true", help="ignora posts de dias que já passaram")
    p.set_defaults(func=cmd_renderizar)

    p = sub.add_parser("publicar", help="publica (Instagram, Facebook, YouTube) o que já passou do horário")
    p.add_argument("--simular", action="store_true")
    p.set_defaults(func=cmd_publicar)

    p = sub.add_parser("fila", help="mostra a fila de publicação")
    p.set_defaults(func=cmd_fila)

    p = sub.add_parser("teste-voz", help="gera o Reel narrado de teste e manda no Telegram")
    p.add_argument("--vozes", default="", help="vozes da Azure separadas por vírgula, para comparar")
    p.add_argument("--velocidade", default="+12%")
    p.add_argument("--tom", default="+3%")
    p.set_defaults(func=cmd_teste_voz)

    p = sub.add_parser("gemini", help="testa a chave e os modelos do Gemini")
    p.set_defaults(func=cmd_gemini)

    p = sub.add_parser("comentarios", help="sugestões de comentário nos posts bombando (vão no Telegram)")
    p.set_defaults(func=cmd_comentarios)

    p = sub.add_parser("resumo", help="resumo do dia no Telegram, com músicas em alta para cada post")
    p.set_defaults(func=cmd_resumo)

    p = sub.add_parser("metricas", help="coleta métricas dos Reels publicados")
    p.set_defaults(func=cmd_metricas)

    p = sub.add_parser("catalogar", help="folhas de contato e catálogo das gravações em clipes/")
    p.add_argument("pasta", nargs="?")
    p.add_argument("--intervalo", type=float, default=2.0, help="segundos entre quadros na folha")
    p.set_defaults(func=cmd_catalogar)

    p = sub.add_parser("ciclo", help="o ciclo automático (rode a cada 15 min)")
    p.add_argument("--sem-publicar", action="store_true")
    p.set_defaults(func=cmd_ciclo)

    p = sub.add_parser("claude", help="roda uma tarefa do Claude Code sem janela")
    p.add_argument("tarefa", choices=["radar", "pauta", "alerta", "catalogo", "ajustes", "traducao"])
    p.add_argument("--contexto", help="texto extra para a tarefa (ex.: a notícia do alerta)")
    p.set_defaults(func=cmd_claude)

    p = sub.add_parser("radar", help="busca notícias novas agora")
    p.set_defaults(func=cmd_radar)

    p = sub.add_parser("diagnostico-reel", help="testa variações de um Reel no Instagram sem publicar")
    p.add_argument("arquivo")
    p.add_argument("--marca", default="gg_explica")
    p.set_defaults(func=cmd_diagnostico_reel)

    p = sub.add_parser("nova-capa", help="troca a capa de um Reel por outra imagem oficial")
    p.add_argument("video_id")
    p.add_argument("--busca", default="vice city noite")
    p.add_argument("--marca", default="gg_explica")
    p.set_defaults(func=cmd_nova_capa)

    p = sub.add_parser("dossie", help="abre as matérias do radar para o redator (saida/radar/dossie.md)")
    p.set_defaults(func=cmd_dossie)

    p = sub.add_parser("clipes", help="organiza clipes/entrada e atualiza o catálogo")
    p.set_defaults(func=cmd_clipes)

    p = sub.add_parser("biblioteca", help="baixa trailers, screenshots e artes oficiais da Rockstar e cataloga")
    p.add_argument("--so", help="só o pacote com este nome (ex.: screenshots)")
    p.set_defaults(func=cmd_biblioteca)

    p = sub.add_parser("oficial", help="baixa imagens oficiais (links que você escolheu) para clipes/oficial")
    p.add_argument("urls", nargs="+")
    p.add_argument("--credito", default="Imagens: Rockstar Games")
    p.set_defaults(func=cmd_oficial)

    p = sub.add_parser("nuvem", help="modo GitHub Actions: decide se a rodada é leve ou pesada")
    p.add_argument("acao", choices=["plano"])
    p.set_defaults(func=cmd_nuvem)

    p = sub.add_parser("meta", help="confere o token da Meta (Instagram e Página) sem publicar")
    p.add_argument("acao", choices=["conferir"])
    p.add_argument("--marca", default="gg_explica")
    p.set_defaults(func=cmd_meta)

    p = sub.add_parser("youtube", help="liga um canal do YouTube (uma vez por canal)")
    p.add_argument("acao", choices=["autorizar"])
    p.add_argument("--marca", required=True, help="id da marca (ex.: gg_explica)")
    p.add_argument("--porta", type=int, default=8765)
    p.set_defaults(func=cmd_youtube)

    p = sub.add_parser("telegram", help="aprovação pelo celular")
    p.add_argument("acao", choices=["teste", "enviar", "ouvir"])
    p.add_argument("--dias", type=int, help="enviar: quantos dias à frente")
    p.set_defaults(func=cmd_telegram)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ValidationError as e:      # pauta fora do formato: mensagem curta em vez do traceback
        print("A pauta não está no formato certo:")
        for erro in e.errors():
            onde = " > ".join(str(x) for x in erro["loc"])
            print(f"  - {onde}: {erro['msg'].removeprefix('Value error, ')}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
