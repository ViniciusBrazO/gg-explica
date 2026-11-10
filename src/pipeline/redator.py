"""Redator gratuito: o Gemini escreve os posts no lugar do Claude (`redator: gemini` em
config/automacao.yaml), sem gastar o plano do Claude.

O código faz o trabalho de pesquisa e de controle; o Gemini só escreve:
- separa as notícias do radar que ainda não viraram post e abre o texto das matérias (artigos.py);
- calcula os horários livres, junta os posts recentes, o vocabulário do catálogo e as orientações;
- pede o JSON ao Gemini, valida cada post (modelo + regras do kit) e devolve os erros para ele
  corrigir (até 2 vezes); CONFIRMADO sem fonte oficial lida vira RELATO;
- grava os rascunhos na pauta do dia. O ciclo agenda e publica como sempre.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from .marca import RAIZ, carregar_marca
from .modelos import Pauta, Video
from .radar import config

HORARIOS = ["09:00", "11:00", "12:30", "15:00", "17:00", "19:00", "21:00"]
USADAS = RAIZ / "saida" / "radar" / "usadas.json"
MARCA = "gg_explica"


# ---------------------------------------------------------------- contexto

def _ler(caminho: Path, limite: int = 12000) -> str:
    return caminho.read_text(encoding="utf-8")[:limite] if caminho.exists() else ""


def voz_ligada() -> bool:
    from .qualidade import so_carrossel
    return not so_carrossel()


def vocabulario_catalogo(n: int = 70) -> list[str]:
    arq = RAIZ / "clipes" / "catalogo.json"
    if not arq.exists():
        return []
    c = Counter()
    for e in json.loads(arq.read_text(encoding="utf-8")):
        if "logo" in e.get("tags", []):
            continue
        for t in e.get("tags", []) + [x.lower() for x in e.get("personagens", [])] + [e.get("lugar", "").lower()]:
            if t:
                c[t] += 1
    return [t for t, _ in c.most_common(n)]


def pautas() -> list[Path]:
    return sorted(p for p in (RAIZ / "pautas").glob("*.json") if not p.name.startswith(("exemplo_", "demo_")))


def posts_recentes(hoje: date, dias: int = 3) -> list[dict]:
    lista = []
    for arq in pautas():
        try:
            pauta = Pauta.carregar(arq)
        except Exception:
            continue
        for v in pauta.videos:
            if v.status == "descartado" or abs((v.data - hoje).days) > dias:
                continue
            lista.append({"data": v.data.isoformat(), "horario": v.horario.strftime("%H:%M"), "id": v.id,
                          "formato": v.formato, "capa": v.cenas[0].titulo,
                          "legenda": v.legenda_post.split("\n")[0][:140]})
    return sorted(lista, key=lambda x: (x["data"], x["horario"]))


def horarios_livres(dia: date, agora: datetime, antecedencia_min: int = 90) -> list[str]:
    ocupados = {p["horario"] for p in posts_recentes(dia, 0) if p["data"] == dia.isoformat()}
    livres = []
    for h in HORARIOS:
        quando = datetime.combine(dia, datetime.strptime(h, "%H:%M").time())
        if h not in ocupados and quando >= agora + timedelta(minutes=antecedencia_min):
            livres.append(h)
    return livres


def ja_coberto(titulo: str, recentes: list[dict], limite: float = 0.34) -> str:
    """Id do post recente que trata do mesmo assunto (palavras em comum), ou ""."""
    from .radar import _palavras
    base = _palavras(titulo.replace("*", ""))
    for p in recentes:
        for texto in (p.get("capa") or "", p.get("legenda") or ""):
            outra = _palavras(texto.replace("*", ""))
            if base and outra and len(base & outra) / min(len(base), len(outra)) >= 0.6 \
                    and len(base & outra) / len(base | outra) >= limite:
                return p["id"]
    return ""


def _usadas() -> set[str]:
    return set(json.loads(USADAS.read_text(encoding="utf-8"))) if USADAS.exists() else set()


def marcar_usadas(ids: list[str]) -> None:
    USADAS.parent.mkdir(parents=True, exist_ok=True)
    USADAS.write_text(json.dumps(sorted(_usadas() | set(ids))), encoding="utf-8")


def noticias_pendentes(hoje: date, maximo: int = 6) -> list[dict]:
    """Assuntos das últimas 36 horas que ainda não viraram post, do mais forte para o mais fraco."""
    from .radar import _palavras
    cfg = config()["radar"]
    quentes = [p.lower() for p in cfg.get("alerta", {}).get("palavras_quentes", [])]
    itens = []
    for d in (hoje - timedelta(days=1), hoje):
        arq = RAIZ / "saida" / "radar" / f"{d.isoformat()}.jsonl"
        if arq.exists():
            itens += [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    usadas = _usadas()
    recentes = posts_recentes(hoje)
    grupos: list[list[dict]] = []
    for n in sorted(itens, key=lambda x: x["publicada"], reverse=True):
        if n["id"] in usadas or ja_coberto(n["titulo"], recentes):
            continue
        base = _palavras(n["titulo"])
        for g in grupos:
            outra = _palavras(g[0]["titulo"])
            if base and outra and len(base & outra) / len(base | outra) >= 0.35:
                g.append(n)
                break
        else:
            grupos.append([n])

    def forca(g):
        oficial = any(n["selo_sugerido"] == "confirmado" for n in g)
        serias = len({n["dominio"] for n in g if n["selo_sugerido"] in ("confirmado", "relato")})
        quente = any(p in n["titulo"].lower() for n in g for p in quentes)
        return (oficial, quente, serias, len(g))
    grupos.sort(key=forca, reverse=True)
    return [{"ids": [n["id"] for n in g], "manchetes": g[:5]} for g in grupos[:maximo]]


def com_textos(assuntos: list[dict], por_assunto: int = 2) -> list[dict]:
    from .artigos import ler
    saida = []
    for a in assuntos:
        fontes = []
        for n in sorted(a["manchetes"], key=lambda x: ("news.google.com" in x["link"], x["selo_sugerido"] != "confirmado")):
            if len(fontes) >= por_assunto:
                break
            art = ler(n["link"])
            fontes.append({"veiculo": n["fonte"] or n["dominio"], "dominio": n["dominio"],
                           "selo_sugerido": n["selo_sugerido"], "data": n["publicada"][:10],
                           "manchete": n["titulo"], "link": art["url"] if art["texto"] else n["link"],
                           "texto": art["texto"] or "(só a manchete: a matéria não abriu)"})
        saida.append({"ids": a["ids"], "fontes": fontes,
                      "outras_manchetes": [n["titulo"] for n in a["manchetes"][len(fontes):]]})
    return saida


def contexto_base(hoje: date) -> dict:
    marca = carregar_marca(MARCA)
    orient = _ler(RAIZ / "saida" / "telegram" / "orientacoes.md", 4000)
    return {
        "hoje": hoje.isoformat(), "agora": datetime.now().strftime("%H:%M"),
        "voz": "ligada" if voz_ligada() else "desligada",
        "guia_de_estilo": _ler(RAIZ / "docs" / "guia_de_estilo.md", 9000),
        "series": {k: v.get("nome", k) for k, v in marca.series.items()},
        "tags_do_catalogo": vocabulario_catalogo(),
        "posts_recentes": posts_recentes(hoje),
        "orientacoes_do_vinicius": orient or "(nenhuma ainda)",
    }


# ---------------------------------------------------------------- validação e gravação

def _dominio_oficial(url: str) -> bool:
    fontes = config()["radar"]["fontes"].get("confirmado", [])
    d = urlparse(url).netloc.lower().removeprefix("www.")
    return any(d == f or d.endswith("." + f) for f in fontes)


def normalizar(bruto: dict, hoje: date, lidos: set[str]) -> dict:
    v = dict(bruto)
    v["status"] = "rascunho"
    v.setdefault("serie", "radar")
    v.setdefault("data", hoje.isoformat())
    v["plataformas"] = v.get("plataformas") or ["instagram", "facebook"]
    v["id"] = re.sub(r"[^a-z0-9_]+", "_", str(v.get("id", "post")).lower()).strip("_")[:60] or "post"
    v["publi"] = False
    v["produtos"] = []
    v["voz_ia"] = v.get("formato") == "reel"
    if v.get("formato") == "carrossel":
        v["gerar_reel"] = bool(v.get("gerar_reel", not voz_ligada()))
    for c in v.get("cenas", []):
        if c.get("selo") == "confirmado" and not (_dominio_oficial(c.get("fonte_url", "")) and c.get("fonte_url") in lidos):
            c["selo"] = "relato"          # oficial só se a fonte oficial foi lida nesta rodada
        if (c.get("fundo_clipe") or c.get("midia")) and not c.get("credito"):
            c["credito"] = "Imagens: Rockstar Games"
        if c.get("tipo") in ("midia", "tela_cheia"):
            c.pop("fundo_clipe", None)
        for campo in ("fundo_clipe", "midia"):
            if c.get(campo) and not str(c[campo]).startswith("busca:"):
                c[campo] = "busca:" + re.sub(r"[_/.\-]+", " ", Path(str(c[campo])).stem).lower()
    return v


def problemas(v: dict) -> list[str]:
    from .qualidade import checar_pauta
    try:
        video = Video.model_validate(v)
    except Exception as e:
        return [f"formato inválido: {str(e)[:600]}"]
    bloqueios, _ = checar_pauta(carregar_marca(MARCA), video)
    recentes = [p for p in posts_recentes(video.data) if not p["id"].startswith(video.id.removesuffix("_reel"))]
    repetido = ja_coberto(video.cenas[0].titulo, recentes)
    if repetido and not _par_do_mesmo_assunto(video.id, repetido):
        bloqueios.append(f"assunto repetido: já saiu no post {repetido}; escolha outro assunto ou outro ângulo")
    return bloqueios


def _par_do_mesmo_assunto(a: str, b: str) -> bool:
    """Reel e carrossel do mesmo post (escritos juntos) não contam como repetição."""
    limpa = lambda x: re.sub(r"_(reel|carrossel|narrado)$", "", x)
    return limpa(a) == limpa(b)


def arquivo_do_dia(hoje: date) -> Path:
    return RAIZ / "pautas" / f"radar_{hoje.isoformat()}_{MARCA}.json"


def gravar(videos: list[dict], arq: Path, hoje: date) -> list[str]:
    if arq.exists():
        pauta = Pauta.carregar(arq)
    else:
        pauta = Pauta.model_validate({"marca": MARCA, "semana": f"{hoje.isocalendar().year}-W{hoje.isocalendar().week:02d}",
                                      "videos": []})
    existentes = {v.id for v in pauta.videos}
    feitos = []
    for v in videos:
        base, k = v["id"], 2
        while v["id"] in existentes:
            v["id"] = f"{base}_{k}"
            k += 1
        pauta.videos.append(Video.model_validate(v))
        existentes.add(v["id"])
        feitos.append(v["id"])
    pauta.salvar(arq)
    return feitos


def escrever(tarefa_txt: str, contexto: dict, hoje: date, lidos: set[str]) -> tuple[list[dict], list[str]]:
    """Pede ao Gemini, valida e devolve (posts bons, problemas que sobraram)."""
    from .gemini import gerar_json
    sistema = _ler(RAIZ / "prompts" / "gemini_sistema.md", 20000)
    modelo = (config().get("gemini") or {}).get("modelo", "auto")
    pedido = tarefa_txt + "\n\nDADOS (JSON):\n" + json.dumps(contexto, ensure_ascii=False)
    resposta = gerar_json(sistema, pedido, modelo)
    for rodada in range(3):
        videos = [normalizar(v, hoje, lidos) for v in resposta.get("videos", [])]
        erros = {v["id"]: problemas(v) for v in videos}
        ruins = {k: e for k, e in erros.items() if e}
        if not ruins or rodada == 2:
            bons = [v for v in videos if not erros[v["id"]]]
            return bons, [f"{k}: {'; '.join(e)}" for k, e in ruins.items()]
        correcao = ("Alguns posts não passaram no validador do kit. Corrija SÓ os problemas listados e "
                    "devolva o JSON completo de novo (todos os vídeos), no mesmo formato.\n\nPROBLEMAS:\n"
                    + json.dumps(ruins, ensure_ascii=False) + "\n\nSEU JSON ANTERIOR:\n"
                    + json.dumps({"videos": videos}, ensure_ascii=False))
        resposta = gerar_json(sistema, correcao + "\n\nDADOS (JSON):\n" + json.dumps(contexto, ensure_ascii=False), modelo)
    return [], ["sem resposta"]


# ---------------------------------------------------------------- tarefas

def _post_duplo(voz: bool) -> str:
    if voz:
        return ("Para CADA assunto escreva DOIS vídeos: (1) um Reel narrado (`formato: reel`, id terminando em "
                "`_reel`) no horário indicado e (2) um carrossel do mesmo assunto (`formato: carrossel`, "
                "`gerar_reel: false`) 2 horas depois, com outra manchete, outra capa e outras buscas de imagem.")
    return ("Para cada assunto escreva UM carrossel (`formato: carrossel`, `gerar_reel: true`): o kit faz o Reel "
            "dele sozinho.")


def tarefa_radar(contexto: str = "", agora: datetime | None = None) -> tuple[bool, str]:
    agora = agora or datetime.now()
    hoje = agora.date()
    livres = horarios_livres(hoje, agora)
    dia = hoje
    if not livres and agora.hour >= 17:
        dia = hoje + timedelta(days=1)
        livres = ["09:00", "11:00"]
    assuntos = noticias_pendentes(hoje)
    if not livres or not assuntos:
        return True, f"nada a escrever (horários livres: {livres or 'nenhum'}, assuntos novos: {len(assuntos)})"
    n = min(3, len(livres), len(assuntos))
    escolhidos = assuntos[:n]
    fontes = com_textos(escolhidos)
    lidos = {f["link"] for a in fontes for f in a["fontes"] if not f["texto"].startswith("(só")}
    ctx = contexto_base(hoje) | {"assuntos": fontes, "horarios_para_usar": livres[:n],
                                 "data_dos_posts": dia.isoformat()}
    pedido = (f"TAREFA: escreva os posts de notícia dos {n} assunto(s) de `assuntos`, um por horário de "
              f"`horarios_para_usar` (na ordem, o assunto mais forte primeiro), na data `data_dos_posts`. Se um "
              f"assunto já está em `posts_recentes`, troque o ângulo (atualização, o que muda) ou pule. "
              f"{_post_duplo(ctx['voz'] == 'ligada')} Use só o que está nos textos das fontes. Em cada vídeo, "
              f"`notas_revisao` diz quais links usou. Responda {{\"videos\": [...]}}.")
    bons, falhas = escrever(pedido, ctx, dia, lidos)
    marcar_usadas([i for a in escolhidos for i in a["ids"]])
    if not bons:
        return False, "o Gemini não entregou posts válidos: " + "; ".join(falhas)[:500]
    feitos = gravar(bons, arquivo_do_dia(dia), dia)
    return True, f"{len(feitos)} post(s): {', '.join(feitos)}" + (f" | descartados: {'; '.join(falhas)}" if falhas else "")


def tarefa_alerta(contexto: str = "", agora: datetime | None = None) -> tuple[bool, str]:
    agora = agora or datetime.now()
    hoje = agora.date()
    assuntos = noticias_pendentes(hoje, maximo=3)
    if not assuntos:
        return True, "notícia já coberta"
    fontes = com_textos(assuntos[:1], por_assunto=3)
    lidos = {f["link"] for a in fontes for f in a["fontes"] if not f["texto"].startswith("(só")}
    horario = (agora + timedelta(minutes=5)).strftime("%H:%M")
    ctx = contexto_base(hoje) | {"assunto": fontes[0], "alerta_do_radar": contexto, "horario_agora": horario}
    voz = ctx["voz"] == "ligada"
    pedido = ("TAREFA: NOTÍCIA QUENTE, sai agora (ignore os horários base). Se o assunto já está em "
              "`posts_recentes`, responda {\"videos\": []}. Senão, " +
              (f"escreva o Reel narrado (`formato: reel`) com `horario` = {horario} e o carrossel do mesmo "
               f"assunto (`gerar_reel: false`) 2 horas depois. " if voz else
               f"escreva um carrossel (`gerar_reel: true`) com `horario` = {horario}. ") +
              "Curto e direto: 4 a 6 cenas. Responda {\"videos\": [...]}.")
    bons, falhas = escrever(pedido, ctx, hoje, lidos)
    if bons:
        gravar(bons, arquivo_do_dia(hoje), hoje)
    marcar_usadas(assuntos[0]["ids"])
    return True, f"{len(bons)} post(s) da notícia quente" + (f" | {'; '.join(falhas)}" if falhas else "")


def tarefa_ajustes(contexto: str = "", agora: datetime | None = None) -> tuple[bool, str]:
    from .telegram import MARCADOR_AJUSTE
    hoje = (agora or datetime.now()).date()
    feitos = []
    for arq in pautas():
        pauta = Pauta.carregar(arq)
        mudou = False
        for i, v in enumerate(pauta.videos):
            if v.status != "rascunho" or MARCADOR_AJUSTE not in (v.notas_revisao or ""):
                continue
            ctx = contexto_base(hoje) | {"post": json.loads(v.model_dump_json())}
            pedido = ("TAREFA: o Vinicius pediu um ajuste neste post (veja `notas_revisao`, depois de "
                      f"'{MARCADOR_AJUSTE}'). Refaça o post atendendo o pedido, mantendo `id`, `data`, `horario` e "
                      "`formato`. Em `notas_revisao`, troque o pedido por 'Ajustado: <o que mudou>'. "
                      "Responda {\"videos\": [o post refeito]}.")
            bons, _ = escrever(pedido, ctx, v.data, set())
            if bons:
                novo = bons[0]
                novo.update({"id": v.id, "data": v.data.isoformat(), "horario": v.horario.strftime("%H:%M")})
                pauta.videos[i] = Video.model_validate(novo)
                mudou = True
                feitos.append(v.id)
        if mudou:
            pauta.salvar(arq)
    return True, f"ajustados: {', '.join(feitos) or 'nenhum'}"


def tarefa_pauta(contexto: str = "", agora: datetime | None = None) -> tuple[bool, str]:
    agora = agora or datetime.now()
    seg = agora.date() + timedelta(days=(7 - agora.weekday()) % 7 or 0)
    dias = [seg + timedelta(days=k) for k in range(7)]
    ctx = contexto_base(agora.date()) | {"dias": [d.isoformat() for d in dias],
                                         "manchetes_da_semana": [a["manchetes"][0]["titulo"] for a in noticias_pendentes(agora.date(), 10)]}
    voz = ctx["voz"] == "ligada"
    pedido = ("TAREFA: pauta da semana (conteúdo que não depende de notícia do dia): 2 posts por dia, às 12:30 "
              "(série `gta_no_brasil`: o ângulo brasileiro, horário de liberação em Brasília, preço em reais, "
              "feriado, espaço no console) e às 21:30 (série `gg_explica`: guia, curiosidade oficial, "
              "comparação, explicação). " + _post_duplo(voz).replace("2 horas depois", "2 horas depois (o "
              "carrossel das 21:30 sai às 23:30)") + " Só fatos que estão no guia de estilo, nas manchetes ou que "
              "são de conhecimento oficial certo (data 19/11/2026, PS5 e Xbox Series); na dúvida, não afirme. "
              "Responda {\"videos\": [...]}.")
    bons, falhas = escrever(pedido, ctx, seg, set())
    if not bons:
        return False, "pauta não saiu: " + "; ".join(falhas)[:400]
    arq = RAIZ / "pautas" / f"{seg.isocalendar().year}-W{seg.isocalendar().week:02d}_{MARCA}.json"
    feitos = gravar(bons, arq, seg)
    return True, f"pauta da semana: {len(feitos)} post(s)" + (f" | descartados: {len(falhas)}" if falhas else "")


def tarefa_resumo(contexto: str = "", agora: datetime | None = None) -> tuple[bool, str]:
    from .gemini import gerar_json
    hoje = (agora or datetime.now()).date()
    sistema = "Você escreve mensagens curtas de Telegram em português do Brasil. Responda só JSON."
    pedido = ("Monte o resumo do dia da página GG Explica. Para cada post publicado hoje (lista abaixo), indique "
              "o ESTILO de música que combina (ex.: batida trap forte, phonk acelerado, synthwave anos 80, "
              "suspense cinematográfico, lo-fi leve) e por quê em 5 palavras. Não cite nomes de músicas. "
              "Responda {\"texto\": \"...\"} com, no máximo, 3.500 caracteres, neste formato:\n"
              f"📊 Resumo de {hoje:%d/%m}: N Reels e M carrosséis no ar\n\n1) <título> (Reel)\n<link>\n🎵 <estilo>\n\n"
              "No fim: 'Como trocar: no post > ⋯ > Editar > toque no áudio > escolha uma música em alta "
              "desse estilo na aba Em alta > Concluir.'\n\nPOSTS:\n" + contexto)
    texto = gerar_json(sistema, pedido, (config().get("gemini") or {}).get("modelo", "auto")).get("texto", "")
    if texto:
        arq = RAIZ / "saida" / "telegram" / f"resumo_{hoje.isoformat()}.md"
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(texto, encoding="utf-8")
    return bool(texto), "resumo escrito" if texto else "resumo vazio"


TAREFAS = {"radar": tarefa_radar, "alerta": tarefa_alerta, "ajustes": tarefa_ajustes,
           "pauta": tarefa_pauta, "resumo": tarefa_resumo}


def rodar(tarefa: str, contexto: str = ""):
    from .claude_cli import Execucao
    if tarefa not in TAREFAS:
        return Execucao(True, f"tarefa {tarefa} não usa o redator gratuito (nada a fazer)", 0.0)
    try:
        ok, resumo = TAREFAS[tarefa](contexto)
    except Exception as e:
        return Execucao(False, f"redator Gemini falhou em {tarefa}: {e}", 0.0)
    return Execucao(ok, resumo, 0.0)
