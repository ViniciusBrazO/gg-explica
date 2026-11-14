"""Sugestões de comentário no Telegram (o Vinicius comenta à mão; nada é postado pelo kit).

Duas vezes por dia: lê pela API oficial (Business Discovery) os posts recentes das páginas grandes de
games, escolhe os que estão bombando, pede ao redator um comentário útil para cada um e manda no
Telegram o link e o texto pronto para copiar. Só leitura: regra nº 1 do CLAUDE.md.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone

import requests

from .marca import RAIZ
from .radar import config

ENVIADOS = RAIZ / "saida" / "telegram" / "comentarios_enviados.json"
GRAPH = "https://graph.facebook.com"


def _enviados() -> set[str]:
    return set(json.loads(ENVIADOS.read_text(encoding="utf-8"))) if ENVIADOS.exists() else set()


def posts_das_paginas(horas: int = 8, por_pagina: int = 6, sessao=None) -> list[dict]:
    from .instagram import Credenciais
    cred = Credenciais.da_marca("gg_explica")
    s = sessao or requests.Session()
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    posts = []
    for pagina in config().get("comentarios", {}).get("paginas", []):
        campos = (f"business_discovery.username({pagina}){{media.limit({por_pagina})"
                  "{caption,permalink,timestamp,like_count,comments_count,media_product_type}}")
        r = s.get(f"{GRAPH}/{cred.versao}/{cred.ig_user_id}", params={"fields": campos, "access_token": cred.token},
                  timeout=30)
        if r.status_code != 200:
            print(f"  {pagina}: não deu para ler ({r.status_code})")
            continue
        for m in (r.json().get("business_discovery", {}).get("media", {}).get("data", [])):
            quando = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
            if quando < limite:
                continue
            horas_no_ar = max((datetime.now(timezone.utc) - quando).total_seconds() / 3600, 0.25)
            ritmo = (m.get("like_count", 0) + 3 * m.get("comments_count", 0)) / horas_no_ar
            posts.append({"pagina": pagina, "link": m["permalink"], "legenda": (m.get("caption") or "")[:600],
                          "curtidas": m.get("like_count", 0), "comentarios": m.get("comments_count", 0),
                          "horas": round(horas_no_ar, 1), "ritmo": ritmo})
    return sorted(posts, key=lambda p: p["ritmo"], reverse=True)


def fatos_da_pagina() -> list[str]:
    """O que a GG Explica já publicou com fonte: a única base de fatos que o comentário pode usar."""
    from .redator import posts_recentes
    from .modelos import Pauta
    fatos = []
    hoje = datetime.now().date()
    for arq in sorted((RAIZ / "pautas").glob("radar_*.json"))[-3:]:
        try:
            for v in Pauta.carregar(arq).videos:
                if v.status != "descartado" and abs((v.data - hoje).days) <= 3:
                    fatos.append(v.legenda_post[:400])
        except Exception:
            continue
    return fatos[:15]


def sugerir(posts: list[dict]) -> list[dict]:
    from .gemini import disponivel, gerar_json
    if not disponivel():
        raise RuntimeError("falta GEMINI_API_KEY")
    instrucoes = (
        "Você escreve comentários de Instagram para o perfil @gg.explica (games, GTA 6, português do Brasil), "
        "que vão ser postados à mão em posts de páginas grandes de games. Objetivo: o comentário ser o mais "
        "curtido do post e fazer gente abrir o perfil. O que mais funciona é HUMOR: a sacada rápida de "
        "brasileiro no zap, como 'Reclama não, que quando quis pegar o nosso ouro não pediu permissão' num "
        "post sobre Portugal reclamando da legenda em português do Brasil. Regras: 1 frase curta (no máximo "
        "2), gíria e ritmo de fala do Brasil, no máximo 1 emoji (pode ser nenhum); piada que só funciona "
        "naquele post (trocadilho, comparação com a vida real do brasileiro, preço em reais, boleto, "
        "salário, chefe, mãe, fila, ônibus, Copa, meme conhecido); zoeira leve, que todo mundo ri junto. "
        "Nunca: ofensa a pessoa, grupo, nacionalidade, religião, gênero ou aparência; política; palavrão; "
        "autopromoção, 'segue lá', link, @ de outra conta, hashtag, spoiler, boato tratado como fato. Fato só "
        "se estiver em FATOS. Cada comentário com uma piada diferente. Se não houver piada boa e segura, "
        "faça um comentário de fã esperto que puxe resposta. Se o post não tiver nada a ver com games, "
        "devolva comentario vazio. Responda {\"sugestoes\": [{\"link\": ..., \"comentario\": ...}]}.")
    dados = {"FATOS": fatos_da_pagina(),
             "POSTS": [{"link": p["link"], "pagina": p["pagina"], "legenda": p["legenda"]} for p in posts]}
    resposta = gerar_json(instrucoes, json.dumps(dados, ensure_ascii=False), temperatura=1.0)
    por_link = {s.get("link"): (s.get("comentario") or "").strip() for s in resposta.get("sugestoes", [])}
    return [p | {"comentario": por_link.get(p["link"], "")} for p in posts if por_link.get(p["link"])]


def rodar(maximo: int = 6) -> int:
    from .telegram import Telegram
    tg = Telegram.do_ambiente()
    enviados = _enviados()
    posts = [p for p in posts_das_paginas() if p["link"] not in enviados][:maximo]
    if not posts:      # manhã fraca: amplia para as últimas 24 h
        posts = [p for p in posts_das_paginas(horas=24) if p["link"] not in enviados][:maximo]
    if not posts:
        print("nenhum post novo bombando")
        return 0
    sugestoes = sugerir(posts)
    linhas = ["💬 <b>Comentários para postar agora</b> (do perfil @gg.explica, à mão; toque no texto para copiar)\n"]
    for n, s in enumerate(sugestoes, 1):
        linhas.append(f"{n}) <b>{html.escape(s['pagina'])}</b> · {s['curtidas']} curtidas em {s['horas']} h\n"
                      f"{s['link']}\n<code>{html.escape(s['comentario'])}</code>\n")
    linhas.append("Dica: responda dentro do comentário mais curtido do post, nos primeiros 30 min.")
    if tg:
        tg.texto("\n".join(linhas), parse_mode="HTML", disable_web_page_preview="true")
    else:
        print("\n".join(linhas))
    ENVIADOS.parent.mkdir(parents=True, exist_ok=True)
    ENVIADOS.write_text(json.dumps(sorted(enviados | {p["link"] for p in posts})[-500:]), encoding="utf-8")
    print(f"{len(sugestoes)} sugestão(ões) enviada(s)")
    return len(sugestoes)
