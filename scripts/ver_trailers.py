"""Diagnóstico: abre as páginas de vídeo oficiais da Rockstar e lista título + endereço de mídia que o
player oficial carrega (só leitura; não baixa nada)."""
import re
import sys

from playwright.sync_api import sync_playwright

LISTA = "https://www.rockstargames.com/videos?game=VI"

with sync_playwright() as p:
    nav = p.chromium.launch()
    pag = nav.new_page()
    pag.goto(LISTA, wait_until="networkidle", timeout=60000)
    for _ in range(6):                      # carrega mais itens da lista
        pag.mouse.wheel(0, 6000)
        pag.wait_for_timeout(1200)
    cartoes = pag.eval_on_selector_all(
        "a[href*='/videos/']", "els => els.map(e => [e.href, (e.innerText||e.getAttribute('aria-label')||'').trim()])")
    vistos = {}
    for href, texto in cartoes:
        vistos.setdefault(href, texto.replace("\n", " ")[:90])
    print(f"{len(vistos)} vídeos na lista")
    for href, texto in list(vistos.items())[:int(sys.argv[1]) if len(sys.argv) > 1 else 25]:
        midias = []
        handler = lambda r: midias.append(r.url) if re.search(r"(\.m3u8|\.mp4|\.mpd)(\?|$)", r.url) else None
        pag.on("request", handler)
        try:
            pag.goto(href, wait_until="networkidle", timeout=45000)
            pag.wait_for_timeout(4000)
            try:
                pag.click("button[aria-label*='lay'], .vjs-big-play-button, video", timeout=3000)
                pag.wait_for_timeout(4000)
            except Exception:
                pass
            titulo = pag.title()
        except Exception as e:
            titulo = f"falhou: {e}"
        pag.remove_listener("request", handler)
        print(f"== {href} | {titulo} | {texto}")
        for m in sorted(set(midias))[:4]:
            print("   midia:", m[:220])
    nav.close()
