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
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from .marca import RAIZ, carregar_marca
from .modelos import Pauta


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
        return pub.publicar_reel(Path(item.video), item.legenda, capa_url=url)
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
    for item in itens:
        if item.status != "pendente" or datetime.fromisoformat(item.quando) > agora:
            continue
        if item.tentativas >= 3:
            continue
        print(f"publicando {item.plataforma}: {item.marca}/{item.id} (agendado para {item.quando})")
        if args.simular:
            print("  simulação: nada foi enviado")
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
                res = Publicador(Credenciais.da_marca(item.marca)).publicar_carrossel(slides, item.legenda, hosp)
            else:
                pub = Publicador(Credenciais.da_marca(item.marca))
                res = publicar_reel_com_capa(pub, item)
            item.status, item.media_id, item.permalink = "publicado", res["media_id"], res["permalink"]
            publicados += 1
            print(f"  no ar: {item.permalink}")
            if item.produtos_para_marcar:
                print(f"  marque no app: {', '.join(item.produtos_para_marcar)}")
        except (ErroInstagram, OSError, RuntimeError) as e:
            item.tentativas += 1
            item.erro = str(e)[:500]
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

    if args.acao == "teste" and not os.environ.get("TELEGRAM_CHAT_ID"):
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
            print("Mande um 'oi' para o seu bot no Telegram e rode de novo.")
            return 1
        for cid, nome in chats.items():
            print(f"TELEGRAM_CHAT_ID={cid}   ({nome})  <- copie para o .env")
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
    p.add_argument("--voz", choices=["elevenlabs", "azure", "silencio"], help="troca o provedor de voz")
    p.add_argument("--previa", action="store_true", help="gera mesmo rascunho, sem colocar na fila")
    p.add_argument("--desde-hoje", action="store_true", help="ignora posts de dias que já passaram")
    p.set_defaults(func=cmd_renderizar)

    p = sub.add_parser("publicar", help="publica (Instagram, Facebook, YouTube) o que já passou do horário")
    p.add_argument("--simular", action="store_true")
    p.set_defaults(func=cmd_publicar)

    p = sub.add_parser("fila", help="mostra a fila de publicação")
    p.set_defaults(func=cmd_fila)

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
